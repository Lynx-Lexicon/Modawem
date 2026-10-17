"""
Tests for DatasetValidator engine covering DDI and Allergy datasets.
"""

from pathlib import Path
import pytest

from clinical_data.validator import DatasetValidator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_ddi_valid_sample():
    validator = DatasetValidator("ddi")
    valid_file = FIXTURES_DIR / "ddi_sample_valid.csv"
    result = validator.validate_file(valid_file)

    assert result.is_valid is True, f"Expected valid, got errors: {result.errors}"
    assert result.row_count == 6
    assert len(result.errors) == 0


def test_ddi_invalid_schema_missing_columns():
    validator = DatasetValidator("ddi")
    invalid_file = FIXTURES_DIR / "ddi_sample_invalid_schema.csv"
    result = validator.validate_file(invalid_file)

    assert result.is_valid is False
    error_types = [e.error_type for e in result.errors]
    assert "missing_columns" in error_types or "column_order_mismatch" in error_types


def test_ddi_corrupted_file():
    validator = DatasetValidator("ddi")
    corrupt_file = FIXTURES_DIR / "ddi_sample_corrupted.csv"
    result = validator.validate_file(corrupt_file)

    assert result.is_valid is False
    assert len(result.errors) > 0


def test_allergy_valid_sample():
    validator = DatasetValidator("allergy")
    valid_file = FIXTURES_DIR / "allergy_sample_valid.csv"
    result = validator.validate_file(valid_file)

    assert result.is_valid is True, f"Expected valid, got errors: {result.errors}"
    assert result.row_count == 6
    assert len(result.errors) == 0


def test_allergy_invalid_enum_rejected():
    validator = DatasetValidator("allergy")
    invalid_file = FIXTURES_DIR / "allergy_sample_invalid_enum.csv"
    result = validator.validate_file(invalid_file)

    assert result.is_valid is False
    error_types = [e.error_type for e in result.errors]
    assert "invalid_relationship_type" in error_types


def test_duplicate_record_id_detection(tmp_path):
    validator = DatasetValidator("ddi")
    dup_file = tmp_path / "dup_ddi.csv"
    valid_file = FIXTURES_DIR / "ddi_sample_valid.csv"

    # Duplicate first data row
    with open(valid_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines.append(lines[1])  # Re-append row 1
    with open(dup_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    result = validator.validate_file(dup_file)
    assert result.is_valid is False
    error_types = [e.error_type for e in result.errors]
    assert "duplicate_record_id" in error_types


def test_empty_required_field_detection(tmp_path):
    validator = DatasetValidator("allergy")
    empty_field_file = tmp_path / "empty_allergen.csv"
    valid_file = FIXTURES_DIR / "allergy_sample_valid.csv"

    with open(valid_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Erase allergen_name from first data row
    modified = content.replace("SyntheticPenicillinCore", "", 1)
    with open(empty_field_file, "w", encoding="utf-8") as f:
        f.write(modified)

    result = validator.validate_file(empty_field_file)
    assert result.is_valid is False
    assert any(e.error_type == "missing_required_value" and e.field == "allergen_name" for e in result.errors)


def test_cross_field_uncertain_mapping_constraint(tmp_path):
    validator = DatasetValidator("allergy")
    test_file = tmp_path / "cross_field.csv"
    valid_file = FIXTURES_DIR / "allergy_sample_valid.csv"

    with open(valid_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Change row 6 (uncertain_mapping) validation_status to clinically_approved
    modified = content.replace("needs_clinical_review,Requires qualified clinical review", "clinically_approved,Illegal approval")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(modified)

    result = validator.validate_file(test_file)
    assert result.is_valid is False
    assert any(e.error_type == "cross_field_conflict" for e in result.errors)
