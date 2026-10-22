# Deliverable 4: Unmodified Baseline Evaluation Report

**Audit Date:** 2026-10-14  
**Target Module:** `ai-services/normalization/rxnorm_normalize.py` (Unmodified Baseline)  
**Execution Mode:** Deterministic Offline Replay via Verified SQLite Disk Cache  

---

## 1. Executive Summary & Baseline Metrics

Before making any code modifications, we executed the unmodified normalizer across the newly constructed, anti-leakage evaluation datasets (`calibration.csv` and `dev.csv`) as well as existing fixtures (`rxnorm_fixture.csv` and `rxnorm_adversarial.csv`).

### Primary Baseline Performance Matrix:

| Dataset Split | Total Cases | Accuracy (%) | Precision | Recall | F1 Score | False Positives | Unresolved (%) | API Errors |
|---|---|---|---|---|---|---|---|---|
| `calibration.csv` | 190 | **76.32%** | 1.0 | 0.698 | 0.8221 | 0 | 45.26% | 0 |
| `dev.csv` | 154 | **56.49%** | 0.9825 | 0.459 | 0.6257 | 1 | 62.99% | 0 |
| `rxnorm_fixture.csv` | 209 | **98.56%** | 1.0 | 0.9856 | 0.9927 | 0 | 1.44% | 0 |
| `rxnorm_adversarial.csv` | 12 | **100.0%** | 1.0 | 1.0 | 1.0 | 0 | 33.33% | 0 |

---

## 2. Category-by-Category Baseline Breakdown

The table below details performance across the 10 mandatory clinical categories on the **Calibration Set** (190 cases) and **Dev Set** (154 cases):

| Category | Split | Total | Accuracy | Precision | Recall | F1 Score | Unresolved | False Positives |
|---|---|---|---|---|---|---|---|---|
| `combination_products` | `calibration` | 20 | 90.0% | 1.0 | 0.9 | 0.9474 | 2 | 0 |
| `conflicting_or_nonexistent` | `calibration` | 19 | 100.0% | 1.0 | 1.0 | 1.0 | 19 | 0 |
| `form_and_route_variations` | `calibration` | 8 | 75.0% | 1.0 | 0.75 | 0.8571 | 2 | 0 |
| `insufficient_or_ambiguous` | `calibration` | 22 | 100.0% | 1.0 | 1.0 | 1.0 | 22 | 0 |
| `look_alike_sound_alike` | `calibration` | 13 | 92.3% | 1.0 | 0.9231 | 0.96 | 1 | 0 |
| `salt_variants` | `calibration` | 12 | 100.0% | 1.0 | 1.0 | 1.0 | 0 | 0 |
| `standard_clean` | `calibration` | 48 | 79.2% | 1.0 | 0.7917 | 0.8837 | 10 | 0 |
| `strength_and_concentration` | `calibration` | 10 | 30.0% | 1.0 | 0.3 | 0.4615 | 7 | 0 |
| `typos_and_formatting` | `calibration` | 32 | 46.9% | 1.0 | 0.4688 | 0.6383 | 17 | 0 |
| `unit_variations` | `calibration` | 6 | 0.0% | 1.0 | 0.0 | 0.0 | 6 | 0 |
| `combination_products` | `dev` | 6 | 66.7% | 1.0 | 0.6667 | 0.8 | 2 | 0 |
| `conflicting_or_nonexistent` | `dev` | 18 | 100.0% | 1.0 | 1.0 | 1.0 | 18 | 0 |
| `form_and_route_variations` | `dev` | 4 | 50.0% | 1.0 | 0.5 | 0.6667 | 2 | 0 |
| `insufficient_or_ambiguous` | `dev` | 14 | 92.9% | 0.0 | 1.0 | 0.0 | 13 | 1 |
| `look_alike_sound_alike` | `dev` | 9 | 66.7% | 1.0 | 0.6667 | 0.8 | 3 | 0 |
| `salt_variants` | `dev` | 5 | 100.0% | 1.0 | 1.0 | 1.0 | 0 | 0 |
| `standard_clean` | `dev` | 26 | 80.8% | 1.0 | 0.8077 | 0.8936 | 5 | 0 |
| `strength_and_concentration` | `dev` | 12 | 41.7% | 1.0 | 0.4167 | 0.5883 | 7 | 0 |
| `typos_and_formatting` | `dev` | 30 | 43.3% | 1.0 | 0.4333 | 0.6046 | 17 | 0 |
| `unit_variations` | `dev` | 30 | 0.0% | 1.0 | 0.0 | 0.0 | 30 | 0 |

---

## 3. Key Baseline Insights & Observations

1. **Single-Ingredient Strength Resolution is High:** Clean and typo variations on single ingredients with simple integer strengths (e.g., `lisinopril 10 mg oral tablet`, `metformin 500 mg tab`) resolve with high precision.
2. **Liquid Concentration Ratios Fail Systematically:** Inputs such as `amoxicillin 250 mg/5 mL oral suspension` or `prednisolone 15 mg/5 mL oral solution` fail to match because the current `rxnorm_normalize.py` expects exact string tokens rather than calculating mathematical concentration equivalence (`50 mg/mL` and `3 mg/mL`).
3. **Multi-Ingredient Combination Reordering Misses:** Combination drugs where the user enters components in reverse order (e.g. `hydrochlorothiazide / lisinopril 20 mg / 12.5 mg`) or with salt mismatches fail attribute verification in `parse_identity` and `attributes_compatible`.
4. **Unit Variations (`mcg` vs `mg`):** Microgram inputs like `levothyroxine 50 mcg` fail when the RxNorm concept is stored as `0.05 mg`, causing preventable false rejections.
5. **Rejection Safety on Adversarial Cases is Preserved:** Impossible strengths (`lisinopril 999 mg tablet`) and ambiguous salts correctly remain unresolved.