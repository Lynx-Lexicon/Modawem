"""
Machine-readable validation engine for Modawem Clinical Datasets (DDI and Allergy).
Loads schema rules, column orders, and enums directly from schema.json to prevent drift.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from clinical_data.config import get_schema_path

ISO8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
)

# Fallback column specifications in case schema.json is temporarily unreachable
DEFAULT_DDI_COLUMNS = [
    "record_id",
    "interaction_group_id",
    "ingredient_a_name",
    "ingredient_a_id",
    "ingredient_a_id_system",
    "ingredient_b_name",
    "ingredient_b_id",
    "ingredient_b_id_system",
    "interaction_type",
    "severity",
    "clinical_effect",
    "management_guidance",
    "source_id",
    "source_record_id",
    "source_version",
    "source_url",
    "retrieved_at",
    "validation_status",
    "notes",
]

DEFAULT_ALLERGY_COLUMNS = [
    "record_id",
    "allergen_name",
    "allergen_class",
    "ingredient_name",
    "ingredient_id",
    "ingredient_id_system",
    "relationship_type",
    "evidence_summary",
    "qualifiers",
    "source_id",
    "source_record_id",
    "source_version",
    "source_url",
    "retrieved_at",
    "validation_status",
    "notes",
]

DEFAULT_VALIDATION_STATUSES = {
    "unvalidated",
    "technically_validated",
    "needs_clinical_review",
    "clinically_approved",
}

DEFAULT_ALLERGY_RELATIONSHIPS = {
    "class_membership",
    "documented_cross_reactivity",
    "precaution",
    "uncertain_mapping",
}

# Backward compatibility aliases
DDI_REQUIRED_COLUMNS = DEFAULT_DDI_COLUMNS
ALLERGY_REQUIRED_COLUMNS = DEFAULT_ALLERGY_COLUMNS
ALLOWED_VALIDATION_STATUSES = DEFAULT_VALIDATION_STATUSES
ALLOWED_ALLERGY_RELATIONSHIP_TYPES = DEFAULT_ALLERGY_RELATIONSHIPS

DDI_NULLABLE_FIELDS = {"management_guidance", "source_url", "notes"}
ALLERGY_NULLABLE_FIELDS = {"qualifiers", "source_url", "notes"}


def is_valid_url(url_str: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url_str)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


@dataclass
class ValidationError:
    dataset: str
    row_number: Optional[int]
    field: Optional[str]
    error_type: str
    message: str

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "dataset": self.dataset,
            "row_number": str(self.row_number) if self.row_number is not None else None,
            "field": self.field,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    dataset: str
    is_valid: bool
    row_count: int
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = "1.0.0"

    def to_dict(self) -> Dict:
        return {
            "dataset": self.dataset,
            "is_valid": self.is_valid,
            "row_count": self.row_count,
            "schema_version": self.schema_version,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }


class DatasetValidator:
    """
    Validates CSV files against the strict Modawem dataset schema and clinical rules.
    Synchronizes directly with schema.json to ensure zero drift between specification and validation.
    """

    def __init__(self, dataset: str):
        self.dataset = "ddi" if dataset.lower().strip() in ("ddi", "drug_drug_interaction") else "allergy"
        self.nullable_fields = (
            DDI_NULLABLE_FIELDS if self.dataset == "ddi" else ALLERGY_NULLABLE_FIELDS
        )
        self.schema_metadata = self._load_schema()

        # Extract rules dynamically from schema.json
        self.expected_columns = (
            self.schema_metadata.get("ordered_columns")
            or self.schema_metadata.get("required")
            or (DEFAULT_DDI_COLUMNS if self.dataset == "ddi" else DEFAULT_ALLERGY_COLUMNS)
        )

        props = self.schema_metadata.get("properties", {})
        val_status_prop = props.get("validation_status", {})
        self.allowed_validation_statuses = (
            set(val_status_prop.get("enum", [])) or DEFAULT_VALIDATION_STATUSES
        )

        if self.dataset == "allergy":
            rel_prop = props.get("relationship_type", {})
            self.allowed_relationship_types = (
                set(rel_prop.get("enum", [])) or DEFAULT_ALLERGY_RELATIONSHIPS
            )
        else:
            self.allowed_relationship_types = set()

    def _load_schema(self) -> Dict:
        try:
            schema_file = get_schema_path(self.dataset)
            with open(schema_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "version": "1.0.0",
                "ordered_columns": DEFAULT_DDI_COLUMNS if self.dataset == "ddi" else DEFAULT_ALLERGY_COLUMNS,
            }

    def validate_file(self, file_path: Path | str) -> ValidationResult:
        path = Path(file_path).resolve()
        errors: List[ValidationError] = []
        warnings: List[str] = []

        if not path.exists():
            return ValidationResult(
                dataset=self.dataset,
                is_valid=False,
                row_count=0,
                errors=[
                    ValidationError(
                        dataset=self.dataset,
                        row_number=None,
                        field=None,
                        error_type="file_not_found",
                        message=f"Dataset file does not exist: {path}",
                    )
                ],
                schema_version=self.schema_metadata.get("version", "1.0.0"),
            )

        if path.stat().st_size == 0:
            return ValidationResult(
                dataset=self.dataset,
                is_valid=False,
                row_count=0,
                errors=[
                    ValidationError(
                        dataset=self.dataset,
                        row_number=None,
                        field=None,
                        error_type="empty_file",
                        message=f"Dataset file is empty (0 bytes): {path}",
                    )
                ],
                schema_version=self.schema_metadata.get("version", "1.0.0"),
            )

        seen_record_ids: Set[str] = set()
        row_count = 0

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    return ValidationResult(
                        dataset=self.dataset,
                        is_valid=False,
                        row_count=0,
                        errors=[
                            ValidationError(
                                dataset=self.dataset,
                                row_number=1,
                                field=None,
                                error_type="missing_header",
                                message="File contains no rows (missing CSV header).",
                            )
                        ],
                        schema_version=self.schema_metadata.get("version", "1.0.0"),
                    )

                # 1. Header validation: Column names and order
                header_errors = self._validate_header(header)
                errors.extend(header_errors)

                if any(e.error_type in ("missing_columns", "column_count_mismatch") for e in header_errors):
                    return ValidationResult(
                        dataset=self.dataset,
                        is_valid=False,
                        row_count=0,
                        errors=errors,
                        schema_version=self.schema_metadata.get("version", "1.0.0"),
                    )

                col_idx = {col: i for i, col in enumerate(header)}

                # 2. Row by row validation
                for line_num, row in enumerate(reader, start=2):
                    row_count += 1
                    row_errors = self._validate_row(row, line_num, col_idx, seen_record_ids)
                    errors.extend(row_errors)

        except csv.Error as ce:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=None,
                    field=None,
                    error_type="csv_syntax_error",
                    message=f"CSV parsing error: {str(ce)}",
                )
            )
        except UnicodeDecodeError as ue:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=None,
                    field=None,
                    error_type="encoding_error",
                    message=f"File encoding error (UTF-8 required): {str(ue)}",
                )
            )

        if row_count == 0 and not errors:
            warnings.append("Dataset contains valid headers but zero data records.")

        is_valid = len(errors) == 0
        return ValidationResult(
            dataset=self.dataset,
            is_valid=is_valid,
            row_count=row_count,
            errors=errors,
            warnings=warnings,
            schema_version=self.schema_metadata.get("version", "1.0.0"),
        )

    def _validate_header(self, header: List[str]) -> List[ValidationError]:
        errors: List[ValidationError] = []
        cleaned_header = [c.strip() for c in header]

        missing = [c for c in self.expected_columns if c not in cleaned_header]
        if missing:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=1,
                    field=None,
                    error_type="missing_columns",
                    message=f"Missing required columns: {', '.join(missing)}",
                )
            )

        unexpected = [c for c in cleaned_header if c not in self.expected_columns]
        if unexpected:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=1,
                    field=None,
                    error_type="unexpected_columns",
                    message=f"Unexpected extra columns detected: {', '.join(unexpected)}",
                )
            )

        if len(cleaned_header) == len(self.expected_columns):
            for idx, (exp, actual) in enumerate(zip(self.expected_columns, cleaned_header)):
                if exp != actual:
                    errors.append(
                        ValidationError(
                            dataset=self.dataset,
                            row_number=1,
                            field=actual,
                            error_type="column_order_mismatch",
                            message=f"Column at position {idx + 1} should be '{exp}', found '{actual}'",
                        )
                    )
                    break

        return errors

    def _validate_row(
        self,
        row: List[str],
        line_num: int,
        col_idx: Dict[str, int],
        seen_record_ids: Set[str],
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if len(row) != len(self.expected_columns):
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field=None,
                    error_type="field_count_mismatch",
                    message=f"Row has {len(row)} values, expected {len(self.expected_columns)}",
                )
            )
            return errors

        record_id = row[col_idx["record_id"]].strip()
        if not record_id:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field="record_id",
                    error_type="missing_required_value",
                    message="record_id is empty or blank.",
                )
            )
        elif record_id in seen_record_ids:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field="record_id",
                    error_type="duplicate_record_id",
                    message=f"Duplicate record_id '{record_id}' detected.",
                )
            )
        else:
            seen_record_ids.add(record_id)

        # Check required fields
        for col_name in self.expected_columns:
            val = row[col_idx[col_name]].strip()
            if col_name not in self.nullable_fields and not val:
                errors.append(
                    ValidationError(
                        dataset=self.dataset,
                        row_number=line_num,
                        field=col_name,
                        error_type="missing_required_value",
                        message=f"Required column '{col_name}' cannot be empty.",
                    )
                )

        # Check validation_status enum
        validation_status = row[col_idx["validation_status"]].strip()
        if validation_status and validation_status not in self.allowed_validation_statuses:
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field="validation_status",
                    error_type="invalid_enum_value",
                    message=(
                        f"Invalid validation_status '{validation_status}'. "
                        f"Must be one of: {', '.join(sorted(self.allowed_validation_statuses))}"
                    ),
                )
            )

        # Check retrieved_at ISO 8601 timestamp
        retrieved_at = row[col_idx["retrieved_at"]].strip()
        if retrieved_at and not ISO8601_PATTERN.match(retrieved_at):
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field="retrieved_at",
                    error_type="invalid_timestamp_format",
                    message=(
                        f"Invalid timestamp '{retrieved_at}' in retrieved_at. "
                        "Must match ISO 8601 format (e.g. YYYY-MM-DDTHH:MM:SSZ)."
                    ),
                )
            )

        # Check source_url if provided
        source_url = row[col_idx["source_url"]].strip()
        if source_url and not is_valid_url(source_url):
            errors.append(
                ValidationError(
                    dataset=self.dataset,
                    row_number=line_num,
                    field="source_url",
                    error_type="invalid_url_format",
                    message=f"Invalid URL format in source_url: '{source_url}' (must be http:// or https://)",
                )
            )

        # Dataset specific checks
        if self.dataset == "allergy":
            rel_type = row[col_idx["relationship_type"]].strip()
            if rel_type and rel_type not in self.allowed_relationship_types:
                errors.append(
                    ValidationError(
                        dataset=self.dataset,
                        row_number=line_num,
                        field="relationship_type",
                        error_type="invalid_relationship_type",
                        message=(
                            f"Invalid relationship_type '{rel_type}'. "
                            f"Must be one of: {', '.join(sorted(self.allowed_relationship_types))}"
                        ),
                    )
                )

            # Cross-field constraint: uncertain_mapping cannot be clinically_approved
            if rel_type == "uncertain_mapping" and validation_status == "clinically_approved":
                errors.append(
                    ValidationError(
                        dataset=self.dataset,
                        row_number=line_num,
                        field="validation_status",
                        error_type="cross_field_conflict",
                        message="Record with relationship_type 'uncertain_mapping' cannot have validation_status 'clinically_approved'.",
                    )
                )

        elif self.dataset == "ddi":
            severity = row[col_idx["severity"]].strip()
            if not severity:
                errors.append(
                    ValidationError(
                        dataset=self.dataset,
                        row_number=line_num,
                        field="severity",
                        error_type="missing_severity",
                        message="DDI severity is required and must preserve original source rating.",
                    )
                )

        return errors
