import json
import unittest
import urllib.error
import urllib.request

from app.control_api import ControlAPIServer
from app.phone_provider import PhoneSession
from app.runtime import RuntimeContext


class PhoneAPITests(unittest.TestCase):
    def test_webhook_run_correlation_and_duplicates(self):
        runtime = RuntimeContext("qa", "run-1", "sms", {"sms"})
        phone = PhoneSession({"provider": "mock", "delivery_mode": "webhook"}, runtime)
        phone.start()
        api = ControlAPIServer(runtime, host="127.0.0.1", port=0)
        api.start()
        base = f"http://127.0.0.1:{api._server.server_port}/api/v1/identities/qa/runs/"
        def post(run, aid):
            req = urllib.request.Request(base + run + "/inputs/sms",
                json.dumps({"allocation_id": aid, "verification_code": "123456"}).encode(),
                {"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=2) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code
        try:
            self.assertEqual(post("wrong-run", "run-1"), 404)
            self.assertEqual(post("run-1", "wrong-allocation"), 400)
            self.assertEqual(post("run-1", "run-1"), 202)
            self.assertEqual(post("run-1", "run-1"), 409)
            self.assertEqual(runtime.wait_for_input("sms", 1)[1]["verification_code"], "123456")
        finally:
            api.stop()
            phone.close()
