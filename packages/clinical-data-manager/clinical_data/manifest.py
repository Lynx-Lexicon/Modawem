"""
Version Manifest and Rollback Management for Modawem Clinical Datasets.
Includes inter-process locking, crash consistency, self-healing, and immutability guarantees.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from clinical_data.config import get_cache_dir
from clinical_data.fetcher import calculate_sha256

VERSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\.\-]+$")


def sanitize_version_id(version_id: str) -> str:
    """
    Validates that a version identifier contains only safe alphanumeric characters,
    dots, dashes, and underscores. Prevents path traversal vulnerabilities.
    """
    cleaned = version_id.strip()
    if not cleaned or not VERSION_ID_REGEX.match(cleaned) or ".." in cleaned:
        raise ValueError(
            f"Invalid version identifier '{version_id}'. Version IDs must contain only "
            "alphanumeric characters, underscores, dashes, and dots, with no path traversal ('..')."
        )
    return cleaned


class DatasetLock:
    """
    Inter-process file lock for clinical dataset cache operations.
    Enforces token-based ownership so a process only releases its own lock,
    preventing lock-stealing and race conditions.
    """

    def __init__(self, lock_path: Path, timeout_seconds: float = 10.0, stale_seconds: float = 120.0):
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self.lock_token = str(uuid.uuid4())
        self.acquired = False

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{self.lock_token}:{os.getpid()}:{time.time()}")
                self.acquired = True
                return self
            except FileExistsError:
                # Check for abandoned stale lock
                try:
                    mtime = self.lock_path.stat().st_mtime
                    if time.time() - mtime > self.stale_seconds:
                        self._break_stale_lock()
                        continue
                except OSError:
                    pass

                if time.time() - start_time >= self.timeout_seconds:
                    raise TimeoutError(
                        f"Could not acquire lock for dataset cache at {self.lock_path} within {self.timeout_seconds}s. "
                        "Another operation may be in progress."
                    )
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release()

    def _release(self):
        if self.acquired and self.lock_path.exists():
            try:
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content.startswith(self.lock_token):
                    self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass
        self.acquired = False

    def _break_stale_lock(self):
        if self.lock_path.exists():
            try:
                mtime = self.lock_path.stat().st_mtime
                if time.time() - mtime > self.stale_seconds:
                    self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass


@dataclass
class VersionRecord:
    version_id: str
    dataset_name: str
    schema_version: str
    remote_location: str
    retrieved_at: str
    sha256_hash: str
    validation_status: str
    row_count: int
    file_relative_path: str
    activated_at: str


@dataclass
class ActivationHistoryEvent:
    timestamp: str
    action: str  # "refresh", "rollback", "self-heal"
    version_id: str
    previous_version_id: Optional[str]
    notes: str = ""


@dataclass
class DatasetManifest:
    dataset_name: str
    active_version: Optional[str]
    versions: Dict[str, VersionRecord] = field(default_factory=dict)
    history: List[ActivationHistoryEvent] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "dataset_name": self.dataset_name,
            "active_version": self.active_version,
            "versions": {k: asdict(v) for k, v in self.versions.items()},
            "history": [asdict(h) for h in self.history],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> DatasetManifest:
        versions = {}
        for k, v in data.get("versions", {}).items():
            versions[k] = VersionRecord(**v)
        history = [ActivationHistoryEvent(**h) for h in data.get("history", [])]
        return cls(
            dataset_name=data.get("dataset_name", "unknown"),
            active_version=data.get("active_version"),
            versions=versions,
            history=history,
        )


class ManifestManager:
    """
    Manages the lifecycle, version manifest (manifest.json), atomic activation,
    crash consistency, and rollback of clinical datasets.
    """

    def __init__(self, dataset: str):
        self.dataset = "ddi" if dataset.lower().strip() in ("ddi", "drug_drug_interaction") else "allergy"
        self.dataset_cache_dir = get_cache_dir() / self.dataset
        self.versions_dir = self.dataset_cache_dir / "versions"
        self.active_dir = self.dataset_cache_dir / "active"
        self.manifest_file = self.dataset_cache_dir / "manifest.json"
        self.lock_file = self.dataset_cache_dir / ".dataset.lock"

        # Ensure directory structure
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.active_dir.mkdir(parents=True, exist_ok=True)

    def lock(self, timeout_seconds: float = 10.0) -> DatasetLock:
        return DatasetLock(self.lock_file, timeout_seconds=timeout_seconds)

    def load_manifest(self) -> DatasetManifest:
        if not self.manifest_file.exists():
            return DatasetManifest(dataset_name=self.dataset, active_version=None)
        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DatasetManifest.from_dict(data)
        except Exception:
            return DatasetManifest(dataset_name=self.dataset, active_version=None)

    def _save_manifest_atomic(self, manifest: DatasetManifest):
        """
        Atomically saves manifest.json via temporary file replace.
        """
        data = manifest.to_dict()
        temp_file = self.dataset_cache_dir / f"manifest_{os.getpid()}_{int(time.time() * 1000)}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Atomic rename/replace on same filesystem
        temp_file.replace(self.manifest_file)

    def get_active_file_path(self) -> Optional[Path]:
        """
        Returns the path to the currently active CSV file.
        Automatically verifies integrity against manifest and self-heals
        if an interruption left active out of sync with manifest.
        """
        manifest = self.load_manifest()
        if not manifest.active_version or manifest.active_version not in manifest.versions:
            return None

        active_rec = manifest.versions[manifest.active_version]
        target_active = self.active_dir / f"modawem_{self.dataset}.csv"
        version_csv = self.dataset_cache_dir / active_rec.file_relative_path

        # Check if active file exists and matches the active version hash
        if target_active.exists():
            current_hash = calculate_sha256(target_active)
            if current_hash.lower() == active_rec.sha256_hash.lower():
                return target_active

        # Self-heal from immutable historical version if mismatched or missing
        if version_csv.exists() and calculate_sha256(version_csv).lower() == active_rec.sha256_hash.lower():
            temp_active = self.active_dir / f"modawem_{self.dataset}.csv.tmp_{os.getpid()}"
            shutil.copy2(version_csv, temp_active)
            temp_active.replace(target_active)
            return target_active

        return None

    def is_same_as_active(self, sha256_hash: str) -> bool:
        """
        Checks whether the given hash matches the active version hash.
        Used to guarantee refresh idempotency.
        """
        manifest = self.load_manifest()
        if not manifest.active_version:
            return False
        active_rec = manifest.versions.get(manifest.active_version)
        if not active_rec:
            return False
        return active_rec.sha256_hash.lower() == sha256_hash.lower()

    def activate_version(
        self,
        staged_csv_path: Path,
        sha256_hash: str,
        row_count: int,
        remote_location: str,
        schema_version: str = "1.0.0",
        custom_version_id: Optional[str] = None,
    ) -> VersionRecord:
        """
        Atomically registers a validated candidate into version history and activates it.
        Guarantees:
          - Inter-process locking.
          - Immutability of historical versions (rejects overwrite with different bytes).
          - Path traversal sanitization on version identifiers.
          - Crash consistency between manifest and active CSV.
        """
        clean_hash = sha256_hash.strip().lower()

        # Sanitize version_id
        if custom_version_id:
            version_id = sanitize_version_id(custom_version_id)
        else:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            version_id = f"v{timestamp_str}"

        with self.lock():
            manifest = self.load_manifest()
            now_utc = datetime.now(timezone.utc).isoformat()

            # Immutability Check: Do not allow overwriting an existing version with different data
            if version_id in manifest.versions:
                existing_rec = manifest.versions[version_id]
                if existing_rec.sha256_hash.lower() != clean_hash:
                    raise ValueError(
                        f"Version '{version_id}' already exists in version history with different SHA-256 "
                        f"(existing: {existing_rec.sha256_hash[:8]}..., new: {clean_hash[:8]}...). "
                        "Historical versions are strictly immutable."
                    )
                # If identical, reuse existing record
                version_record = existing_rec
                version_target_csv = self.dataset_cache_dir / existing_rec.file_relative_path
            else:
                # Store new immutable version copy via atomic temporary write and replace
                version_target_dir = self.versions_dir / version_id
                version_target_dir.mkdir(parents=True, exist_ok=True)
                version_target_tmp = version_target_dir / f"modawem_{self.dataset}.csv.tmp_{os.getpid()}"
                shutil.copy2(staged_csv_path, version_target_tmp)
                if calculate_sha256(version_target_tmp).lower() != clean_hash:
                    version_target_tmp.unlink(missing_ok=True)
                    raise ValueError("Checksum verification failed while copying candidate to historical version storage.")
                version_target_csv = version_target_dir / f"modawem_{self.dataset}.csv"
                version_target_tmp.replace(version_target_csv)

                relative_path = str(version_target_csv.relative_to(self.dataset_cache_dir))
                version_record = VersionRecord(
                    version_id=version_id,
                    dataset_name=self.dataset,
                    schema_version=schema_version,
                    remote_location=remote_location,
                    retrieved_at=now_utc,
                    sha256_hash=clean_hash,
                    validation_status="technically_validated",
                    row_count=row_count,
                    file_relative_path=relative_path,
                    activated_at=now_utc,
                )
                manifest.versions[version_id] = version_record

            # Update active version reference in manifest
            previous_ver = manifest.active_version
            history_event = ActivationHistoryEvent(
                timestamp=now_utc,
                action="refresh",
                version_id=version_id,
                previous_version_id=previous_ver,
                notes=f"Activated from {remote_location} (SHA-256: {clean_hash[:8]}...)",
            )

            manifest.active_version = version_id
            manifest.history.append(history_event)

            # 1. Save manifest atomically FIRST with active pointer
            self._save_manifest_atomic(manifest)

            # 2. Update active file atomically
            temp_active = self.active_dir / f"modawem_{self.dataset}.csv.tmp_{os.getpid()}"
            shutil.copy2(version_target_csv, temp_active)
            target_active = self.active_dir / f"modawem_{self.dataset}.csv"
            temp_active.replace(target_active)

            return version_record

    def rollback(self, target_version_id: str) -> VersionRecord:
        """
        Reverts active dataset to target_version_id without deleting version history.
        Verifies SHA-256 checksum of target version file before activation to reject
        corrupted historical versions.
        """
        clean_target_id = sanitize_version_id(target_version_id)

        with self.lock():
            manifest = self.load_manifest()
            if clean_target_id not in manifest.versions:
                available = ", ".join(manifest.versions.keys()) or "None"
                raise ValueError(
                    f"Target rollback version '{clean_target_id}' not found in manifest for '{self.dataset}'. "
                    f"Available versions: {available}"
                )

            target_record = manifest.versions[clean_target_id]
            target_csv = self.dataset_cache_dir / target_record.file_relative_path

            if not target_csv.exists():
                raise FileNotFoundError(
                    f"Target version file is missing from cache at {target_csv}"
                )

            # Integrity Verification: Ensure target historical file has not been corrupted
            target_computed_hash = calculate_sha256(target_csv)
            if target_computed_hash.lower() != target_record.sha256_hash.lower():
                raise ValueError(
                    f"Historical version file '{clean_target_id}' is corrupted. "
                    f"Expected SHA-256: {target_record.sha256_hash}, found: {target_computed_hash}. "
                    "Rollback aborted to preserve active dataset integrity."
                )

            # 1. Update manifest history
            now_utc = datetime.now(timezone.utc).isoformat()
            previous_ver = manifest.active_version
            history_event = ActivationHistoryEvent(
                timestamp=now_utc,
                action="rollback",
                version_id=clean_target_id,
                previous_version_id=previous_ver,
                notes=f"Rolled back from {previous_ver} to {clean_target_id}",
            )

            manifest.active_version = clean_target_id
            manifest.history.append(history_event)
            self._save_manifest_atomic(manifest)

            # 2. Atomic copy to active
            temp_active = self.active_dir / f"modawem_{self.dataset}.csv.tmp_{os.getpid()}"
            shutil.copy2(target_csv, temp_active)
            target_active = self.active_dir / f"modawem_{self.dataset}.csv"
            temp_active.replace(target_active)

            return target_record
