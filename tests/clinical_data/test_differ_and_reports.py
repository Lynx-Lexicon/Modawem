"""
Tests for DatasetDiffer differential analysis and clinical review routing.
"""

from pathlib import Path
import json
import pytest

from clinical_data.differ import DatasetDiffer

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def isolated_reports_dir(tmp_path, monkeypatch):
    rep_path = tmp_path / "reports" / "refresh-reports"
    rep_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MODAWEM_REPORTS_DIR", str(rep_path))
    return rep_path


def test_ddi_initial_diff_report(isolated_reports_dir):
    differ = DatasetDiffer("ddi")
    candidate = FIXTURES_DIR / "ddi_sample_valid.csv"

    report = differ.generate_diff(candidate_path=candidate, baseline_path=None)

    assert report.dataset == "ddi"
    assert report.baseline_record_count == 0
    assert report.candidate_record_count == 6
    assert report.added_count == 6
    assert report.removed_count == 0
    assert report.modified_count == 0

    # In ddi_sample_valid, SYN-DDI-001 and SYN-DDI-002 have conflicting severities (Major vs Severe)
    # in the same interaction group (GRP-RxNorm-SYN01-RxNorm-SYN02), and SYN-DDI-002 has needs_clinical_review
    assert report.clinical_review_required is True
    assert report.clinical_review_count > 0


def test_ddi_differential_v1_to_v2(isolated_reports_dir):
    differ = DatasetDiffer("ddi")
    base_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    cand_file = FIXTURES_DIR / "ddi_sample_v2.csv"

    report = differ.generate_diff(
        candidate_path=cand_file,
        baseline_path=base_file,
        baseline_version_id="v1.0.0",
    )

    assert report.baseline_record_count == 6
    assert report.candidate_record_count == 6

    # In v2: SYN-DDI-007 added, SYN-DDI-004 removed
    assert report.added_count == 1
    assert "SYN-DDI-007" in report.added_record_ids
    assert report.removed_count == 1
    assert "SYN-DDI-004" in report.removed_record_ids

    # In v2: SYN-DDI-001 (severity Major -> Contraindicated) and SYN-DDI-003 (guidance updated)
    assert report.modified_count == 2
    mod_ids = [m.record_id for m in report.modifications]
    assert "SYN-DDI-001" in mod_ids
    assert "SYN-DDI-003" in mod_ids

    # Field change counts
    assert report.field_change_counts.get("severity") == 1
    assert report.field_change_counts.get("management_guidance") == 2

    # Clinical Review Flags
    assert report.clinical_review_required is True
    flag_reasons = [f.flag_reason for f in report.clinical_review_flags]
    assert "severity_classification_changed" in flag_reasons
    assert "record_removed" in flag_reasons

    # Check that report files save properly
    json_path, md_path = differ.save_reports(report)
    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["dataset"] == "ddi"
    assert data["added_count"] == 1


def test_allergy_differential_v1_to_v2(isolated_reports_dir):
    differ = DatasetDiffer("allergy")
    base_file = FIXTURES_DIR / "allergy_sample_valid.csv"
    cand_file = FIXTURES_DIR / "allergy_sample_v2.csv"

    report = differ.generate_diff(
        candidate_path=cand_file,
        baseline_path=base_file,
        baseline_version_id="v1.0.0",
    )

    assert report.dataset == "allergy"
    # In v2: SYN-ALG-007 added, SYN-ALG-006 removed
    assert report.added_count == 1
    assert "SYN-ALG-007" in report.added_record_ids
    assert report.removed_count == 1
    assert "SYN-ALG-006" in report.removed_record_ids

    # SYN-ALG-003 modified (relationship_type precaution -> documented_cross_reactivity)
    mod_ids = [m.record_id for m in report.modifications]
    assert "SYN-ALG-003" in mod_ids
    assert report.field_change_counts.get("relationship_type") == 1

    # Check high priority flags
    high_flags = [f for f in report.clinical_review_flags if f.severity_level == "high"]
    high_reasons = [f.flag_reason for f in high_flags]
    assert "relationship_type_changed" in high_reasons
    assert "uncertain_allergy_mapping" in high_reasons
