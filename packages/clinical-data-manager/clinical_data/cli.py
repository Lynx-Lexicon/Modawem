"""
Command Line Interface for Modawem Clinical Data Manager (modawem-dataset).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from clinical_data.config import (
    find_workspace_root,
    get_cache_dir,
    get_dataset_location,
    get_reports_dir,
)
from clinical_data.differ import DatasetDiffer
from clinical_data.fetcher import DatasetFetcher
from clinical_data.manifest import ManifestManager
from clinical_data.validator import DatasetValidator


def cmd_validate(args: argparse.Namespace) -> int:
    dataset = args.dataset.lower()
    file_path = Path(args.file).resolve()
    print(f"[*] Validating {dataset.upper()} dataset file: {file_path}")

    validator = DatasetValidator(dataset=dataset)
    result = validator.validate_file(file_path)

    if result.is_valid:
        print(f"[+] VALID: File conforms to {dataset.upper()} schema v{result.schema_version}.")
        print(f"[+] Total records validated: {result.row_count}")
        if result.warnings:
            for w in result.warnings:
                print(f"    [!] Warning: {w}")
        return 0
    else:
        print(f"[-] INVALID: Found {len(result.errors)} validation errors:")
        for err in result.errors[:25]:
            row_prefix = f"Row {err.row_number}: " if err.row_number else ""
            field_prefix = f"[{err.field}] " if err.field else ""
            print(f"    - {row_prefix}{field_prefix}({err.error_type}) {err.message}")
        if len(result.errors) > 25:
            print(f"    ... and {len(result.errors) - 25} more errors.")
        return 1


def cmd_refresh(args: argparse.Namespace) -> int:
    dataset = args.dataset.lower()
    location = args.location or get_dataset_location(dataset)

    print(f"[*] Refreshing {dataset.upper()} dataset from: {location}")
    fetcher = DatasetFetcher()
    validator = DatasetValidator(dataset)
    manifest_mgr = ManifestManager(dataset)
    differ = DatasetDiffer(dataset)

    # 1. Fetch to staging
    try:
        fetch_result = fetcher.fetch(
            dataset=dataset,
            location=location,
            expected_sha256=args.expected_sha256,
        )
    except Exception as e:
        print(f"[-] Fetch failed: {e}", file=sys.stderr)
        return 1

    try:
        # 2. Check Idempotency
        if manifest_mgr.is_same_as_active(fetch_result.sha256_checksum) and not args.force:
            print(f"[+] Idempotent check passed: Active version already matches candidate SHA-256 ({fetch_result.sha256_checksum[:8]}...). No changes required.")
            fetch_result.cleanup()
            return 0

        # 3. Validate Staged Candidate
        print(f"[*] Validating candidate ({fetch_result.bytes_downloaded} bytes, SHA-256: {fetch_result.sha256_checksum})...")
        val_result = validator.validate_file(fetch_result.staged_file_path)
        if not val_result.is_valid:
            print(f"[-] Validation failed for candidate. Aborting refresh; active version was NOT modified.", file=sys.stderr)
            for err in val_result.errors[:15]:
                print(f"    - ({err.error_type}) {err.message}", file=sys.stderr)
            fetch_result.cleanup()
            return 1

        # 4. Generate Diff Against Current Active
        active_csv = manifest_mgr.get_active_file_path()
        manifest = manifest_mgr.load_manifest()
        diff_report = differ.generate_diff(
            candidate_path=fetch_result.staged_file_path,
            baseline_path=active_csv,
            baseline_version_id=manifest.active_version,
        )

        json_rep, md_rep = differ.save_reports(diff_report)
        print(f"[+] Differential reports generated:")
        print(f"    JSON: {json_rep}")
        print(f"    MD:   {md_rep}")

        # 5. Atomically Activate New Version
        version_rec = manifest_mgr.activate_version(
            staged_csv_path=fetch_result.staged_file_path,
            sha256_hash=fetch_result.sha256_checksum,
            row_count=val_result.row_count,
            remote_location=location,
            schema_version=val_result.schema_version,
            custom_version_id=args.version_id,
        )

        print(f"[+] Refresh Successful! Activated Version: {version_rec.version_id}")
        print(f"    Active file: {manifest_mgr.active_dir / f'modawem_{dataset}.csv'}")
        print(f"    Total records: {version_rec.row_count}")
        print(f"    Diff Summary: +{diff_report.added_count} / -{diff_report.removed_count} / ~{diff_report.modified_count}")
        if diff_report.clinical_review_required:
            print(f"    [!] ATTENTION: {diff_report.clinical_review_count} changes flagged for clinical review.")

        return 0

    finally:
        fetch_result.cleanup()


def cmd_status(args: argparse.Namespace) -> int:
    datasets = [args.dataset.lower()] if args.dataset else ["ddi", "allergy"]
    for ds in datasets:
        mgr = ManifestManager(ds)
        manifest = mgr.load_manifest()
        print(f"\n==================== DATASET: {ds.upper()} ====================")
        print(f"Active Version:    {manifest.active_version or 'None (Not initialized)'}")
        if manifest.active_version and manifest.active_version in manifest.versions:
            rec = manifest.versions[manifest.active_version]
            print(f"Activated At:      {rec.activated_at}")
            print(f"Remote Location:   {rec.remote_location}")
            print(f"SHA-256 Hash:      {rec.sha256_hash}")
            print(f"Row Count:         {rec.row_count}")
            print(f"Active CSV Path:   {mgr.get_active_file_path()}")
        print(f"Total Versions:    {len(manifest.versions)}")
        print(f"Total History:     {len(manifest.history)} events")
        if manifest.versions:
            print("Historical Versions:")
            for vid, v in sorted(manifest.versions.items(), key=lambda x: x[1].activated_at, reverse=True)[:5]:
                print(f"  * {vid} | {v.activated_at} | {v.row_count} rows | hash:{v.sha256_hash[:8]}...")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    dataset = args.dataset.lower()
    candidate_path = Path(args.candidate).resolve()
    differ = DatasetDiffer(dataset)
    manifest_mgr = ManifestManager(dataset)

    baseline_path = Path(args.baseline).resolve() if args.baseline else manifest_mgr.get_active_file_path()
    manifest = manifest_mgr.load_manifest()
    baseline_ver = manifest.active_version if not args.baseline else "custom_baseline"

    print(f"[*] Generating diff for {dataset.upper()}...")
    print(f"    Baseline:  {baseline_path or 'None'}")
    print(f"    Candidate: {candidate_path}")

    report = differ.generate_diff(
        candidate_path=candidate_path,
        baseline_path=baseline_path,
        baseline_version_id=baseline_ver,
    )

    json_rep, md_rep = differ.save_reports(report)
    print(report.to_markdown())
    print(f"\n[+] Full reports written to:\n    {json_rep}\n    {md_rep}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    dataset = args.dataset.lower()
    target_version = args.target_version
    print(f"[*] Rolling back {dataset.upper()} dataset to version '{target_version}'...")

    manifest_mgr = ManifestManager(dataset)
    try:
        rec = manifest_mgr.rollback(target_version)
        print(f"[+] Rollback Successful! Active version is now: {rec.version_id}")
        print(f"    Active file: {manifest_mgr.get_active_file_path()}")
        print(f"    SHA-256:     {rec.sha256_hash}")
        print(f"    Row count:   {rec.row_count}")
        return 0
    except Exception as e:
        print(f"[-] Rollback failed: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modawem-dataset",
        description="Modawem Clinical Data Infrastructure Management CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a local dataset CSV against schema")
    p_val.add_argument("--dataset", required=True, choices=["ddi", "allergy"], help="Target dataset")
    p_val.add_argument("--file", required=True, help="Path to CSV candidate file")
    p_val.set_defaults(func=cmd_validate)

    # refresh
    p_ref = subparsers.add_parser("refresh", help="Refresh dataset from remote or local storage")
    p_ref.add_argument("--dataset", required=True, choices=["ddi", "allergy"], help="Target dataset")
    p_ref.add_argument("--location", help="Override remote or local source location")
    p_ref.add_argument("--expected-sha256", help="Optional expected SHA-256 checksum")
    p_ref.add_argument("--version-id", help="Optional explicit version ID string")
    p_ref.add_argument("--force", action="store_true", help="Force refresh even if checksum matches active")
    p_ref.set_defaults(func=cmd_refresh)

    # status
    p_stat = subparsers.add_parser("status", help="Show active version and history of datasets")
    p_stat.add_argument("--dataset", choices=["ddi", "allergy"], help="Filter by specific dataset")
    p_stat.set_defaults(func=cmd_status)

    # diff
    p_diff = subparsers.add_parser("diff", help="Generate differential and clinical review report")
    p_diff.add_argument("--dataset", required=True, choices=["ddi", "allergy"], help="Target dataset")
    p_diff.add_argument("--candidate", required=True, help="Path to new candidate CSV file")
    p_diff.add_argument("--baseline", help="Optional path to baseline CSV (defaults to current active)")
    p_diff.set_defaults(func=cmd_diff)

    # rollback
    p_rb = subparsers.add_parser("rollback", help="Roll back dataset to a prior validated version")
    p_rb.add_argument("--dataset", required=True, choices=["ddi", "allergy"], help="Target dataset")
    p_rb.add_argument("--target-version", required=True, help="Version ID to roll back to")
    p_rb.set_defaults(func=cmd_rollback)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
