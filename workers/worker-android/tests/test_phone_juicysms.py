import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app.phone_provider import JuicySMSPhoneProvider, ProviderError


class JuicySMSTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, payload):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.calls.append((self.command, self.path, json.loads(body or b"{}"), self.headers.get("Authorization")))
                if self.path == "/orders":
                    self._reply({"id": 42, "phone_number": "+4915112345678"})
                else:
                    self._reply({"ok": True})

            def do_GET(self):
                owner.calls.append((self.command, self.path, self.headers.get("Authorization")))
                self._reply({"data": [{"text": "Code: 001234"}]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_order_poll_and_cancel_without_secret_leak(self):
        with tempfile.NamedTemporaryFile(mode="w") as token:
            token.write("juicy-secret")
            token.flush()
            with patch.dict(os.environ, {"WORKER_JUICY_SMS_TOKEN_FILE": token.name}):
                with patch.object(JuicySMSPhoneProvider, "API", f"http://127.0.0.1:{self.server.server_port}"):
                    provider = JuicySMSPhoneProvider({"poll_interval_sec": .1})
                    allocated = provider.allocate({"country": "DE", "service_id": 12, "max_price": 0.25}, "run-id")
                    sms = provider.wait_message("42", 1, threading.Event())
                    provider.release("42")
        self.assertEqual(allocated, {"allocation_id": "42", "number": "+4915112345678", "country": "de"})
        self.assertEqual(sms["verification_code"], "001234")
        self.assertEqual(self.calls[0], ("POST", "/orders", {"service_id": 12, "country": "de", "max_price": 0.25}, "Bearer juicy-secret"))
        self.assertEqual(self.calls[-1][0:2], ("POST", "/orders/42/cancel"))
        self.assertNotIn("juicy-secret", str(allocated) + str(sms))

    def test_requires_service_and_secret_file(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                JuicySMSPhoneProvider({})
        with tempfile.NamedTemporaryFile(mode="w") as token:
            token.write("token")
            token.flush()
            with patch.dict(os.environ, {"WORKER_JUICY_SMS_TOKEN_FILE": token.name}):
                provider = JuicySMSPhoneProvider({})
                with self.assertRaises(ProviderError):
                    provider.allocate({"country": "de", "service_id": "12"}, "run-id")
