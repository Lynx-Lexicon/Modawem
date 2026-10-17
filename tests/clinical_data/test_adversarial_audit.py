"""
Adversarial and Failure-Safety Verification Suite for Modawem Clinical Data Infrastructure.
Covers crash consistency, self-healing, immutability, corruption detection,
path traversal prevention, transport security, credential scrubbing, and concurrency.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import pytest

from clinical_data.config import get_reports_dir
from clinical_data.differ import DatasetDiffer
from clinical_data.fetcher import DatasetFetcher, calculate_sha256, sanitize_url_for_logging
from clinical_data.manifest import ManifestManager, sanitize_version_id, DatasetLock
from clinical_data.validator import DatasetValidator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def audit_cache_env(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache" / "clinical_data"
    rep_path = tmp_path / "reports" / "refresh-reports"
    cache_path.mkdir(parents=True, exist_ok=True)
    rep_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("MODAWEM_DATA_CACHE_DIR", str(cache_path))
    monkeypatch.setenv("MODAWEM_REPORTS_DIR", str(rep_path))
    return {"cache": cache_path, "reports": rep_path}


# -----------------------------------------------------------------------------
# 1. Crash Consistency & Self-Healing Tests
# -----------------------------------------------------------------------------

def test_crash_consistency_self_healing_mismatched_active(audit_cache_env):
    """
    Simulates a scenario where active/modawem_ddi.csv was corrupted or out of sync
    with manifest.active_version. ManifestManager must detect the mismatch and
    self-heal from the immutable historical version.
    """
    mgr = ManifestManager("ddi")
    sample_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    valid_hash = calculate_sha256(sample_file)

    # Ingest version
    mgr.activate_version(
        staged_csv_path=sample_file,
        sha256_hash=valid_hash,
        row_count=6,
        remote_location="loc",
        custom_version_id="v1.0.0",
    )

    active_csv = mgr.get_active_file_path()
    assert calculate_sha256(active_csv) == valid_hash

    # Simulate crash / active file corruption by external actor
    with open(active_csv, "w", encoding="utf-8") as f:
        f.write("corrupted data that does not match manifest")

    assert calculate_sha256(active_csv) != valid_hash

    # Calling get_active_file_path() must detect divergence and self-heal!
    restored_active = mgr.get_active_file_path()
    assert restored_active is not None
    assert calculate_sha256(restored_active) == valid_hash


def test_immutable_historical_version_rejects_overwrite(audit_cache_env):
    """
    Guarantees that an existing historical version cannot be overwritten
    with different bytes under the same version ID.
    """
    mgr = ManifestManager("ddi")
    sample_v1 = FIXTURES_DIR / "ddi_sample_valid.csv"
    sample_v2 = FIXTURES_DIR / "ddi_sample_v2.csv"

    # Activate v1.0.0
    mgr.activate_version(
        staged_csv_path=sample_v1,
        sha256_hash=calculate_sha256(sample_v1),
        row_count=6,
        remote_location="loc1",
        custom_version_id="v1.0.0",
    )

    # Attempt to activate v1.0.0 with different bytes
    with pytest.raises(ValueError) as exc_info:
        mgr.activate_version(
            staged_csv_path=sample_v2,
            sha256_hash=calculate_sha256(sample_v2),
            row_count=6,
            remote_location="loc2",
            custom_version_id="v1.0.0",
        )

    assert "Historical versions are strictly immutable" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 2. Path Traversal & Security Tests
# -----------------------------------------------------------------------------

def test_path_traversal_in_version_id_rejected():
    with pytest.raises(ValueError) as exc1:
        sanitize_version_id("../../etc/passwd")
    assert "Invalid version identifier" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        sanitize_version_id("..\\..\\windows\\system32")
    assert "Invalid version identifier" in str(exc2.value)

    # Safe version IDs
    assert sanitize_version_id("v1.0.0") == "v1.0.0"
    assert sanitize_version_id("release-2026_10.1") == "release-2026_10.1"


def test_corrupted_historical_version_rejects_rollback(audit_cache_env):
    """
    If a historical version file is corrupted on disk, rollback must detect
    the SHA-256 mismatch, abort, and preserve the active dataset.
    """
    mgr = ManifestManager("ddi")
    sample_v1 = FIXTURES_DIR / "ddi_sample_valid.csv"
    sample_v2 = FIXTURES_DIR / "ddi_sample_v2.csv"

    mgr.activate_version(
        staged_csv_path=sample_v1,
        sha256_hash=calculate_sha256(sample_v1),
        row_count=6,
        remote_location="loc1",
        custom_version_id="v1.0.0",
    )

    mgr.activate_version(
        staged_csv_path=sample_v2,
        sha256_hash=calculate_sha256(sample_v2),
        row_count=6,
        remote_location="loc2",
        custom_version_id="v2.0.0",
    )

    # Corrupt historical version v1.0.0
    manifest = mgr.load_manifest()
    v1_file = mgr.dataset_cache_dir / manifest.versions["v1.0.0"].file_relative_path
    with open(v1_file, "w", encoding="utf-8") as f:
        f.write("tampered content")

    # Attempt rollback to corrupted v1.0.0
    with pytest.raises(ValueError) as exc_info:
        mgr.rollback("v1.0.0")

    assert "Historical version file 'v1.0.0' is corrupted" in str(exc_info.value)
    # Active file must remain v2.0.0
    assert calculate_sha256(mgr.get_active_file_path()) == calculate_sha256(sample_v2)


# -----------------------------------------------------------------------------
# 3. Transport & Download Security Tests
# -----------------------------------------------------------------------------

def test_html_200_response_rejected():
    """
    Tests that a remote server returning an HTML login or error page with HTTP 200
    is rejected before schema validation.
    """
    fetcher = DatasetFetcher()
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch("ddi", "https://example.com/modawem_ddi.csv")

        assert "Remote endpoint returned HTML" in str(exc_info.value)


def test_truncated_download_content_length_mismatch():
    """
    Tests that a download receiving fewer bytes than Content-Length raises ConnectionError.
    """
    fetcher = DatasetFetcher()
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/csv", "Content-Length": "10000"}
    mock_resp.iter_content.return_value = [b"short truncated payload of 30 bytes"]
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch("ddi", "https://example.com/truncated.csv")

        assert "Incomplete download" in str(exc_info.value)


def test_oversized_download_rejected():
    """
    Tests that downloads exceeding max_bytes are aborted immediately.
    """
    fetcher = DatasetFetcher(max_bytes=100)
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/csv"}
    mock_resp.iter_content.return_value = [b"A" * 60, b"B" * 60]  # Total 120 bytes > 100
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch("ddi", "https://example.com/huge.csv")

        assert "Download exceeded maximum permitted size limit" in str(exc_info.value)


def test_credential_scrubbing_in_reports(audit_cache_env):
    """
    Verifies that tokens or signatures in URLs are scrubbed before writing reports.
    """
    sensitive_url = "https://user:password@storage.example.com/modawem_ddi.csv?token=SECRET_AUTH_KEY&signature=SIG123"
    sanitized = sanitize_url_for_logging(sensitive_url)

    assert "SECRET_AUTH_KEY" not in sanitized
    assert "SIG123" not in sanitized
    assert "password" not in sanitized
    assert sanitized == "https://storage.example.com/modawem_ddi.csv"

    # Check diff report does not contain secrets
    differ = DatasetDiffer("ddi")
    candidate = FIXTURES_DIR / "ddi_sample_valid.csv"
    report = differ.generate_diff(candidate_path=candidate, baseline_path=None)
    json_path, md_path = differ.save_reports(report)

    with open(json_path, "r", encoding="utf-8") as f:
        json_content = f.read()
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    assert "SECRET_AUTH_KEY" not in json_content
    assert "SECRET_AUTH_KEY" not in md_content


# -----------------------------------------------------------------------------
# 4. Schema Integrity & Concurrency Tests
# -----------------------------------------------------------------------------

def test_invalid_source_url_rejected_by_validator(tmp_path):
    validator = DatasetValidator("ddi")
    test_file = tmp_path / "bad_url.csv"
    valid_file = FIXTURES_DIR / "ddi_sample_valid.csv"

    with open(valid_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace https://example.com/syn/101 with an invalid non-URL string
    modified = content.replace("https://example.com/syn/101", "not_a_valid_url")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(modified)

    result = validator.validate_file(test_file)
    assert result.is_valid is False
    assert any(e.error_type == "invalid_url_format" for e in result.errors)


def test_inter_process_locking(audit_cache_env):
    """
    Tests that concurrent lock acquisition attempts respect timeout.
    """
    lock_file = audit_cache_env["cache"] / ".test.lock"
    lock1 = DatasetLock(lock_file, timeout_seconds=0.2)
    lock2 = DatasetLock(lock_file, timeout_seconds=0.2)

    with lock1:
        with pytest.raises(TimeoutError) as exc_info:
            with lock2:
                pass
        assert "Could not acquire lock" in str(exc_info.value)

    # After lock1 exits, lock2 should acquire successfully
    with lock2:
        assert lock2.acquired is True


def test_lock_token_ownership_safe_release(audit_cache_env):
    """
    Verifies that a process cannot release or delete another process's lockfile.
    """
    lock_file = audit_cache_env["cache"] / ".ownership.lock"
    lockA = DatasetLock(lock_file, timeout_seconds=1.0)
    lockB = DatasetLock(lock_file, timeout_seconds=0.1)

    with lockA:
        assert lock_file.exists()
        # Attempt to release using instance B (which did not acquire it)
        lockB._release()
        # Lockfile must still exist because lockB does not own the token
        assert lock_file.exists()

    # Now lockA has exited, lockfile should be cleanly unlinked
    assert not lock_file.exists()


def test_redirect_token_leakage_rejected(monkeypatch):
    """
    Verifies that redirects to another host with Bearer token are rejected.
    """
    monkeypatch.setenv("MODAWEM_REMOTE_AUTH_TOKEN", "super_secret_token")
    fetcher = DatasetFetcher()

    mock_resp = MagicMock()
    mock_resp.url = "https://untrusted-external-domain.com/data.csv"
    mock_history_item = MagicMock()
    mock_history_item.url = "https://internal.modawem.internal/data.csv"
    mock_resp.history = [mock_history_item]
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch("ddi", "https://internal.modawem.internal/data.csv")

        assert "Cross-domain redirect" in str(exc_info.value)


def test_empty_http_response_rejected():
    """
    Verifies that HTTP 200 with 0 bytes downloaded is explicitly rejected.
    """
    fetcher = DatasetFetcher()
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/csv"}
    mock_resp.iter_content.return_value = []  # 0 bytes
    mock_resp.raise_for_status.return_value = None
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            fetcher.fetch("ddi", "https://example.com/empty.csv")

        assert "empty dataset payload (0 bytes)" in str(exc_info.value)


def test_clinical_approval_gate_cannot_be_bypassed(audit_cache_env):
    """
    Verifies that technical validation does NOT mark records as clinically approved,
    and active versions in manifest are strictly marked as technically_validated.
    """
    mgr = ManifestManager("ddi")
    sample_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    valid_hash = calculate_sha256(sample_file)

    rec = mgr.activate_version(
        staged_csv_path=sample_file,
        sha256_hash=valid_hash,
        row_count=6,
        remote_location="https://example.com/sample.csv",
        custom_version_id="v1.0.0",
    )

    assert rec.validation_status == "technically_validated"
    assert rec.validation_status != "clinically_approved"

    manifest = mgr.load_manifest()
    assert manifest.versions["v1.0.0"].validation_status == "technically_validated"

