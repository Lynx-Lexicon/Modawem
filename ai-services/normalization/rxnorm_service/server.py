"""Small HTTP service adapter for Spring Boot and other clients."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from rxnorm_normalize import Result, RxNormNormalizer

MAX_BODY_BYTES = 1_048_576


def _result_body(result: Result) -> dict[str, Any]:
    return asdict(result)


def normalize_payload(
    payload: Any, normalizer: RxNormNormalizer
) -> tuple[int, dict[str, Any]]:
    """Validate a request and return an HTTP status plus the JSON response."""
    if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
        return HTTPStatus.BAD_REQUEST, {
            "status": "error",
            "reason": "Request body must contain a string field named 'name'",
        }
    if not payload["name"].strip():
        return HTTPStatus.BAD_REQUEST, {
            "status": "error",
            "reason": "The name field must not be blank",
        }

    result = normalizer.normalize(payload["name"])
    status = (
        HTTPStatus.SERVICE_UNAVAILABLE if result.status == "error" else HTTPStatus.OK
    )
    return status, _result_body(result)


class _Handler(BaseHTTPRequestHandler):
    normalizer = RxNormNormalizer()

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(
            HTTPStatus.NOT_FOUND, {"status": "error", "reason": "Not found"}
        )

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/v1/normalize":
            self._send_json(
                HTTPStatus.NOT_FOUND, {"status": "error", "reason": "Not found"}
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "reason": "Invalid or oversized request body"},
            )
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "reason": "Request body must be valid JSON"},
            )
            return

        status, body = normalize_payload(payload, self.normalizer)
        self._send_json(status, body)


def main() -> None:
    host = os.environ.get("RXNORM_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("RXNORM_SERVICE_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"RxNorm service listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
