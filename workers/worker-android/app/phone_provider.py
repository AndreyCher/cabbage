"""Normalized phone-number providers; no vendor fields enter scenario syntax."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol

from .runtime import FatalActionError


class ProviderError(FatalActionError):
    def __init__(self, message="Phone provider operation failed"):
        super().__init__(message, reason="phone_provider_failed")


class PhoneNumberProvider(Protocol):
    def allocate(self, request: dict, request_id: str) -> dict: ...
    def get_status(self, allocation_id: str) -> dict: ...
    def wait_message(self, allocation_id: str, timeout: float, stop: threading.Event) -> dict | None: ...
    def release(self, allocation_id: str) -> None: ...


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r"\+[1-9][0-9]{6,14}", value):
        raise ProviderError("Phone number must use E.164 format")
    return value


def allocation(data):
    if not isinstance(data, dict):
        raise ProviderError("Invalid allocation response")
    aid = data.get("allocation_id")
    if not isinstance(aid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", aid):
        raise ProviderError("Invalid allocation ID")
    result = {"allocation_id": aid, "number": number(data.get("number"))}
    for key in ("country", "operator", "mcc", "mnc"):
        if data.get(key) is not None:
            if not isinstance(data[key], str) or len(data[key]) > 128:
                raise ProviderError("Invalid allocation metadata")
            result[key] = data[key]
    return result


def message(data, allocation_id):
    if not isinstance(data, dict) or data.get("allocation_id") != allocation_id:
        raise ProviderError("SMS allocation mismatch")
    code = data.get("verification_code")
    text = data.get("text", "")
    if not isinstance(text, str) or len(text) > 16000:
        raise ProviderError("Invalid SMS text")
    if code is None:
        match = re.search(r"(?<!\d)(\d{4,8})(?!\d)", text)
        code = match.group(1) if match else None
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,32}", code):
        raise ProviderError("SMS has no valid verification code")
    return {"allocation_id": allocation_id, "verification_code": code, "text": text}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPPhoneProvider:
    """Bridge contract: POST /allocations; GET status/message; DELETE allocation.

    A vendor adapter/gateway implements this normalized API. Allocation is never
    retried automatically; request_id is an idempotency key for reconciliation.
    """

    def __init__(self, cfg):
        self.base = os.environ.get("WORKER_PHONE_PROVIDER_URL", "").rstrip("/")
        parsed = urllib.parse.urlsplit(self.base)
        if (parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ProviderError("Provider URL must be HTTPS (HTTP allowed only on loopback)")
        self.token = ""
        secret = os.environ.get("WORKER_PHONE_PROVIDER_TOKEN_FILE")
        if secret:
            try:
                self.token = Path(secret).read_text().strip()
            except OSError:
                raise ProviderError("Cannot read provider token file") from None
            if not self.token or "\n" in self.token or "\r" in self.token:
                raise ProviderError("Invalid provider token file")
        self.timeout = bounded(cfg, "request_timeout_sec", 10, 0.1, 60)
        self.allocation_timeout = bounded(cfg, "allocation_timeout_sec", 60, 0.1, 60)
        self.interval = bounded(cfg, "poll_interval_sec", 5, 0.1, 300)
        self.opener = urllib.request.build_opener(_NoRedirect())

    def _request(self, method, path, payload=None, request_id=None, timeout=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if request_id:
            headers["Idempotency-Key"] = request_id
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        try:
            req = urllib.request.Request(self.base + path, body, headers, method=method)
            with self.opener.open(req, timeout=timeout or self.timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ProviderError("Provider response exceeds size limit")
                return json.loads(raw) if raw else None
        except ProviderError:
            raise
        except (OSError, ValueError, urllib.error.URLError):
            # URLs, credentials and provider response bodies must not leak.
            raise ProviderError("Provider HTTP request failed") from None

    def allocate(self, request, request_id):
        return allocation(self._request("POST", "/allocations", request, request_id,
                                        timeout=self.allocation_timeout))

    def get_status(self, allocation_id):
        return self._request("GET", f"/allocations/{allocation_id}")

    def wait_message(self, allocation_id, timeout, stop):
        deadline = time.monotonic() + timeout
        while not stop.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            data = self._request("GET", f"/allocations/{allocation_id}/message",
                                 timeout=min(self.timeout, remaining))
            if data is not None:
                return message(data, allocation_id)
            stop.wait(min(self.interval, max(0, deadline - time.monotonic())))
        return None

    def release(self, allocation_id):
        self._request("DELETE", f"/allocations/{allocation_id}")


class MockPhoneProvider:
    """Explicit QA fixture: no real allocation, billing or SMS delivery."""
    def __init__(self, cfg):
        self.cfg = cfg

    def allocate(self, request, request_id):
        return allocation({"allocation_id": request_id,
                           "number": self.cfg.get("mock_number", "+15555550100"),
                           **{k: v for k, v in request.items() if k == "country" and v}})

    def get_status(self, allocation_id):
        return {"allocation_id": allocation_id, "status": "active", "test": True}

    def wait_message(self, allocation_id, timeout, stop):
        delay = bounded(self.cfg, "mock_delay_sec", 1, 0, 3600)
        if stop.wait(min(delay, timeout)) or delay > timeout:
            return None
        return message({"allocation_id": allocation_id,
                        "verification_code": self.cfg.get("mock_code", "123456")}, allocation_id)

    def release(self, allocation_id):
        pass


def bounded(cfg, key, default, low, high):
    value = cfg.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high:
        raise ProviderError(f"{key} must be between {low} and {high}")
    return float(value)


class PhoneSession:
    """Own one run allocation. Poll only when the scenario requests its SMS."""
    def __init__(self, cfg, runtime, provider=None):
        self.cfg, self.runtime = cfg, runtime
        self.delivery = cfg.get("delivery_mode", "polling")
        if self.delivery not in {"polling", "webhook"}:
            raise ProviderError("delivery_mode must be polling or webhook")
        self.timeout = bounded(cfg, "message_timeout_sec", 180, 0.1, 3600)
        kind = cfg.get("provider")
        if provider is None:
            if kind not in {"http", "mock"}:
                raise ProviderError("phone_number_provider.provider must be http or mock")
            provider = HTTPPhoneProvider(cfg) if kind == "http" else MockPhoneProvider(cfg)
        self.provider = provider
        self.key = cfg.get("input_key", "sms")
        self.number_key = cfg.get("number_input_key", "phone")
        for key in (self.key, self.number_key):
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
                raise ProviderError("Invalid phone input key")
        if self.key == self.number_key:
            raise ProviderError("Phone and SMS input keys must differ")
        self.allocated = None
        self.closed = False
        self.stop = threading.Event()
        self.runtime.input_validators[self.key] = self.validate_sms

    def validate_sms(self, data):
        if self.allocated is None:
            raise ProviderError("Phone allocation is not ready")
        return message(data, self.allocated["allocation_id"])

    def start(self):
        request = {key: self.cfg[key] for key in ("country", "service") if self.cfg.get(key)}
        self.allocated = allocation(self.provider.allocate(request, self.runtime.run_id))
        self.runtime.expected_inputs.update({self.key, self.number_key})
        accepted, _ = self.runtime.put_input(self.number_key, self.allocated)
        if not accepted:
            raise ProviderError("Cannot publish allocated phone number")
        if self.delivery == "polling":
            self.runtime.input_sources[self.key] = self.receive
        return self.allocated

    def receive(self, timeout):
        # Bounded polling on a helper thread lets API-delivered input or shutdown
        # win immediately while the provider HTTP request completes in background.
        outcome = []
        def poll():
            try:
                outcome.append(self.provider.wait_message(
                    self.allocated["allocation_id"], min(timeout, self.timeout), self.stop))
            except Exception:
                outcome.append(ProviderError())
        thread = threading.Thread(target=poll, name="phone-sms", daemon=True)
        thread.start()
        deadline = time.monotonic() + min(timeout, self.timeout)
        try:
            while thread.is_alive() and time.monotonic() < deadline:
                self.runtime.raise_if_shutdown_requested()
                if self.runtime.has_input(self.key):
                    return
                thread.join(0.1)
            self.runtime.raise_if_shutdown_requested()
            if self.runtime.has_input(self.key):
                return
            if outcome and isinstance(outcome[0], Exception):
                raise outcome[0]
            if outcome and outcome[0] is not None:
                self.runtime.put_input(self.key, message(outcome[0], self.allocated["allocation_id"]))
        finally:
            self.stop.set()
            thread.join(timeout=61)

    def close(self):
        self.stop.set()
        if not self.closed and self.allocated and self.cfg.get("release_on_finish", True):
            self.provider.release(self.allocated["allocation_id"])
            self.closed = True
