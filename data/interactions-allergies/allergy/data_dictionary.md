# Data Dictionary: Drug-Allergen Cross-Reference Dataset (`modawem_allergy.csv`)

## 1. Overview & Architectural Scope

The Modawem Drug-Allergen Cross-Reference dataset (`modawem_allergy.csv`) establishes structured relationships between known patient drug allergies, chemical drug classes, and active pharmaceutical ingredients. It powers hypersensitivity screening and allergy contraindication checks within the Modawem mobile companion and prescribing backend.

### Initial Clinical Scope
The initial scope focuses on high-risk, high-frequency hypersensitivity categories:
1. **Penicillin Class and Beta-Lactams:** Characterizing true IgE-mediated cross-reactivity vs. class membership vs. side-chain specific cross-reactivity (e.g., aminopenicillins vs. aminocephalosporins).
2. **Sulfonamide-Related Classes:** Differentiating arylamine sulfonamide antimicrobials from non-arylamine sulfonamides.

---

## 2. Critical Clinical Safety Directives

1. **Non-Conflation of Sulfonamide Antibiotics and Non-Antibiotics:**
   - Sulfonamide antimicrobials (e.g., *sulfamethoxazole*) feature an aromatic amine ($N4$) and a 5- or 6-membered substituted ring at the $N1$ sulfonamide nitrogen, driving stereospecific immunological and toxicological reactions.
   - Non-antibiotic sulfonamides (e.g., *furosemide*, *celecoxib*, *sumatriptan*, *tamsulosin*) lack the $N4$ aromatic amine.
   - **Clinical Rule:** Do NOT conflate antibiotic sulfonamides with non-antibiotic sulfonamides. Cross-reactivity between sulfonamide antibiotics and non-antibiotics is not supported by immunological evidence. Label non-antibiotic manufacturer warnings strictly as `precaution`, never as `documented_cross_reactivity`.
2. **Class Membership is NOT Proof of Cross-Reactivity:**
   - Belonging to a chemical superfamily (e.g., beta-lactams) does not mean cross-reactivity occurs across all members. Cross-reactivity between penicillins and 3rd/4th generation cephalosporins or carbapenems is historically over-reported and primarily governed by $R_1$ side-chain structural homology.
   - **Clinical Rule:** Use `class_membership` to denote taxonomy, and reserve `documented_cross_reactivity` strictly for relationships where clinical or immunological literature validates cross-reactivity.
3. **Qualifiers Must Retain Scientific Nuance:**
   - Always state immunological mechanisms (IgE-mediated immediate vs. T-cell mediated delayed) and structural qualifiers (e.g., *shared R1 side chain with ampicillin*).

---

## 3. Complete 16-Column Specification

| # | Column Name | Data Type | Required | Allowed Values / Format | Description & Clinical Rules |
|---|---|---|---|---|---|
| 1 | `record_id` | String | Yes | Unique string (e.g., `ALG-REC-00001`, UUID) | Unique, immutable identifier for this allergen-ingredient relationship record. |
| 2 | `allergen_name` | String | Yes | Substance / drug name (e.g., `Penicillin G`, `Sulfamethoxazole`) | Index allergen to which patient hypersensitivity is documented. |
| 3 | `allergen_class` | String | Yes | Drug class name (e.g., `Penicillins`, `Sulfonamide Antibiotics`) | Established therapeutic or chemical class of the index allergen. |
| 4 | `ingredient_name` | String | Yes | Non-proprietary name (e.g., `Amoxicillin`, `Cephalexin`, `Celecoxib`) | Active ingredient evaluated for cross-sensitivity or class relationship. |
| 5 | `ingredient_id` | String | Yes | Alphanumeric (e.g., `723`, `2231`) | Unique identifier of the ingredient in `ingredient_id_system`. |
| 6 | `ingredient_id_system` | String | Yes | `RxNorm`, `UNII`, `CAS`, `custom` | Coding authority for the ingredient ID. RxNorm RxCUI preferred. |
| 7 | `relationship_type` | String | Yes | `class_membership`, `documented_cross_reactivity`, `precaution`, `uncertain_mapping` | **Strict clinical relationship type.** (See Section 4). |
| 8 | `evidence_summary` | String | Yes | Text summary | Concise synthesis of literature, package inserts, or clinical practice guidelines. |
| 9 | `qualifiers` | String | No | Text | Structural and immunological qualifiers (e.g., *identical R1 side chain*, *non-arylamine*). |
| 10 | `source_id` | String | Yes | Stable identifier (e.g., `AAAAI`, `DailyMed`, `PubMed`, `FDA`) | Source institution, medical society, or compendium. |
| 11 | `source_record_id` | String | Yes | String / alphanumeric | Identifier used within the originating source. |
| 12 | `source_version` | String | Yes | Version / year (e.g., `2024-Guideline`, `v1.2`) | Release version or publication year of the source. |
| 13 | `source_url` | String | No | Valid URI format (`https://...`) | Canonical URL to guideline, study, or product monograph. |
| 14 | `retrieved_at` | String | Yes | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`) | Exact date and time when data was compiled or ingested. |
| 15 | `validation_status` | String | Yes | `unvalidated`, `technically_validated`, `needs_clinical_review`, `clinically_approved` | Current validation status. (See Section 5). |
| 16 | `notes` | String | No | Text | Contextual notes, review commentary, or clinical warnings. |

---

## 4. Permitted Values for `relationship_type`

Only the following four values are permitted by the schema and validator:

1. **`class_membership`:**
   - **Definition:** The ingredient is a member of the stated chemical or pharmacological class (e.g., *Ampicillin* is a member of *Penicillins*).
   - **Constraint:** Does not assert or guarantee cross-reactivity with external classes.
2. **`documented_cross_reactivity`:**
   - **Definition:** High-quality clinical trials, immunological testing (skin testing/specific IgE), or published clinical practice guidelines explicitly confirm cross-reactivity between the allergen and the ingredient.
   - **Example:** *Amoxicillin* and *Cefadroxil* sharing identical side chains.
3. **`precaution`:**
   - **Definition:** A precautionary warning exists (e.g., in FDA package inserts) based on theoretical class overlap, but independent clinical or immunological evidence does not support true allergic cross-reactivity.
   - **Example:** *Celecoxib* product labeling warning regarding patients with sulfonamide allergy.
4. **`uncertain_mapping`:**
   - **Definition:** The relationship, structural similarity, or ingredient identifier cannot be verified with sufficient confidence.
   - **Constraint:** Automatically triggers `needs_clinical_review` in `validation_status`.

---

## 5. Validation Status Lifecycle

- **`unvalidated`:** Raw ingested candidate data.
- **`technically_validated`:** Satisfies schema, column order, non-empty fields, date formats, and allowed enums.
- **`needs_clinical_review`:** Flagged when conflicting evidence exists between sources, `relationship_type` is `uncertain_mapping`, or novel cross-reactivity logic is proposed.
- **`clinically_approved`:** Validated by an authorized clinical pharmacist or allergist. Never set automatically.
