from __future__ import annotations

import copy
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any


_TEMPLATE_RE = re.compile(r"\{\{\s*(input|webhook)\.([a-zA-Z0-9_.-]+)\s*\}\}")


class FatalActionError(RuntimeError):
    """Controlled scenario failure that must abort even in debug mode."""

    def __init__(self, message: str, *, reason: str = "scenario_failed", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.details = dict(details or {})


class ShutdownRequested(RuntimeError):
    """Internal control-flow exception for a graceful user/container shutdown."""

    def __init__(self, signal_number: int | None = None):
        super().__init__("Shutdown requested")
        self.signal_number = signal_number


class RuntimeContext:
    def __init__(self, identity: str, run_id: str, scenario: str, expected_inputs: set[str] | None = None):
        self.identity = identity
        self.run_id = run_id
        self.scenario = scenario
        self.expected_inputs = set(expected_inputs or set())
        self.status = "starting"
        self.current_action: int | None = None
        self.waiting_input: dict[str, Any] | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.error_reason: str | None = None
        self.error_message: str | None = None
        self._inputs: dict[str, Any] = {}
        self._webhooks: dict[str, Any] = {}
        self._events: list[dict[str, Any]] = []
        self._condition = threading.Condition()
        self._shutdown_event = threading.Event()
        self.shutdown_signal: int | None = None

    def _event(self, event: str, **fields: Any) -> None:
        self._events.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        })

    def request_shutdown(self, signal_number: int | None = None) -> bool:
        """Request graceful shutdown. Returns True only for the first request."""
        with self._condition:
            first = not self._shutdown_event.is_set()
            if first:
                self.shutdown_signal = int(signal_number) if signal_number is not None else None
                self._event("shutdown_requested", signal=self.shutdown_signal)
                self._shutdown_event.set()
                self._condition.notify_all()
            return first

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    def raise_if_shutdown_requested(self) -> None:
        if self._shutdown_event.is_set():
            raise ShutdownRequested(self.shutdown_signal)

    def interruptible_wait(self, timeout_sec: float) -> bool:
        """Wait up to timeout_sec. Return False if shutdown was requested."""
        return not self._shutdown_event.wait(max(0.0, timeout_sec))

    def set_status(self, status: str, *, current_action: int | None = None) -> None:
        with self._condition:
            self.status = status
            self.current_action = current_action
            if status not in {"waiting_input"}:
                self.waiting_input = None
            if status in {"completed", "failed", "stopped"}:
                self.finished_at = datetime.now(timezone.utc).isoformat()
            self._condition.notify_all()

    def set_action(self, index: int) -> None:
        with self._condition:
            self.current_action = index
            if self.status not in {"waiting_input"}:
                self.status = "running"

    def set_failure(self, reason: str, message: str) -> None:
        with self._condition:
            self.error_reason = str(reason)
            self.error_message = str(message)
            self.status = "failed"
            self.current_action = None
            self.waiting_input = None
            self.finished_at = datetime.now(timezone.utc).isoformat()
            self._condition.notify_all()

    def put_input(self, key: str, value: Any) -> tuple[bool, str]:
        with self._condition:
            if self.status in {"completed", "failed", "stopped"} or self._shutdown_event.is_set():
                return False, "run_finished"
            if self.expected_inputs and key not in self.expected_inputs:
                return False, "unknown_input_key"
            if key in self._inputs:
                return False, "input_already_exists"
            self._inputs[key] = copy.deepcopy(value)
            self._event("input_received", key=key)
            self._condition.notify_all()
            return True, "accepted"

    def wait_for_input(self, key: str, timeout_sec: float) -> tuple[bool, Any | None]:
        deadline = time.monotonic() + timeout_sec
        with self._condition:
            if self._shutdown_event.is_set():
                raise ShutdownRequested(self.shutdown_signal)
            if key in self._inputs:
                return True, copy.deepcopy(self._inputs[key])

            self.status = "waiting_input"
            self.waiting_input = {
                "key": key,
                "timeout_sec": timeout_sec,
                "started_monotonic": time.monotonic(),
                "deadline_monotonic": deadline,
            }
            self._event("waiting_input", key=key, timeout_sec=timeout_sec)

            while key not in self._inputs:
                if self._shutdown_event.is_set():
                    self.waiting_input = None
                    raise ShutdownRequested(self.shutdown_signal)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._event("input_timeout", key=key, timeout_sec=timeout_sec)
                    self.status = "running"
                    self.waiting_input = None
                    return False, None
                # Wake periodically as a fallback; request_shutdown also notify_all().
                self._condition.wait(timeout=min(remaining, 0.5))

            value = copy.deepcopy(self._inputs[key])
            self.status = "running"
            self.waiting_input = None
            return True, value

    def set_default_input(self, key: str, value: Any) -> None:
        with self._condition:
            self._inputs[key] = copy.deepcopy(value)
            self._event("input_default_used", key=key)
            self._condition.notify_all()

    def consume_input(self, key: str) -> None:
        with self._condition:
            if key in self._inputs:
                del self._inputs[key]
                self._event("input_consumed", key=key)

    def _get_path(self, namespace: str, path: str) -> Any:
        parts = path.split(".")
        if not parts:
            raise KeyError(path)
        store = self._inputs if namespace == "input" else self._webhooks
        with self._condition:
            if parts[0] not in store:
                raise KeyError(f"Runtime {namespace} key not found: {parts[0]}")
            value: Any = store[parts[0]]
            for part in parts[1:]:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    raise KeyError(f"Runtime {namespace} path not found: {namespace}.{path}")
            return copy.deepcopy(value)

    def get_input_path(self, path: str) -> Any:
        return self._get_path("input", path)

    def set_webhook_result(self, key: str, value: Any) -> None:
        with self._condition:
            self._webhooks[str(key)] = copy.deepcopy(value)
            self._event("webhook_result_saved", key=str(key))
            self._condition.notify_all()

    def get_webhook_path(self, path: str) -> Any:
        return self._get_path("webhook", path)

    def resolve_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self.resolve_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve_value(v) for v in value]
        if not isinstance(value, str):
            return value

        full = _TEMPLATE_RE.fullmatch(value)
        if full:
            return self._get_path(full.group(1), full.group(2))

        def repl(match: re.Match[str]) -> str:
            namespace, path = match.group(1), match.group(2)
            resolved = self._get_path(namespace, path)
            if isinstance(resolved, (dict, list)):
                raise TypeError(
                    f"Cannot embed non-scalar runtime value {namespace}.{path} inside a string"
                )
            return str(resolved)

        return _TEMPLATE_RE.sub(repl, value)

    def public_status(self) -> dict[str, Any]:
        with self._condition:
            waiting = None
            if self.waiting_input:
                remaining = max(0, int(round(self.waiting_input["deadline_monotonic"] - time.monotonic())))
                waiting = {
                    "key": self.waiting_input["key"],
                    "timeout_sec": self.waiting_input["timeout_sec"],
                    "remaining_sec": remaining,
                }
            return {
                "identity": self.identity,
                "run_id": self.run_id,
                "scenario": self.scenario,
                "status": self.status,
                "current_action": self.current_action,
                "waiting_input": waiting,
                "expected_inputs": sorted(self.expected_inputs),
                "received_inputs": sorted(self._inputs.keys()),
                "shutdown_requested": self._shutdown_event.is_set(),
                "shutdown_signal": self.shutdown_signal,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "error_reason": self.error_reason,
                "error_message": self.error_message,
            }

    def events(self) -> list[dict[str, Any]]:
        with self._condition:
            return copy.deepcopy(self._events)
