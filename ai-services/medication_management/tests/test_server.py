"""Tests for the medication management health endpoint."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from medication_management.server import create_server


class TestHealthEndpoint(unittest.TestCase):
    """The service exposes only a successful health check endpoint."""

    def setUp(self):
        self.server = create_server(host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = "http://127.0.0.1:{}/healthz".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_health_check_returns_ok(self):
        with urlopen(self.url) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers["Content-Type"], "application/json; charset=utf-8"
            )
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(json.load(response), {"status": "ok"})

    def test_unknown_path_returns_not_found(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url.replace("/healthz", "/"))

        self.assertEqual(error.exception.code, 404)
