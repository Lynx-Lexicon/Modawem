"""
Differential Analysis and Clinical Review Routing Engine for Modawem Clinical Datasets.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from clinical_data.config import get_reports_dir
from clinical_data.fetcher import sanitize_url_for_logging


@dataclass
class FieldChange:
    field_name: str
    old_value: str
    new_value: str


@dataclass
class RecordModification:
    record_id: str
    changes: List[FieldChange]


@dataclass
class ClinicalReviewItem:
    record_id: str
    flag_reason: str
    details: str
    severity_level: str  # "high", "medium", "info"


@dataclass
class DiffReport:
    dataset: str
    generated_at: str
    baseline_version: Optional[str]
    candidate_file: str
    baseline_record_count: int
    candidate_record_count: int
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    clinical_review_required: bool
    clinical_review_count: int
    clinical_review_flags: List[ClinicalReviewItem] = field(default_factory=list)
    field_change_counts: Dict[str, int] = field(default_factory=dict)
    added_record_ids: List[str] = field(default_factory=list)
    removed_record_ids: List[str] = field(default_factory=list)
    modifications: List[RecordModification] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_markdown(self) -> str:
        lines = [
            f"# Clinical Dataset Refresh Diff Report: {self.dataset.upper()}",
            f"**Generated At (UTC):** {self.generated_at}",
            f"**Baseline Version:** {self.baseline_version or 'Initial Ingestion (None)'}",
            f"**Candidate Source:** `{Path(self.candidate_file).name}`",
            "",
            "## 1. Summary Statistics",
            f"- **Baseline Records:** {self.baseline_record_count}",
            f"- **Candidate Records:** {self.candidate_record_count}",
            f"- **Added Records:** {self.added_count}",
            f"- **Removed Records:** {self.removed_count}",
            f"- **Modified Records:** {self.modified_count}",
            f"- **Unchanged Records:** {self.unchanged_count}",
            "",
            "## 2. Clinical Review Gating",
            f"- **Clinical Review Required:** {'YES (ACTION REQUIRED)' if self.clinical_review_required else 'NO'}",
            f"- **Total Flagged Items:** {self.clinical_review_count}",
            "",
        ]

        if self.clinical_review_flags:
            lines.append("### Flagged Clinical Items for Qualified Review:")
            lines.append("| Record ID | Priority | Flag Reason | Details |")
            lines.append("|---|---|---|---|")
            for flag in self.clinical_review_flags[:50]:  # Cap at 50 in table preview
                lines.append(
                    f"| `{flag.record_id}` | **{flag.severity_level.upper()}** | {flag.flag_reason} | {flag.details} |"
                )
            if len(self.clinical_review_flags) > 50:
                lines.append(f"\n*(Truncated: {len(self.clinical_review_flags) - 50} additional flagged items in JSON)*")
            lines.append("")

        if self.field_change_counts:
            lines.append("## 3. Field Modification Counts")
            lines.append("| Field Name | Total Changed Records |")
            lines.append("|---|---|")
            for k, v in sorted(self.field_change_counts.items(), key=lambda x: -x[1]):
                lines.append(f"| `{k}` | {v} |")
            lines.append("")

        return "\n".join(lines)


class DatasetDiffer:
    """
    Compares two versions of a dataset and extracts differential statistics
    and clinical review routing flags.
    """

    def __init__(self, dataset: str):
        self.dataset = "ddi" if dataset.lower().strip() in ("ddi", "drug_drug_interaction") else "allergy"

    def _read_records(self, csv_path: Path) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
        """
        Reads CSV and returns a dictionary mapping record_id to full row dictionary,
        along with the ordered list of headers.
        """
        records: Dict[str, Dict[str, str]] = {}
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for row in reader:
                rec_id = row.get("record_id", "").strip()
                if rec_id:
                    records[rec_id] = {k: (v.strip() if v is not None else "") for k, v in row.items()}
        return records, headers

    def generate_diff(
        self,
        candidate_path: Path,
        baseline_path: Optional[Path] = None,
        baseline_version_id: Optional[str] = None,
    ) -> DiffReport:
        now_utc = datetime.now(timezone.utc).isoformat()
        candidate_records, headers = self._read_records(candidate_path)

        if not baseline_path or not baseline_path.exists():
            # Initial ingestion without prior baseline
            return self._build_initial_report(
                candidate_path=candidate_path,
                candidate_records=candidate_records,
                now_utc=now_utc,
            )

        baseline_records, _ = self._read_records(baseline_path)

        base_ids = set(baseline_records.keys())
        cand_ids = set(candidate_records.keys())

        added_ids = sorted(cand_ids - base_ids)
        removed_ids = sorted(base_ids - cand_ids)
        common_ids = sorted(base_ids & cand_ids)

        modifications: List[RecordModification] = []
        field_change_counts: Dict[str, int] = {}
        clinical_flags: List[ClinicalReviewItem] = []
        unchanged_count = 0

        # Check modifications in common records
        for rec_id in common_ids:
            base_row = baseline_records[rec_id]
            cand_row = candidate_records[rec_id]
            changes: List[FieldChange] = []

            for h in headers:
                old_val = base_row.get(h, "")
                new_val = cand_row.get(h, "")
                if old_val != new_val:
                    changes.append(FieldChange(field_name=h, old_value=old_val, new_value=new_val))
                    field_change_counts[h] = field_change_counts.get(h, 0) + 1

            if changes:
                modifications.append(RecordModification(record_id=rec_id, changes=changes))
                self._check_clinical_flags_for_modification(rec_id, changes, cand_row, clinical_flags)
            else:
                unchanged_count += 1

        # Check newly added records for clinical flags
        for rec_id in added_ids:
            cand_row = candidate_records[rec_id]
            self._check_clinical_flags_for_added(rec_id, cand_row, clinical_flags)

        # Check removed records
        for rec_id in removed_ids:
            clinical_flags.append(
                ClinicalReviewItem(
                    record_id=rec_id,
                    flag_reason="record_removed",
                    details=f"Record '{rec_id}' was present in baseline but removed in candidate.",
                    severity_level="medium",
                )
            )

        # Multi-source conflict detection on the candidate dataset
        self._check_group_conflicts(candidate_records, clinical_flags)

        report = DiffReport(
            dataset=self.dataset,
            generated_at=now_utc,
            baseline_version=baseline_version_id,
            candidate_file=sanitize_url_for_logging(Path(candidate_path).name),
            baseline_record_count=len(baseline_records),
            candidate_record_count=len(candidate_records),
            added_count=len(added_ids),
            removed_count=len(removed_ids),
            modified_count=len(modifications),
            unchanged_count=unchanged_count,
            clinical_review_required=len(clinical_flags) > 0,
            clinical_review_count=len(clinical_flags),
            clinical_review_flags=clinical_flags,
            field_change_counts=field_change_counts,
            added_record_ids=added_ids,
            removed_record_ids=removed_ids,
            modifications=modifications,
        )
        return report

    def _build_initial_report(
        self,
        candidate_path: Path,
        candidate_records: Dict[str, Dict[str, str]],
        now_utc: str,
    ) -> DiffReport:
        added_ids = sorted(candidate_records.keys())
        clinical_flags: List[ClinicalReviewItem] = []

        for rec_id, row in candidate_records.items():
            self._check_clinical_flags_for_added(rec_id, row, clinical_flags)

        self._check_group_conflicts(candidate_records, clinical_flags)

        return DiffReport(
            dataset=self.dataset,
            generated_at=now_utc,
            baseline_version=None,
            candidate_file=sanitize_url_for_logging(Path(candidate_path).name),
            baseline_record_count=0,
            candidate_record_count=len(candidate_records),
            added_count=len(added_ids),
            removed_count=0,
            modified_count=0,
            unchanged_count=0,
            clinical_review_required=len(clinical_flags) > 0,
            clinical_review_count=len(clinical_flags),
            clinical_review_flags=clinical_flags,
            field_change_counts={},
            added_record_ids=added_ids,
            removed_record_ids=[],
            modifications=[],
        )

    def _check_clinical_flags_for_modification(
        self,
        record_id: str,
        changes: List[FieldChange],
        new_row: Dict[str, str],
        flags: List[ClinicalReviewItem],
    ):
        for ch in changes:
            if ch.field_name == "severity":
                flags.append(
                    ClinicalReviewItem(
                        record_id=record_id,
                        flag_reason="severity_classification_changed",
                        details=f"Severity shifted from '{ch.old_value}' to '{ch.new_value}'",
                        severity_level="high",
                    )
                )
            elif ch.field_name == "relationship_type":
                flags.append(
                    ClinicalReviewItem(
                        record_id=record_id,
                        flag_reason="relationship_type_changed",
                        details=f"Allergy relationship changed from '{ch.old_value}' to '{ch.new_value}'",
                        severity_level="high",
                    )
                )
            elif "ingredient" in ch.field_name and ("id" in ch.field_name or "name" in ch.field_name):
                flags.append(
                    ClinicalReviewItem(
                        record_id=record_id,
                        flag_reason="ingredient_identity_modified",
                        details=f"Ingredient field '{ch.field_name}' changed from '{ch.old_value}' to '{ch.new_value}'",
                        severity_level="high",
                    )
                )

        if new_row.get("validation_status") == "needs_clinical_review":
            flags.append(
                ClinicalReviewItem(
                    record_id=record_id,
                    flag_reason="status_flagged_for_review",
                    details=f"Record validation_status set to 'needs_clinical_review': {new_row.get('notes', '')}",
                    severity_level="medium",
                )
            )

    def _check_clinical_flags_for_added(
        self,
        record_id: str,
        row: Dict[str, str],
        flags: List[ClinicalReviewItem],
    ):
        status = row.get("validation_status", "")
        if status == "needs_clinical_review":
            flags.append(
                ClinicalReviewItem(
                    record_id=record_id,
                    flag_reason="added_record_needs_review",
                    details=f"Newly added record flagged for clinical review: {row.get('notes', '')}",
                    severity_level="medium",
                )
            )

        if self.dataset == "allergy":
            rel_type = row.get("relationship_type", "")
            if rel_type == "uncertain_mapping":
                flags.append(
                    ClinicalReviewItem(
                        record_id=record_id,
                        flag_reason="uncertain_allergy_mapping",
                        details="Relationship type is 'uncertain_mapping'. Requires qualified allergist review.",
                        severity_level="high",
                    )
                )

    def _check_group_conflicts(
        self,
        records: Dict[str, Dict[str, str]],
        flags: List[ClinicalReviewItem],
    ):
        """
        Detects inter-source conflicts within the candidate dataset
        (e.g., same interaction_group_id evaluated by multiple sources with conflicting severities).
        """
        if self.dataset != "ddi":
            return

        groups: Dict[str, List[Dict[str, str]]] = {}
        for row in records.values():
            grp_id = row.get("interaction_group_id", "").strip()
            if grp_id:
                groups.setdefault(grp_id, []).append(row)

        for grp_id, group_rows in groups.items():
            if len(group_rows) > 1:
                severities = {r.get("severity", "").strip().lower() for r in group_rows if r.get("severity")}
                if len(severities) > 1:
                    # Discrepancy between sources
                    sources_str = ", ".join(f"{r.get('source_id')}:{r.get('severity')}" for r in group_rows)
                    for r in group_rows:
                        flags.append(
                            ClinicalReviewItem(
                                record_id=r.get("record_id", "unknown"),
                                flag_reason="multi_source_severity_conflict",
                                details=(
                                    f"Interaction group '{grp_id}' contains conflicting source severities "
                                    f"across sources: [{sources_str}]"
                                ),
                                severity_level="high",
                            )
                        )

    def save_reports(self, report: DiffReport) -> Tuple[Path, Path]:
        """
        Saves both JSON and Markdown reports to MODAWEM_REPORTS_DIR.
        """
        reports_dir = get_reports_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"{self.dataset}_diff_{timestamp}"

        json_path = reports_dir / f"{prefix}.json"
        md_path = reports_dir / f"{prefix}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())

        return json_path, md_path
