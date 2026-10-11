from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from threading import Barrier

import rxnorm_service.server as service
import rxnorm_normalize as rx


class FakeNormalizer:
    def __init__(self, result):
        self.result = result
        self.inputs = []

    def normalize(self, name):
        self.inputs.append(name)
        return self.result


def test_normalize_payload_preserves_resolved_json_contract():
    normalizer = FakeNormalizer(
        rx.Result("metformn", "6809", "metformin", 0.95, "resolved", None, [])
    )

    status, body = service.normalize_payload({"name": "metformn"}, normalizer)

    assert status == HTTPStatus.OK
    assert body["status"] == "resolved"
    assert body["rxcui"] == "6809"
    assert normalizer.inputs == ["metformn"]


def test_normalize_payload_returns_unresolved_as_successful_http_response():
    normalizer = FakeNormalizer(
        rx.Result("unknown", None, None, 0.0, "unresolved", "not found", [])
    )

    status, body = service.normalize_payload({"name": "unknown"}, normalizer)

    assert status == HTTPStatus.OK
    assert body["status"] == "unresolved"
    assert body["rxcui"] is None


def test_normalize_payload_maps_api_errors_to_service_unavailable():
    normalizer = FakeNormalizer(
        rx.Result("metformin", None, None, 0.0, "error", "offline", [])
    )

    status, body = service.normalize_payload({"name": "metformin"}, normalizer)

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert body["status"] == "error"
    assert body["reason"] == "offline"


def test_normalize_payload_rejects_invalid_requests():
    normalizer = FakeNormalizer(None)

    for payload in ({}, {"name": 6809}, {"name": "   "}, "not-an-object"):
        status, body = service.normalize_payload(payload, normalizer)
        assert status == HTTPStatus.BAD_REQUEST
        assert body["status"] == "error"

    assert normalizer.inputs == []


def test_independent_normalize_requests_progress_concurrently():
    barrier = Barrier(2)

    class BlockingNormalizer:
        def normalize(self, name):
            barrier.wait(timeout=1)
            return rx.Result(name, "6809", "metformin", 1.0, "resolved", None, [])

    normalizer = BlockingNormalizer()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda name: service.normalize_payload({"name": name}, normalizer),
                ("metformin", "metformn"),
            )
        )
    assert [status for status, _ in results] == [HTTPStatus.OK, HTTPStatus.OK]
