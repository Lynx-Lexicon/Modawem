"""HTTP server for the medication management service."""

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DEFAULT_PORT = 8080
HOST_ENV = "MEDICATION_MANAGEMENT_SERVICE_HOST"
PORT_ENV = "MEDICATION_MANAGEMENT_SERVICE_PORT"


class MedicationManagementHandler(BaseHTTPRequestHandler):
    """Serve the medication management service health endpoint."""

    def _send_json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if urlsplit(self.path).path != "/healthz":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error"})
            return

        self._send_json(HTTPStatus.OK, {"status": "ok"})


def create_server(host="127.0.0.1", port=DEFAULT_PORT):
    """Create the HTTP server without starting its serving loop."""
    return ThreadingHTTPServer((host, port), MedicationManagementHandler)


def main():
    """Start the HTTP server using the configured port."""
    host = os.environ.get(HOST_ENV, "127.0.0.1")
    port = int(os.environ.get(PORT_ENV, DEFAULT_PORT))
    server = create_server(host=host, port=port)
    print(f"Medication management service listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
