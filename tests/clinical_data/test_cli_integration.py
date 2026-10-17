"""
End-to-End CLI Integration Tests for modawem-dataset.
"""

from pathlib import Path
import pytest

from clinical_data.cli import main, build_parser
from clinical_data.manifest import ManifestManager
from clinical_data.fetcher import calculate_sha256

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def cli_test_env(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache" / "clinical_data"
    reports_dir = tmp_path / "reports" / "refresh-reports"
    cache_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("MODAWEM_DATA_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("MODAWEM_REPORTS_DIR", str(reports_dir))
    monkeypatch.setenv("MODAWEM_DDI_DATA_LOCATION", str(FIXTURES_DIR / "ddi_sample_valid.csv"))
    monkeypatch.setenv("MODAWEM_ALLERGY_DATA_LOCATION", str(FIXTURES_DIR / "allergy_sample_valid.csv"))

    return {
        "cache_dir": cache_dir,
        "reports_dir": reports_dir,
    }


def test_cli_validate_success(capsys):
    parser = build_parser()
    valid_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    args = parser.parse_args(["validate", "--dataset", "ddi", "--file", str(valid_file)])

    exit_code = args.func(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[+] VALID" in captured.out


def test_cli_validate_failure(capsys):
    parser = build_parser()
    invalid_file = FIXTURES_DIR / "allergy_sample_invalid_enum.csv"
    args = parser.parse_args(["validate", "--dataset", "allergy", "--file", str(invalid_file)])

    exit_code = args.func(args)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[-] INVALID" in captured.out


def test_cli_refresh_and_idempotency(cli_test_env, capsys):
    parser = build_parser()

    # 1. First refresh (clean activation)
    args_refresh_1 = parser.parse_args(["refresh", "--dataset", "ddi"])
    code_1 = args_refresh_1.func(args_refresh_1)
    assert code_1 == 0
    cap_1 = capsys.readouterr()
    assert "Refresh Successful!" in cap_1.out

    mgr = ManifestManager("ddi")
    manifest = mgr.load_manifest()
    assert manifest.active_version is not None
    active_v1 = manifest.active_version

    # 2. Second refresh with same file (Idempotent: should NOT activate new version)
    args_refresh_2 = parser.parse_args(["refresh", "--dataset", "ddi"])
    code_2 = args_refresh_2.func(args_refresh_2)
    assert code_2 == 0
    cap_2 = capsys.readouterr()
    assert "Idempotent check passed" in cap_2.out

    manifest_2 = mgr.load_manifest()
    assert manifest_2.active_version == active_v1
    assert len(manifest_2.versions) == 1  # No duplicate version created!


def test_cli_refresh_fault_tolerance(cli_test_env, capsys):
    parser = build_parser()

    # 1. Establish valid active version first
    args_init = parser.parse_args(["refresh", "--dataset", "ddi"])
    assert args_init.func(args_init) == 0
    capsys.readouterr()

    mgr = ManifestManager("ddi")
    active_path = mgr.get_active_file_path()
    assert active_path is not None
    initial_hash = calculate_sha256(active_path)

    # 2. Attempt refresh with invalid schema file
    invalid_file = FIXTURES_DIR / "ddi_sample_invalid_schema.csv"
    args_bad = parser.parse_args(["refresh", "--dataset", "ddi", "--location", str(invalid_file)])
    bad_code = args_bad.func(args_bad)
    assert bad_code == 1
    cap_bad = capsys.readouterr()
    assert "Validation failed for candidate. Aborting refresh; active version was NOT modified." in cap_bad.err

    # 3. Assert active version was preserved and intact!
    assert calculate_sha256(mgr.get_active_file_path()) == initial_hash


def test_cli_status_and_rollback(cli_test_env, capsys):
    parser = build_parser()

    # Ingest v1
    v1_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    args_v1 = parser.parse_args(["refresh", "--dataset", "ddi", "--location", str(v1_file), "--version-id", "v1.0.0"])
    assert args_v1.func(args_v1) == 0
    capsys.readouterr()

    # Ingest v2
    v2_file = FIXTURES_DIR / "ddi_sample_v2.csv"
    args_v2 = parser.parse_args(["refresh", "--dataset", "ddi", "--location", str(v2_file), "--version-id", "v2.0.0"])
    assert args_v2.func(args_v2) == 0
    capsys.readouterr()

    # Status check
    args_stat = parser.parse_args(["status", "--dataset", "ddi"])
    assert args_stat.func(args_stat) == 0
    stat_out = capsys.readouterr().out
    assert "Active Version:    v2.0.0" in stat_out
    assert "Total Versions:    2" in stat_out

    # Rollback to v1.0.0
    args_rb = parser.parse_args(["rollback", "--dataset", "ddi", "--target-version", "v1.0.0"])
    assert args_rb.func(args_rb) == 0
    rb_out = capsys.readouterr().out
    assert "Rollback Successful! Active version is now: v1.0.0" in rb_out

    mgr = ManifestManager("ddi")
    assert calculate_sha256(mgr.get_active_file_path()) == calculate_sha256(v1_file)
