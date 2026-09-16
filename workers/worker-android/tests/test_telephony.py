import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.telephony import TelephonyError, TelephonySession, resolve_identity


def profile():
    return {"enabled": True, "packages": ["org.example.qa"],
            "operator": {"name": "QA DE", "mcc": "262", "mnc": "01", "country_iso": "de"},
            "phone_number": "+4915112345678"}


class IdentityTests(unittest.TestCase):
    def test_disabled(self):
        self.assertIsNone(resolve_identity({}, "qa"))

    def test_generation_is_stable_and_coherent(self):
        first = resolve_identity(profile(), "one")
        self.assertEqual(first, resolve_identity(profile(), "one"))
        self.assertNotEqual(first["imei"], resolve_identity(profile(), "two")["imei"])
        self.assertTrue(first["imsi"].startswith("26201"))
        explicit = {**profile(), "imei": first["imei"], "imsi": first["imsi"]}
        self.assertEqual(first, resolve_identity(explicit, "other"))

    def test_invalid_fields_fail(self):
        for changes in ({"imei": "123"}, {"imsi": "310260123456789"},
                        {"packages": []}, {"packages": ["bad; shell"]},
                        {"phone_number": "1234"}, {"mode": "real"}):
            with self.subTest(changes=changes), self.assertRaises(TelephonyError):
                resolve_identity({**profile(), **changes}, "qa")

    def test_leading_zero_mnc_requires_string(self):
        cfg = profile()
        cfg["operator"]["mnc"] = 1
        with self.assertRaises(TelephonyError):
            resolve_identity(cfg, "qa")

    def test_cloud_number_required_and_applied(self):
        cfg = profile()
        cfg["phone_number"] = {"source": "cloud_provider"}
        with self.assertRaises(TelephonyError):
            resolve_identity(cfg, "qa")
        self.assertEqual(resolve_identity(cfg, "qa", "+4915112345678")["phone_number"], "+4915112345678")

    def test_profile_not_modified(self):
        cfg = profile()
        before = copy.deepcopy(cfg)
        resolve_identity(cfg, "qa")
        self.assertEqual(cfg, before)

    def test_start_retries_transient_system_server_absence(self):
        class NotReady(Exception):
            pass
        remote = MagicMock()
        remote.enumerate_processes.side_effect = [NotReady(), []]
        manager = MagicMock()
        manager.add_remote_device.return_value = remote
        frida = SimpleNamespace(get_device_manager=lambda: manager,
                                TransportError=NotReady, ServerNotRunningError=NotReady,
                                ProcessNotFoundError=NotReady, NotSupportedError=NotReady)
        device = MagicMock()
        device.serial = "emulator-5554"
        device.adb.return_value.stdout = "0\n"
        session = TelephonySession(device, profile(), resolve_identity(profile(), "qa"))
        with patch.dict("sys.modules", {"frida": frida}), patch("app.telephony.subprocess.Popen"), patch("app.telephony.time.sleep"):
            session.prepare()
            session.start()
        self.assertEqual(remote.enumerate_processes.call_count, 2)
        self.assertEqual(sum(call.args == ("root",) for call in device.adb.call_args_list), 1)

    def test_known_imei_check_digit(self):
        cfg = {**profile(), "imei": "490154203237518"}
        self.assertEqual(resolve_identity(cfg, "qa")["imei"], "490154203237518")
        cfg["imei"] = "490154203237519"
        with self.assertRaises(TelephonyError):
            resolve_identity(cfg, "qa")
