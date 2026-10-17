"""
Tests for ManifestManager version manifest, atomic activation, and rollback.
"""

from pathlib import Path
import pytest

from clinical_data.manifest import ManifestManager
from clinical_data.fetcher import calculate_sha256

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def isolated_cache_dir(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache" / "clinical_data"
    cache_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MODAWEM_DATA_CACHE_DIR", str(cache_path))
    return cache_path


def test_initial_manifest_state(isolated_cache_dir):
    mgr = ManifestManager("ddi")
    manifest = mgr.load_manifest()

    assert manifest.dataset_name == "ddi"
    assert manifest.active_version is None
    assert len(manifest.versions) == 0
    assert mgr.get_active_file_path() is None


def test_atomic_activation(isolated_cache_dir):
    mgr = ManifestManager("ddi")
    sample_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    sample_hash = calculate_sha256(sample_file)

    rec = mgr.activate_version(
        staged_csv_path=sample_file,
        sha256_hash=sample_hash,
        row_count=6,
        remote_location="https://example.com/ddi_v1.csv",
        custom_version_id="v1.0.0",
    )

    assert rec.version_id == "v1.0.0"
    assert rec.sha256_hash == sample_hash
    assert rec.row_count == 6

    # Verify active CSV exists and matches content
    active_path = mgr.get_active_file_path()
    assert active_path is not None
    assert active_path.exists()
    assert calculate_sha256(active_path) == sample_hash

    # Verify manifest.json on disk
    manifest = mgr.load_manifest()
    assert manifest.active_version == "v1.0.0"
    assert "v1.0.0" in manifest.versions
    assert len(manifest.history) == 1
    assert manifest.history[0].action == "refresh"

    # Verify idempotency check
    assert mgr.is_same_as_active(sample_hash) is True
    assert mgr.is_same_as_active("another_random_hash_value") is False


def test_multiple_activations_and_rollback(isolated_cache_dir):
    mgr = ManifestManager("ddi")
    sample_v1 = FIXTURES_DIR / "ddi_sample_valid.csv"
    sample_v2 = FIXTURES_DIR / "ddi_sample_v2.csv"

    hash_v1 = calculate_sha256(sample_v1)
    hash_v2 = calculate_sha256(sample_v2)

    # 1. Activate v1
    mgr.activate_version(
        staged_csv_path=sample_v1,
        sha256_hash=hash_v1,
        row_count=6,
        remote_location="loc1",
        custom_version_id="v1.0.0",
    )

    # 2. Activate v2
    mgr.activate_version(
        staged_csv_path=sample_v2,
        sha256_hash=hash_v2,
        row_count=6,
        remote_location="loc2",
        custom_version_id="v2.0.0",
    )

    manifest = mgr.load_manifest()
    assert manifest.active_version == "v2.0.0"
    assert calculate_sha256(mgr.get_active_file_path()) == hash_v2
    assert len(manifest.versions) == 2

    # 3. Rollback to v1
    rolled_back_rec = mgr.rollback("v1.0.0")
    assert rolled_back_rec.version_id == "v1.0.0"

    # Verify active file content now matches v1
    assert calculate_sha256(mgr.get_active_file_path()) == hash_v1

    # Verify manifest reflects rollback without deleting history
    manifest_after = mgr.load_manifest()
    assert manifest_after.active_version == "v1.0.0"
    assert len(manifest_after.versions) == 2  # v1 and v2 both retained!
    assert len(manifest_after.history) == 3
    assert manifest_after.history[-1].action == "rollback"
    assert manifest_after.history[-1].version_id == "v1.0.0"


def test_invalid_rollback_target_rejected(isolated_cache_dir):
    mgr = ManifestManager("allergy")
    sample = FIXTURES_DIR / "allergy_sample_valid.csv"

    mgr.activate_version(
        staged_csv_path=sample,
        sha256_hash=calculate_sha256(sample),
        row_count=6,
        remote_location="loc",
        custom_version_id="v1.0.0",
    )

    with pytest.raises(ValueError) as exc:
        mgr.rollback("v99.99.99")

    assert "not found in manifest" in str(exc.value)
