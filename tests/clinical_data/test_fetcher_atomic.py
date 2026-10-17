"""
Tests for DatasetFetcher atomic downloading and SHA-256 verification.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
import requests

from clinical_data.fetcher import DatasetFetcher, calculate_sha256

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_calculate_sha256():
    sample = FIXTURES_DIR / "ddi_sample_valid.csv"
    digest = calculate_sha256(sample)
    assert len(digest) == 64
    assert isinstance(digest, str)
    # Recalculating produces identical output
    assert calculate_sha256(sample) == digest


def test_fetch_local_file():
    fetcher = DatasetFetcher()
    sample = FIXTURES_DIR / "ddi_sample_valid.csv"
    res = fetcher.fetch(dataset="ddi", location=str(sample))

    try:
        assert res.staged_file_path.exists()
        assert res.bytes_downloaded == sample.stat().st_size
        assert res.sha256_checksum == calculate_sha256(sample)
    finally:
        res.cleanup()
        assert not res.staging_dir.exists()


def test_fetch_file_uri():
    fetcher = DatasetFetcher()
    sample = FIXTURES_DIR / "allergy_sample_valid.csv"
    file_uri = sample.as_uri()

    res = fetcher.fetch(dataset="allergy", location=file_uri)
    try:
        assert res.staged_file_path.exists()
        assert res.sha256_checksum == calculate_sha256(sample)
    finally:
        res.cleanup()


def test_fetch_expected_sha256_match():
    fetcher = DatasetFetcher()
    sample = FIXTURES_DIR / "ddi_sample_valid.csv"
    expected = calculate_sha256(sample)

    res = fetcher.fetch(dataset="ddi", location=str(sample), expected_sha256=expected)
    try:
        assert res.sha256_checksum == expected
    finally:
        res.cleanup()


def test_fetch_expected_sha256_mismatch():
    fetcher = DatasetFetcher()
    sample = FIXTURES_DIR / "ddi_sample_valid.csv"
    tampered_hash = "0" * 64

    with pytest.raises(RuntimeError) as exc_info:
        fetcher.fetch(dataset="ddi", location=str(sample), expected_sha256=tampered_hash)

    assert "SHA-256 integrity mismatch" in str(exc_info.value)


def test_fetch_nonexistent_file():
    fetcher = DatasetFetcher()
    with pytest.raises(RuntimeError) as exc_info:
        fetcher.fetch(dataset="ddi", location="nonexistent_dataset_location.csv")

    assert "Failed to fetch dataset" in str(exc_info.value)


def test_fetch_http_success():
    fetcher = DatasetFetcher()
    sample = FIXTURES_DIR / "ddi_sample_valid.csv"
    sample_bytes = sample.read_bytes()

    mock_resp = MagicMock()
    mock_resp.iter_content.return_value = [sample_bytes]
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        res = fetcher.fetch(dataset="ddi", location="https://example.com/test_ddi.csv")
        try:
            assert res.staged_file_path.exists()
            assert res.sha256_checksum == calculate_sha256(sample)
        finally:
            res.cleanup()


def test_fetch_http_network_failure():
    fetcher = DatasetFetcher()
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Simulated DNS timeout")):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch(dataset="ddi", location="https://invalid-host-clinical-data.com/dataset.csv")

        assert "HTTP fetch error" in str(exc_info.value) or "Failed to fetch" in str(exc_info.value)
