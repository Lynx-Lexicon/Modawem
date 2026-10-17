# Modawem Drug-Allergen Cross-Reference Dataset Infrastructure

## 1. Overview

This directory houses the schema definitions, data dictionary, source register, and technical contracts for Modawem's Drug-Allergen Cross-Reference dataset (`modawem_allergy.csv`).

In accordance with Modawem Git Security policies, **full production dataset files are never tracked in Git**. Full release versions are maintained in external secure remote storage (e.g., `Modawem Clinical Data/allergy/versions/`) and synchronized using the `packages/clinical-data-manager` CLI tooling (`modawem-dataset`).

---

## 2. Directory Structure

```
data/interactions-allergies/allergy/
├── README.md               # Architecture and engineering guide (this file)
├── data_dictionary.md      # Detailed column definitions and clinical rules
├── schema.json             # Machine-readable JSON schema (16 ordered columns)
└── source_register.csv     # Approved data sources, licensing, and provenance
```

---

## 3. Remote Storage & Versioning Architecture

Full CSV datasets are distributed through versioned immutable artifacts:
```
Modawem Clinical Data/
└── allergy/
    └── versions/
        ├── v1.0.0/
        │   ├── modawem_allergy.csv
        │   └── modawem_allergy.csv.sha256
        ├── v1.1.0/
        │   ├── modawem_allergy.csv
        │   └── modawem_allergy.csv.sha256
        └── manifest.json
```

- Each version directory contains the exact CSV and its SHA-256 integrity checksum.
- When ingested locally via `modawem-dataset refresh --dataset allergy`, files are staged into temporary storage, checksum-verified, schema-validated, and atomically linked to the local cache directory (`MODAWEM_DATA_CACHE_DIR`).

---

## 4. Ingestion & Validation Commands

All operations are executed via the `clinical_data` package:

```bash
# 1. Validate a local Allergy candidate against schema
python -m clinical_data.cli validate --dataset allergy --file path/to/candidate.csv

# 2. Refresh Allergy dataset from remote storage
python -m clinical_data.cli refresh --dataset allergy

# 3. Check current dataset status and active version
python -m clinical_data.cli status --dataset allergy

# 4. Generate structured diff between active version and candidate
python -m clinical_data.cli diff --dataset allergy --candidate path/to/candidate.csv

# 5. Rollback to a prior validated version
python -m clinical_data.cli rollback --dataset allergy --target-version v1.0.0
```

---

## 5. Clinical Safety Directives

1. **Strict Relationship Types:** Only `class_membership`, `documented_cross_reactivity`, `precaution`, and `uncertain_mapping` are permitted.
2. **Sulfonamide Distinction:** Never treat non-antibiotic sulfonamides (furosemide, celecoxib) as cross-reactive with sulfonamide antimicrobials (sulfamethoxazole) unless explicitly supported by clinical studies.
3. **Beta-Lactam Side Chains:** Recognize that beta-lactam cross-reactivity is largely dictated by $R_1$ side-chain structural similarity rather than class-wide cross-reactivity.
4. **Clinical Review:** Any `uncertain_mapping` or newly flagged source conflict must have `validation_status = "needs_clinical_review"` and cannot be marked `clinically_approved` without qualified physician/pharmacist sign-off.
