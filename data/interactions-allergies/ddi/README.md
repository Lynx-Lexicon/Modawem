# Modawem Drug-Drug Interaction (DDI) Dataset Infrastructure

## 1. Overview

This directory houses the schema definitions, data dictionary, source register, and technical contracts for Modawem's Drug-Drug Interaction dataset (`modawem_ddi.csv`).

In accordance with Modawem Git Security policies, **full production dataset files are never tracked in Git**. Full release versions are maintained in external secure remote storage (e.g., `Modawem Clinical Data/ddi/versions/`) and synchronized using the `packages/clinical-data-manager` CLI tooling (`modawem-dataset`).

---

## 2. Directory Structure

```
data/interactions-allergies/ddi/
├── README.md               # Architecture and engineering guide (this file)
├── data_dictionary.md      # Detailed column definitions and clinical rules
├── schema.json             # Machine-readable JSON schema (19 ordered columns)
└── source_register.csv     # Approved data sources, licensing, and provenance
```

---

## 3. Remote Storage & Versioning Architecture

Full CSV datasets are distributed through versioned immutable artifacts:
```
Modawem Clinical Data/
└── ddi/
    └── versions/
        ├── v1.0.0/
        │   ├── modawem_ddi.csv
        │   └── modawem_ddi.csv.sha256
        ├── v1.1.0/
        │   ├── modawem_ddi.csv
        │   └── modawem_ddi.csv.sha256
        └── manifest.json
```

- Each version directory contains the exact CSV and its SHA-256 integrity checksum.
- When ingested locally via `modawem-dataset refresh --dataset ddi`, files are staged into temporary storage, checksum-verified, schema-validated, and atomically linked to the local cache directory (`MODAWEM_DATA_CACHE_DIR`).

---

## 4. Ingestion & Validation Commands

All refresh, validation, diffing, and rollback operations are driven by the `clinical_data` package:

```bash
# 1. Validate a local DDI candidate against schema
python -m clinical_data.cli validate --dataset ddi --file path/to/candidate.csv

# 2. Refresh DDI dataset from remote storage
python -m clinical_data.cli refresh --dataset ddi

# 3. Check current dataset status and active version
python -m clinical_data.cli status --dataset ddi

# 4. Generate structured diff between active version and candidate
python -m clinical_data.cli diff --dataset ddi --candidate path/to/candidate.csv

# 5. Rollback to a prior validated version
python -m clinical_data.cli rollback --dataset ddi --target-version v1.0.0
```

---

## 5. Clinical Review & Safety Guardrails

- **No Synthetic Clinical Claims:** Do not fabricate drug interactions.
- **Source Fidelity:** Retain the original source severity rating without forcibly standardizing across heterogeneous scales.
- **Review Flagging:** Records flagged with `needs_clinical_review` in `validation_status` require evaluation by a qualified medical professional prior to production CDS deployment.
- **Zero Leakage:** Never commit raw or cached CSV files to git.
