import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import rxnorm_normalize as rx

FIXTURE = Path(__file__).parent / "rxnorm_fixture.csv"


def _rows():
    with FIXTURE.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


@pytest.mark.integration
def test_fixture_matches_live_rxnorm_api(monkeypatch):
    monkeypatch.setattr(rx, "RETRIES", 0)
    monkeypatch.setattr(rx, "TIMEOUT_SEC", 3)
    normalizer = rx.RxNormNormalizer()
    probe = normalizer.normalize("acetaminophen")
    if probe.status == "error":
        pytest.skip(f"RxNorm API unavailable: {probe.reason}")

    def verify_row(row):
        result = normalizer.normalize(row["input"])
        if result.status == "error":
            return {
                "input": row["input"],
                "expected_rxcui": row["expected_rxcui"],
                "status": result.status,
                "reason": result.reason,
            }
        if result.status != "resolved" or result.rxcui != row["expected_rxcui"]:
            return {
                "input": row["input"],
                "expected_rxcui": row["expected_rxcui"],
                "actual_rxcui": result.rxcui,
                "status": result.status,
                "reason": result.reason,
            }
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        failures = [failure for failure in executor.map(verify_row, _rows()) if failure]
    assert not failures, "Live RxNorm mismatches: " + repr(failures)
