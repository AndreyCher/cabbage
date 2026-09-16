"""Opt-in, application-scoped Android telephony fixtures for QA."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from .runtime import FatalActionError


class TelephonyError(FatalActionError):
    def __init__(self, message):
        super().__init__(message, reason="telephony_failed")


def check_digit(digits):
    total = sum((int(d) * 2 // 10 + int(d) * 2 % 10) if i % 2 else int(d)
                for i, d in enumerate(digits))
    return str((-total) % 10)


def resolve_identity(cfg, identity, cloud_number=None, *, allow_missing_cloud_number=False):
    if not cfg.get("enabled", False):
        return None
    if cfg.get("mode", "emulated") != "emulated" or cfg.get("backend", "app_api") != "app_api":
        raise TelephonyError("Supported telephony mode/backend: emulated/app_api")
    packages = cfg.get("packages")
    if not isinstance(packages, list) or not packages or any(
        not isinstance(p, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", p)
        for p in packages
    ):
        raise TelephonyError("telephony.packages must list the QA application packages")
    operator = cfg.get("operator", {})
    if not isinstance(operator, dict):
        raise TelephonyError("telephony.operator must be an object")
    mcc, mnc = operator.get("mcc", cfg.get("mcc")), operator.get("mnc", cfg.get("mnc"))
    if not isinstance(mcc, str) or not re.fullmatch(r"[0-9]{3}", mcc):
        raise TelephonyError("MCC must be a three-digit string")
    if not isinstance(mnc, str) or not re.fullmatch(r"[0-9]{2,3}", mnc):
        raise TelephonyError("MNC must be a two/three-digit string (keep leading zeroes)")
    name, country = operator.get("name"), operator.get("country_iso")
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise TelephonyError("Operator name is required (maximum 64 characters)")
    if not isinstance(country, str) or not re.fullmatch(r"[a-zA-Z]{2}", country):
        raise TelephonyError("Operator country_iso must be a two-letter country code")
    seed = str(int(hashlib.sha256(identity.encode()).hexdigest(), 16))
    generated_imei = "0044" + seed[:10]
    generated_imei += check_digit(generated_imei)
    def field(key, generated):
        value = cfg.get(key, {"mode": "generated"})
        if isinstance(value, dict):
            mode = value.get("mode", "fixed")
            if mode == "generated":
                return generated
            if mode != "fixed":
                raise TelephonyError(f"Unsupported {key} mode")
            value = value.get("value")
        return value
    imei = field("imei", generated_imei)
    imsi = field("imsi", mcc + mnc + seed[:15-len(mcc+mnc)])
    if not isinstance(imei, str) or not re.fullmatch(r"[0-9]{15}", imei) or check_digit(imei[:14]) != imei[-1]:
        raise TelephonyError("IMEI must contain 15 digits and a valid check digit")
    if not isinstance(imsi, str) or not re.fullmatch(r"[0-9]{15}", imsi) or not imsi.startswith(mcc+mnc):
        raise TelephonyError("IMSI must contain 15 digits and start with MCC/MNC")
    phone = cfg.get("phone_number")
    if isinstance(phone, dict):
        source = phone.get("source", "fixed")
        if source not in {"fixed", "cloud_provider"}:
            raise TelephonyError("Unsupported phone_number.source")
        phone = cloud_number if source == "cloud_provider" else phone.get("value")
        if phone is None and source == "cloud_provider" and allow_missing_cloud_number:
            # Null is the native Android API representation for a device with
            # no line number. It makes this a QA fixture without claiming a
            # persistent SIM/number after a worker restart.
            phone = None
    if phone is None and allow_missing_cloud_number:
        return {"imei": imei, "imsi": imsi, "phone_number": None,
                "operator": name, "mcc": mcc, "mnc": mnc, "country_iso": country.lower()}
    if not isinstance(phone, str) or not re.fullmatch(r"\+[1-9][0-9]{6,14}", phone):
        raise TelephonyError("Telephony phone_number must use E.164 or an allocated cloud number")
    return {"imei": imei, "imsi": imsi, "phone_number": phone,
            "operator": name, "mcc": mcc, "mnc": mnc, "country_iso": country.lower()}


class TelephonySession:
    def __init__(self, device, cfg, values):
        self.device, self.cfg, self.values = device, cfg, values
        self.remote = None
        self.sessions = {}
        self.server = None
        self.prepared = False

    def prepare(self):
        """Restart adbd before Appium establishes its port forwards/session."""
        if self.prepared:
            return
        self.device.adb("root")
        self.device.adb("wait-for-device")
        if self.device.adb("shell", "id", "-u").stdout.strip() != "0":
            raise TelephonyError("Telephony QA requires an emulator with adb root")
        self.device.adb("push", "/opt/worker-android/tools/frida-server", "/data/local/tmp/worker-telephony")
        self.device.adb("shell", "chmod", "700", "/data/local/tmp/worker-telephony")
        self.prepared = True

    def start(self):
        import frida
        self.prepare()
        self.server = subprocess.Popen(
            ["adb", "-s", self.device.serial, "shell", "/data/local/tmp/worker-telephony", "-l", "127.0.0.1:27042"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.device.adb("forward", "tcp:27042", "tcp:27042")
        self.remote = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                self.remote.enumerate_processes()
                return
            except (frida.TransportError, frida.ServerNotRunningError,
                    frida.ProcessNotFoundError, frida.NotSupportedError):
                time.sleep(.2)
        raise TelephonyError("Telephony QA runtime did not become ready")

    def launch(self, package):
        if package not in self.cfg["packages"]:
            return False
        # Each explicit launch starts a fresh process so the fixture is installed
        # before Application.onCreate and cannot leave a cached original identity.
        if package in self.sessions:
            session, script = self.sessions.pop(package)
            session.detach()
        self.device.adb("shell", "am", "force-stop", package)
        pid = self.remote.spawn([package])
        session = None
        try:
            session = self.remote.attach(pid)
            source = Path(__file__).with_name("telephony_hook.js").read_text()
            script = session.create_script("const fixture = " + json.dumps(self.values) + ";\n" + source)
            script.load()
            result = script.exports_sync.install()
            if not result:
                raise TelephonyError("Telephony API fixture was not installed")
            self.sessions[package] = session, script
            self.remote.resume(pid)
            return True
        except Exception:
            self.remote.kill(pid)
            if session:
                session.detach()
            raise TelephonyError("Cannot instrument QA application telephony APIs") from None

    def close(self):
        for session, _ in self.sessions.values():
            try:
                session.detach()
            except Exception:
                pass
        self.sessions.clear()
        if self.server:
            self.device.adb("shell", "pkill", "-f", "^/data/local/tmp/worker-telephony", check=False)
            self.server.terminate()
            self.server.wait(timeout=5)
        if self.remote:
            self.device.adb("forward", "--remove", "tcp:27042", check=False)
