import logging
import threading
import time
import unittest
from pathlib import Path

from app.actions import ActionEngine
from app.phone_provider import PhoneSession, ProviderError, allocation, message
from app.runtime import RuntimeContext, FatalActionError, ShutdownRequested


class ProviderTests(unittest.TestCase):
    def runtime(self):
        return RuntimeContext("qa", "run-123", "test", {"sms"})

    def test_mock_full_flow_and_templates(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "mock_delay_sec": 0}, runtime)
        phone.start()
        self.assertEqual(runtime.resolve_value("{{input.phone.number}}"), "+15555550100")
        ok, value = runtime.wait_for_input("sms", 2)
        self.assertTrue(ok)
        self.assertEqual(value["verification_code"], "123456")
        self.assertEqual(runtime.resolve_value("{{input.sms.verification_code}}"), "123456")
        phone.close()
        phone.close()
        self.assertTrue(phone.closed)
        self.assertNotIn("123456", str(runtime.events()))

    def test_mismatched_allocation_rejected(self):
        with self.assertRaises(ProviderError):
            message({"allocation_id": "wrong", "verification_code": "1234"}, "run-123")

    def test_sms_extraction_and_validation(self):
        self.assertEqual(message({"allocation_id": "a", "text": "Your code: 019234"}, "a")["verification_code"], "019234")
        for data in ({}, {"allocation_id": "../secret", "number": "+15555550100"},
                     {"allocation_id": "x", "number": "123"}):
            with self.assertRaises(ProviderError):
                allocation(data)

    def test_timeout_is_fatal_in_debug(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "mock_delay_sec": 1}, runtime)
        phone.start()
        engine = ActionEngine(None, Path("."), logging.getLogger("test"), runtime, True)
        with self.assertRaises(FatalActionError) as caught:
            engine.run([{"type": "wait_input", "key": "sms", "timeout_sec": .01}])
        self.assertEqual(caught.exception.reason, "input_timeout")
        phone.close()

    def test_shutdown_interrupts_polling(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "mock_delay_sec": 30}, runtime)
        phone.start()
        timer = threading.Timer(.05, runtime.request_shutdown)
        timer.start()
        start = time.monotonic()
        with self.assertRaises(ShutdownRequested):
            runtime.wait_for_input("sms", 60)
        self.assertLess(time.monotonic() - start, 1)
        timer.join()
        phone.close()

    def test_api_input_wins_over_polling(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "mock_delay_sec": 30}, runtime)
        phone.start()
        timer = threading.Timer(.05, lambda: runtime.put_input("sms", {"allocation_id": "run-123", "verification_code": "9876"}))
        timer.start()
        ok, result = runtime.wait_for_input("sms", 5)
        timer.join()
        self.assertTrue(ok)
        self.assertEqual(result["verification_code"], "9876")
        phone.close()

    def test_webhook_only_rejects_wrong_allocation(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "delivery_mode": "webhook"}, runtime)
        self.assertEqual(runtime.put_input("sms", {"allocation_id": "run-123", "verification_code": "0000"}), (False, "invalid_input"))
        phone.start()
        self.assertNotIn("sms", runtime.input_sources)
        self.assertEqual(runtime.put_input("sms", {"allocation_id": "other", "verification_code": "1234"}), (False, "invalid_input"))
        self.assertEqual(runtime.put_input("sms", {"allocation_id": "run-123", "verification_code": "0192"}), (True, "accepted"))
        self.assertEqual(runtime.wait_for_input("sms", .1)[1]["verification_code"], "0192")
        phone.close()

    def test_default_on_timeout(self):
        runtime = self.runtime()
        phone = PhoneSession({"provider": "mock", "mock_delay_sec": 1}, runtime)
        phone.start()
        engine = ActionEngine(None, Path("."), logging.getLogger("test"), runtime)
        result = engine.run([{"type": "wait_input", "key": "sms", "timeout_sec": .01,
                              "on_timeout": "default", "default": {"verification_code": "0000"}}])
        self.assertEqual(result[0]["status"], "PASS")
        self.assertEqual(runtime.resolve_value("{{input.sms.verification_code}}"), "0000")
        phone.close()

    def test_invalid_provider_and_timeouts(self):
        for cfg in ({"provider": "bad"}, {"provider": "mock", "message_timeout_sec": -1},
                    {"provider": "mock", "input_key": "phone"}):
            with self.assertRaises(ProviderError):
                PhoneSession(cfg, self.runtime())
