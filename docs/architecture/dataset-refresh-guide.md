# Modawem Clinical Dataset Refresh & Ingestion Guide

## 1. Overview & System Purpose

The Modawem Clinical Data Infrastructure provides a secure, version-controlled, and clinically guarded ingestion mechanism for external Drug-Drug Interaction (DDI) and Drug-Allergen datasets.

Due to clinical compliance and Git security guardrails, **production CSV datasets are stored in external remote storage** and are never committed directly to the repository. The `clinical_data` package (`modawem-dataset` CLI) enables engineering and clinical teams to safely refresh, validate, diff, and rollback datasets without risking downtime or data corruption.

---

## 2. Directory Architecture

```
modawem/
├── data/
│   └── interactions-allergies/
│       ├── ddi/
│       │   ├── schema.json               # 19-column JSON schema
│       │   ├── data_dictionary.md        # Clinical definitions and rules
│       │   ├── source_register.csv       # Approved sources & licenses
│       │   └── README.md
│       └── allergy/
│           ├── schema.json               # 16-column JSON schema
│           ├── data_dictionary.md        # Clinical definitions & enums
│           ├── source_register.csv       # Approved sources & licenses
│           └── README.md
├── packages/
│   └── clinical-data-manager/            # Core Python ingestion package
│       ├── pyproject.toml
│       └── clinical_data/
│           ├── cli.py                    # CLI command handlers
│           ├── config.py                 # Environment & path resolver
│           ├── differ.py                 # Diff engine & clinical review routing
│           ├── fetcher.py                # Atomic staging & download
│           ├── manifest.py               # ManifestManager & rollback
│           └── validator.py              # Schema & integrity validator
├── reports/
│   └── refresh-reports/                  # JSON & Markdown diff reports
└── tests/
    ├── fixtures/                         # Synthetic test fixtures (5-10 rows)
    └── clinical_data/                    # Automated test suites
```

---

## 3. Environment Variables Configuration

The system is configured purely via environment variables to avoid hardcoded machine paths:

| Variable | Required | Default Location | Description |
|---|---|---|---|
| `MODAWEM_DDI_DATA_LOCATION` | Yes (for refresh) | None | Remote URL (`https://...`) or local file path (`file://...`) to `modawem_ddi.csv`. |
| `MODAWEM_ALLERGY_DATA_LOCATION` | Yes (for refresh) | None | Remote URL (`https://...`) or local file path (`file://...`) to `modawem_allergy.csv`. |
| `MODAWEM_DATA_CACHE_DIR` | No | `data/cache/clinical_data` | Root directory for local active files, versions, and `manifest.json`. |
| `MODAWEM_REPORTS_DIR` | No | `reports/refresh-reports` | Output directory for JSON and Markdown diff reports. |
| `MODAWEM_REMOTE_AUTH_TOKEN` | No | None | Optional Bearer authorization token for protected HTTP/HTTPS endpoints. |
| `MODAWEM_WORKSPACE_ROOT` | No | Auto-detected | Modawem monorepo root directory. |

### Configuration Example (.env)
```bash
MODAWEM_DDI_DATA_LOCATION=https://clinical-data.modawem.internal/ddi/versions/latest/modawem_ddi.csv
MODAWEM_ALLERGY_DATA_LOCATION=https://clinical-data.modawem.internal/allergy/versions/latest/modawem_allergy.csv
MODAWEM_DATA_CACHE_DIR=./data/cache/clinical_data
MODAWEM_REPORTS_DIR=./reports/refresh-reports
MODAWEM_REMOTE_AUTH_TOKEN=your_secure_bearer_token_here
```

---

## 4. Supported Remote Transports & Limitations

The fetcher (`DatasetFetcher`) supports the following protocols:
- `https://` and `http://`: Standard HTTPS/HTTP with streaming downloads, configurable timeouts, and optional Bearer token authentication.
- `file://` or filesystem paths: Direct local or mounted network files.

### Honest Limitations:
- Arbitrary cloud storage protocols (e.g., Google Drive web viewer URLs or AWS S3 URIs) are **not supported natively** unless mounted as a local volume or exposed via an authenticated direct HTTP(S) endpoint.
- SHA-256 calculation verifies byte-level file transfer integrity; it does not independently prove clinical validity or source authenticity.

---

## 5. Safe Atomic Refresh Lifecycle

Refresh operations execute with strict fault tolerance to prevent data corruption:

```
[Remote Source]
      │
      ▼ (Atomic Download)
[Temporary Staging Directory]
      │
      ├─► Compute SHA-256 Checksum
      ├─► Validate against Expected SHA-256 (if provided)
      ├─► Check Idempotency (if identical to active hash -> abort cleanly)
      │
      ▼ (Schema & Clinical Integrity Validation)
[DatasetValidator]
      │  * Column presence & exact 19/16 column order
      │  * Data types & non-empty required fields
      │  * Strict enum checks (relationship_type, validation_status)
      │  * Duplicate record_id detection
      │
      ├─► [INVALID] ──► Abort refresh. Output errors. Clean up staging.
      │                 *ACTIVE VERSION IS NEVER OVERWRITTEN*
      │
      ▼ [VALID]
[DatasetDiffer]
      │  * Compare against active version
      │  * Calculate Added / Removed / Modified records
      │  * Flag changes requiring qualified clinical review
      │  * Save JSON and Markdown diff reports to reports/refresh-reports/
      │
      ▼ (Atomic Activation)
[ManifestManager]
      │  * Copy to versions/<version_id>/modawem_<dataset>.csv (immutable)
      │  * Atomically replace active/modawem_<dataset>.csv
      │  * Atomically update manifest.json with history record
      │
      ▼
[Clean up Staging] ──► Refresh Complete!
```

---

## 6. CLI Command Reference

Execute commands using `modawem-dataset` (or `python -m clinical_data.cli` with `PYTHONPATH=packages/clinical-data-manager`).

### 1. Validate a Local Candidate
Validates a candidate CSV file against the target schema without activating it:
```bash
python -m clinical_data.cli validate --dataset ddi --file path/to/modawem_ddi.csv
python -m clinical_data.cli validate --dataset allergy --file path/to/modawem_allergy.csv
```

### 2. Refresh from Remote Storage
Fetches, validates, diffs, and activates the candidate:
```bash
# Uses environment variable MODAWEM_DDI_DATA_LOCATION
python -m clinical_data.cli refresh --dataset ddi

# Override location with local or custom URL
python -m clinical_data.cli refresh --dataset allergy --location /mnt/data/modawem_allergy.csv

# Verify with expected SHA-256 checksum
python -m clinical_data.cli refresh --dataset ddi --expected-sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

# Force re-activation even if hash matches active
python -m clinical_data.cli refresh --dataset ddi --force
```

### 3. Check Dataset Status
Displays active version, retrieval timestamps, SHA-256 hash, and historical activations:
```bash
python -m clinical_data.cli status
python -m clinical_data.cli status --dataset ddi
```

### 4. Generate Diff Report
Compares a candidate CSV against the active version (or custom baseline):
```bash
python -m clinical_data.cli diff --dataset ddi --candidate path/to/new_ddi.csv
```

### 5. Rollback to Prior Version
Reverts the active version to any historical validated version in `manifest.json`:
```bash
python -m clinical_data.cli rollback --dataset ddi --target-version v20261017_001500
```

---

## 7. Clinical Review Routing Guidelines

When a new version is ingested, the diff engine analyzes record modifications and generates clinical flags under `reports/refresh-reports/`.

The following changes trigger **High-Priority Clinical Review**:
1. **Severity Classification Changes:** Any change to the source severity level (e.g., `Major` to `Contraindicated` or vice versa).
2. **Allergy Relationship Changes:** Any change to `relationship_type` (e.g., `precaution` elevated to `documented_cross_reactivity`).
3. **Ingredient Identity Mappings:** Any modification to ingredient names, RxCUI identifiers, or coding systems.
4. **Inter-Source Severity Conflicts:** Multiple independent source records within the same `interaction_group_id` presenting conflicting severity levels.
5. **Uncertain Mappings:** Any new or modified records with `relationship_type = "uncertain_mapping"`.

**Policy:** Records flagged for clinical review must remain in `validation_status = "needs_clinical_review"` until signed off by an authorized clinical pharmacist. They must **never** be programmatically marked as `clinically_approved`.
