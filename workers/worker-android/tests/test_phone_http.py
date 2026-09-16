import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app.phone_provider import HTTPPhoneProvider, PhoneSession, ProviderError
from app.runtime import RuntimeContext


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.response_mode = "normal"
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                owner.calls.append((self.command, self.path, self.headers.get("Idempotency-Key"),
                                    self.headers.get("Authorization")))
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if owner.response_mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "/leak")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                if owner.response_mode == "invalid":
                    self.wfile.write(b'super-secret-token invalid JSON')
                    return
                self.wfile.write(json.dumps({"allocation_id": "alloc-1", "number": "+15555550100"}).encode())

            def do_GET(self):
                owner.calls.append((self.command, self.path))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"allocation_id": "alloc-1", "verification_code": "000123"}).encode())

            def do_DELETE(self):
                owner.calls.append((self.command, self.path))
                self.send_response(204)
                self.end_headers()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, {"WORKER_PHONE_PROVIDER_URL": f"http://127.0.0.1:{self.server.server_port}"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_allocation_sms_release_and_secret(self):
        with tempfile.NamedTemporaryFile(mode="w") as token:
            token.write("super-secret-token")
            token.flush()
            with patch.dict(os.environ, {"WORKER_PHONE_PROVIDER_TOKEN_FILE": token.name}):
                runtime = RuntimeContext("qa", "run-id", "sms", {"sms"})
                phone = PhoneSession({"provider": "http"}, runtime)
                phone.start()
                ok, sms = runtime.wait_for_input("sms", 5)
                phone.close()
                phone.close()
                self.assertTrue(ok)
                self.assertEqual(sms["verification_code"], "000123")
                self.assertEqual(self.calls[0], ("POST", "/allocations", "run-id", "Bearer super-secret-token"))
                self.assertEqual(self.calls[-1], ("DELETE", "/allocations/alloc-1"))
                self.assertEqual(len(self.calls), 3)
                self.assertNotIn("super-secret-token", str(runtime.events()))

    def test_redirect_blocked_and_no_retry(self):
        self.response_mode = "redirect"
        with self.assertRaises(ProviderError):
            HTTPPhoneProvider({}).allocate({}, "id")
        self.assertEqual(len(self.calls), 1)

    def test_error_does_not_expose_response(self):
        self.response_mode = "invalid"
        with self.assertRaises(ProviderError) as caught:
            HTTPPhoneProvider({}).allocate({}, "id")
        self.assertNotIn("super-secret-token", str(caught.exception))

    def test_unsafe_urls_rejected(self):
        for url in ("http://example.com", "https://user:pass@example.com", "file:///tmp/x", "https://example.com?token=x"):
            with patch.dict(os.environ, {"WORKER_PHONE_PROVIDER_URL": url}), self.assertRaises(ProviderError):
                HTTPPhoneProvider({})
