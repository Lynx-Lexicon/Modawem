# Data Dictionary: Drug-Drug Interaction Dataset (`modawem_ddi.csv`)

## 1. Overview & Architectural Purpose

The Modawem Drug-Drug Interaction (DDI) dataset (`modawem_ddi.csv`) provides a standardized, multi-source reference of pharmacological interactions between active pharmaceutical ingredients. It is designed to drive safety alerts in the Modawem mobile companion and clinical decision support backend.

### Core Principles
1. **Active Ingredients Over Brand Names:** Interactions are evaluated and stored at the active ingredient level (e.g., *sildenafil* and *nitroglycerin*), rather than by brand/trade names.
2. **Preservation of Source Provenance:** Multiple sources (e.g., ONC High Priority, DrugBank, DailyMed) describing the same interaction pair are stored as distinct records, preserving source-specific severity, clinical descriptions, and management guidance.
3. **Deterministic Interaction Grouping:** Independent source records referring to the same ingredient pair share a canonical `interaction_group_id` without mutating individual records.
4. **Preservation of Source Severities:** Severity scales vary widely between clinical compendia. Severity classifications are retained exactly as stated by the originating source without arbitrary cross-scale conflation.
5. **Technical vs. Clinical Validation:** Technical schema and integrity validation is strictly separated from qualified clinical approval. A record is never marked `clinically_approved` without a documented clinical review process.

---

## 2. Complete 19-Column Specification

The table below specifies all 19 columns in their required sequential order.

| # | Column Name | Data Type | Required | Allowed Values / Format | Description & Clinical Rules |
|---|---|---|---|---|---|
| 1 | `record_id` | String | Yes | Unique string (e.g., `DDI-REC-00001`, UUID) | Unique identifier for this specific source record. Must be immutable. |
| 2 | `interaction_group_id` | String | Yes | `GRP-<system_1>-<id_1>-<system_2>-<id_2>` | Deterministic canonical identifier grouping all records for this ingredient pair, sorted canonically. |
| 3 | `ingredient_a_name` | String | Yes | Standard non-proprietary name (e.g., `Warfarin`) | Active ingredient A. Do not record salt or dosage form unless pharmacologically distinct. |
| 4 | `ingredient_a_id` | String | Yes | Alphanumeric (e.g., `11289`) | Unique identifier for Ingredient A in the specified coding system. |
| 5 | `ingredient_a_id_system` | String | Yes | `RxNorm`, `UNII`, `CAS`, `custom` | Coding authority for Ingredient A identifier. RxNorm RxCUI preferred. |
| 6 | `ingredient_b_name` | String | Yes | Standard non-proprietary name (e.g., `Aspirin`) | Active ingredient B. |
| 7 | `ingredient_b_id` | String | Yes | Alphanumeric (e.g., `1191`) | Unique identifier for Ingredient B in the specified coding system. |
| 8 | `ingredient_b_id_system` | String | Yes | `RxNorm`, `UNII`, `CAS`, `custom` | Coding authority for Ingredient B identifier. RxNorm RxCUI preferred. |
| 9 | `interaction_type` | String | Yes | `pharmacokinetic`, `pharmacodynamic`, `additive`, `antagonism`, `unspecified` | Underlying pharmacological mechanism of interaction. |
| 10 | `severity` | String | Yes | Source-specific string (e.g., `Contraindicated`, `Major`, `Moderate`, `Minor`, `Severe`) | Severity level **exactly as classified by the originating source**. Do not force into a synthetic scale. |
| 11 | `clinical_effect` | String | Yes | Free text narrative | Summary of observed or potential adverse clinical outcome. |
| 12 | `management_guidance` | String | No | Free text narrative | Evidence-based recommendation, monitoring plan, or alternative therapy. |
| 13 | `source_id` | String | Yes | Stable identifier (e.g., `ONCHigh`, `DrugBank`, `DailyMed`, `FDA`) | Registered identifier of the source institution or dataset. |
| 14 | `source_record_id` | String | Yes | String / alphanumeric | Identifier used within the original source dataset. |
| 15 | `source_version` | String | Yes | Version / release string or date (e.g., `2026.10`, `v5.1`) | Version of the source dataset at the time of extraction. |
| 16 | `source_url` | String | No | Valid URI format (`https://...`) | Canonical reference or access URL for the source record. |
| 17 | `retrieved_at` | String | Yes | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`) | Exact date and time the record was fetched or compiled. |
| 18 | `validation_status` | String | Yes | `unvalidated`, `technically_validated`, `needs_clinical_review`, `clinically_approved` | Current lifecycle state. Strict lifecycle rules apply (see Section 3). |
| 19 | `notes` | String | No | Free text | Annotations, clinical rationale for review flags, or mapping caveats. |

---

## 3. Validation Status Lifecycle & Rules

The `validation_status` field strictly tracks clinical and engineering confidence:

1. **`unvalidated`:**
   - Raw extracted data prior to automated schema validation and integrity verification.
2. **`technically_validated`:**
   - The record has passed automated CSV structural checks, column order enforcement, required field presence, date format validation, and identifier checks.
   - **Crucial Rule:** Technical validation DOES NOT imply clinical endorsement.
3. **`needs_clinical_review`:**
   - Automatically flagged by ingestion or diff pipelines when:
     * Two authoritative sources report conflicting severities for the same `interaction_group_id` (e.g., `Contraindicated` vs `Minor`).
     * The ingredient identifier mapping is uncertain, missing an RxCUI, or mapped through a fuzzy fallback.
     * Clinical management guidance is ambiguous, missing, or contradictory.
     * Newly derived clinical logic or classification rules have been applied.
4. **`clinically_approved`:**
   - Formally evaluated and confirmed by a licensed clinical pharmacist or physician with documented reviewer credentials and audit trail.
   - **Never set programmatically or automatically.**

---

## 4. Canonical Grouping (`interaction_group_id`)

To ensure commutative equivalence where `Interaction(A, B) == Interaction(B, A)`:
1. Normalize ingredient identity to canonical keys: `<system>:<id>`.
2. Sort keys lexicographically:
   $$\text{Key}_1 = \min(A, B), \quad \text{Key}_2 = \max(A, B)$$
3. Construct group ID:
   $$\text{GRP-}\{\text{system}_1\}\text{-}\{\text{id}_1\}\text{-}\{\text{system}_2\}\text{-}\{\text{id}_2\}$$

**Example:**
- Ingredient A: Warfarin (`RxNorm:11289`)
- Ingredient B: Aspirin (`RxNorm:1191`)
- Group ID: `GRP-RxNorm-11289-RxNorm-1191` (or lexicographically sorted `GRP-RxNorm-1191-RxNorm-11289`).
All records from all sources evaluating Aspirin and Warfarin share this group ID.
