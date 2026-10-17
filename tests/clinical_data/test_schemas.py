"""
Tests for Modawem machine-readable JSON schemas (DDI and Allergy).
"""

import json
from pathlib import Path
import pytest

from clinical_data.config import get_schema_path
from clinical_data.validator import (
    DDI_REQUIRED_COLUMNS,
    ALLERGY_REQUIRED_COLUMNS,
    ALLOWED_ALLERGY_RELATIONSHIP_TYPES,
    ALLOWED_VALIDATION_STATUSES,
)


def test_ddi_schema_structure():
    schema_path = get_schema_path("ddi")
    assert schema_path.exists(), f"Schema file missing at {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    assert schema.get("title") == "ModawemDrugDrugInteractionRecord"
    assert schema.get("version") == "1.0.0"
    assert schema.get("type") == "object"

    required_fields = schema.get("required", [])
    assert len(required_fields) == 19
    assert required_fields == DDI_REQUIRED_COLUMNS

    ordered_columns = schema.get("ordered_columns", [])
    assert ordered_columns == DDI_REQUIRED_COLUMNS

    # Ensure validation_status enum matches allowed statuses
    val_status_prop = schema["properties"]["validation_status"]
    assert set(val_status_prop["enum"]) == ALLOWED_VALIDATION_STATUSES


def test_allergy_schema_structure():
    schema_path = get_schema_path("allergy")
    assert schema_path.exists(), f"Schema file missing at {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    assert schema.get("title") == "ModawemDrugAllergenRelationshipRecord"
    assert schema.get("version") == "1.0.0"
    assert schema.get("type") == "object"

    required_fields = schema.get("required", [])
    assert len(required_fields) == 16
    assert required_fields == ALLERGY_REQUIRED_COLUMNS

    ordered_columns = schema.get("ordered_columns", [])
    assert ordered_columns == ALLERGY_REQUIRED_COLUMNS

    # Strict check on relationship_type enum
    rel_type_prop = schema["properties"]["relationship_type"]
    assert set(rel_type_prop["enum"]) == ALLOWED_ALLERGY_RELATIONSHIP_TYPES
    assert set(rel_type_prop["enum"]) == {
        "class_membership",
        "documented_cross_reactivity",
        "precaution",
        "uncertain_mapping",
    }
