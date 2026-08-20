from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .runtime import RuntimeContext
from .profile_config import load_or_create_profile_config, patch_profile_config


class ControlAPIServer:
    def __init__(self, runtime: RuntimeContext, host: str = "0.0.0.0", port: int = 8090, logger=None, profile_config_path=None, project_name: str = "unknown", worker_type: str = "unknown"):
        self.runtime = runtime
        self.host = host
        self.port = int(port)
        self.logger = logger
        self.profile_config_path = profile_config_path
        self.project_name = str(project_name)
        self.worker_type = str(worker_type)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        runtime = self.runtime
        logger = self.logger
        profile_config_path = self.profile_config_path
        project_name = self.project_name
        worker_type = self.worker_type

        class Handler(BaseHTTPRequestHandler):
            server_version = "WorkerControlAPI/1.0"

            def log_message(self, fmt, *args):
                if logger:
                    logger.info("API %s", fmt % args)

            def _json(self, status: int, payload: dict):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _parts(self):
                return [p for p in urlparse(self.path).path.split("/") if p]

            def do_GET(self):
                parts = self._parts()
                if parts == ["api", "v1", "health"]:
                    return self._json(HTTPStatus.OK, {
                        "status": "ok",
                        "api_version": "v1",
                        "project": project_name,
                        "component": f"worker-{worker_type}",
                        "worker_type": worker_type,
                    })

                config_path = ["api", "v1", "identities", runtime.identity, "config"]
                if parts == config_path:
                    if profile_config_path is None:
                        return self._json(HTTPStatus.NOT_FOUND, {"error": "profile_config_unavailable"})
                    try:
                        profile = load_or_create_profile_config(profile_config_path, runtime.identity)
                    except Exception as exc:
                        return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "profile_config_read_failed", "message": str(exc)})
                    return self._json(HTTPStatus.OK, profile)

                base = ["api", "v1", "identities", runtime.identity, "runs"]
                if parts == base:
                    return self._json(HTTPStatus.OK, {"runs": [runtime.public_status()]})
                if parts == base + ["current"]:
                    return self._json(HTTPStatus.OK, runtime.public_status())
                if parts == base + [runtime.run_id]:
                    return self._json(HTTPStatus.OK, runtime.public_status())

                return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_PATCH(self):
                parts = self._parts()
                config_path = ["api", "v1", "identities", runtime.identity, "config"]
                if parts != config_path:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                if profile_config_path is None:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "profile_config_unavailable"})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
                if length <= 0:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "empty_body"})
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "malformed_json"})
                try:
                    profile = patch_profile_config(profile_config_path, runtime.identity, payload)
                except ValueError as exc:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_profile_config", "message": str(exc)})
                except Exception as exc:
                    return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "profile_config_write_failed", "message": str(exc)})
                if logger:
                    logger.info("Identity profile config updated through API; changes apply on next run")
                return self._json(HTTPStatus.OK, {
                    "status": "updated",
                    "identity": runtime.identity,
                    "applies": "next_run",
                    "config": profile,
                })

            def do_POST(self):
                parts = self._parts()
                expected_prefix = [
                    "api", "v1", "identities", runtime.identity,
                    "runs", runtime.run_id, "inputs"
                ]
                if len(parts) != len(expected_prefix) + 1 or parts[:len(expected_prefix)] != expected_prefix:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

                key = parts[-1]
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
                if length <= 0:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "empty_body"})
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "malformed_json"})

                accepted, reason = runtime.put_input(key, payload)
                if accepted:
                    return self._json(HTTPStatus.ACCEPTED, {
                        "status": "accepted",
                        "identity": runtime.identity,
                        "run_id": runtime.run_id,
                        "key": key,
                    })

                code = HTTPStatus.CONFLICT if reason in {"run_finished", "input_already_exists"} else HTTPStatus.NOT_FOUND
                return self._json(code, {"error": reason, "key": key})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="control-api", daemon=True)
        self._thread.start()
        if self.logger:
            self.logger.info("Control API listening on %s:%d", self.host, self.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
