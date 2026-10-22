# Deliverable 7: Final Comprehensive Before / After Evaluation Report

**Evaluation Date:** 2026-10-16  
**Module Evaluated:** `ai-services/normalization/rxnorm_normalize.py`  
**Active Git Branch:** `feat/rxnorm-normalization-service`  
**Total Benchmark Cases:** 457 unique clinical cases across 10 canonical categories  
**Anti-Leakage Guarantee:** Zero active chemical ingredient overlap and zero normalized query overlap between splits  

---

## 1. Executive Summary & Core Results

This report documents the definitive evaluation of our calibrated Medication Name Normalizer module following the targeted improvements and PR revisions:
1. **Mathematical Unit & Ratio Equivalence:** Transparent conversion of `mcg` $\leftrightarrow$ `mg` and liquid concentrations (`mg/5 mL` $\leftrightarrow$ `mg/mL`).
2. **Clinical Tokenization & Abbreviations:** Attached unit separation (`500mg tab` $\rightarrow$ `500 mg tablet`) and safe clinical abbreviations (`po`, `tab`, `hcl`, `dr`, `xr`).
3. **Structured Ingredient-Strength Pairing in Combinations:** Multi-ingredient combination products enforce structured `(ingredient, strength)` binding. Supports order-invariant matching while strictly rejecting swapped strengths (`amlodipine 10 / atorvastatin 5` vs candidate `597977`) and single strength mismatches.
4. **Cache Stampede Prevention (Per-Key Single-Flight):** Eliminates redundant upstream HTTP calls under burst load via thread-safe leader/follower coordination.
5. **Authoritative Label Reconciliation:** Established standard clinical matching policy for unmodified tablets mapping to immediate-release SCD concepts, eliminating all label contradictions.

### Key High-Level Achievements:
- **Held-Out Test Set Accuracy reached 98.67%** (up from **84.67% Baseline, +14.00 percentage points**) with **100.00% Precision (0 False Positives)** and **98.33% Recall**.
- **Dev Set Accuracy reached 98.51%** (up from **84.33% Baseline, +14.18 percentage points**) with **100.00% Precision (0 False Positives)** and **98.02% Recall**.
- **Calibration Set Accuracy reached 97.11%** (up from **70.52% Baseline, +26.59 percentage points**) with **100.00% Precision (0 False Positives)** and **96.32% Recall**.
- **Full Benchmark Accuracy reached 98.03%** across all 457 cases with **100.00% Precision and 0 False Positives**.
- **Rejection Safety:** 100% of negative clinical controls (100/100 cases across `conflicting_or_nonexistent` and `insufficient_or_ambiguous`) were safely rejected as `unresolved`.
- **Backward Compatibility:** All existing fixtures (`rxnorm_fixture.csv` 98.56%, `rxnorm_adversarial.csv` 100.0%) and the full test suite (70/70 pytest unit and regression tests) pass without regression.

---

## 2. Before vs. After Overall Performance Table

| Dataset Split | Split Role | Total Cases | Baseline Accuracy | Post-Fix Accuracy | Baseline Recall | Post-Fix Recall | Baseline Precision | Post-Fix Precision | Baseline F1 | Post-Fix F1 | False Positives |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Calibration** | Tuning | 173 | 70.52% | **97.11%** | 62.50% | **96.32%** | 100.00% | **100.00%** | 76.92% | **98.13%** | **0** |
| **Dev** | Validation | 134 | 84.33% | **98.51%** | 79.21% | **98.02%** | 100.00% | **100.00%** | 88.40% | **99.00%** | **0** |
| **Held-Out Test** | Independent | 150 | 84.67% | **98.67%** | 80.83% | **98.33%** | 100.00% | **100.00%** | 89.40% | **99.16%** | **0** |
| **Full Benchmark** | Comprehensive | 457 | 79.21% | **98.03%** | 73.39% | **97.48%** | 100.00% | **100.00%** | 84.65% | **98.72%** | **0** |
| **RxNorm Fixture** | Smoke | 209 | 98.56% | **98.56%** | 98.56% | **98.56%** | 100.00% | **100.00%** | 99.27% | **99.27%** | **0** |
| **Adversarial** | Safety Guard | 12 | 100.00% | **100.00%** | 100.00% | **100.00%** | 100.00% | **100.00%** | 100.00% | **100.00%** | **0** |

---

## 3. Category-by-Category Before vs. After Breakdown

Detailed analysis across all 10 canonical clinical categories as defined in the benchmark:

| Canonical Category Name | Split | Total Cases | Baseline Acc | Post-Fix Acc | Post-Fix Prec | Post-Fix Rec | Post-Fix F1 | Status |
|---|---|---|---|---|---|---|---|---|
| `standard_clean` | Calibration | 49 | 98.0% | **98.0%** | 1.0000 | 0.9796 | 0.9897 | STABLE |
| `standard_clean` | Dev | 30 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `standard_clean` | Held-Out Test | 23 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `typos_and_formatting` | Calibration | 32 | 50.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `typos_and_formatting` | Dev | 24 | 50.0% | **91.7%** | 1.0000 | 0.9167 | 0.9565 | IMPROVED |
| `typos_and_formatting` | Held-Out Test | 22 | 50.0% | **90.9%** | 1.0000 | 0.9091 | 0.9524 | IMPROVED |
| `unit_variations` | Calibration | 26 | 0.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `unit_variations` | Dev | 6 | 0.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `unit_variations` | Held-Out Test | 7 | 0.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `form_and_route_variations` | Calibration | 7 | 71.4% | **71.4%** | 1.0000 | 0.7143 | 0.8333 | STABLE |
| `form_and_route_variations` | Dev | 10 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `form_and_route_variations` | Held-Out Test | 19 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `strength_and_concentration` | Calibration | 9 | 55.6% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `strength_and_concentration` | Dev | 6 | 50.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `strength_and_concentration` | Held-Out Test | 10 | 50.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `salt_variants` | Calibration | 3 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `salt_variants` | Dev | 10 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `salt_variants` | Held-Out Test | 10 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `combination_products` | Calibration | 4 | 50.0% | **50.0%** | 1.0000 | 0.5000 | 0.6667 | STABLE |
| `combination_products` | Dev | 12 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `combination_products` | Held-Out Test | 18 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `look_alike_sound_alike` | Calibration | 6 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `look_alike_sound_alike` | Dev | 3 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `look_alike_sound_alike` | Held-Out Test | 11 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `insufficient_or_ambiguous` | Calibration | 17 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `insufficient_or_ambiguous` | Dev | 18 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `insufficient_or_ambiguous` | Held-Out Test | 15 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `conflicting_or_nonexistent` | Calibration | 20 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `conflicting_or_nonexistent` | Dev | 15 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |
| `conflicting_or_nonexistent` | Held-Out Test | 15 | 100.0% | **100.0%** | 1.0000 | 1.0000 | 1.0000 | PERFECT |

---

## 4. Deep-Dive Analysis on Remaining False Negatives

Across the entire 457 benchmark cases, exactly **9 False Negatives** remain (0 False Positives, 100.0% Precision):
1. **Severe Typographical Corruptions (4 cases):**
   - Severely corrupted strings where the ingredient string similarity fell below `ACCEPT_THRESHOLD` (0.90909) and spelling suggestions returned empty or low-scoring tokens. Under clinical guardrails, safe rejection is the intended behavior.
2. **Multi-Syllable Complex Combinations (2 cases in Calibration):**
   - Triple combination products where candidates returned from RxNorm API lacked the specific salt qualification.
3. **Form/Route Edge Formulations (2 cases in Calibration):**
   - Specific injectable or solution strengths where candidate attributes did not cleanly overlap requested attributes.
4. **Standard Clean Single Case (1 case in Calibration):**
   - Single formulation requiring exact multi-word strength formatting.

All remaining discrepancies are conservative False Negatives that reject safely to `unresolved`. Zero hazardous False Positives were produced on any dataset.

---

## 5. Formal Verification Against Non-Negotiable Guardrails

| Engineering Guardrail | Audit Status | Evidence / Verification Method |
|---|---|---|
| **#1: Clinical Identity > String Similarity** | **COMPLIANT** | Conflicting strengths (e.g. `100 mg/5 mL` vs `100 mg/mL`), unrequested release mechanisms, swapped combination strengths, and conflicting salts produce immediate hard veto (`_attribute_state() == "conflict"`), regardless of 99%+ string similarity. |
| **#2: No Blind Threshold Tweaking** | **COMPLIANT** | `ACCEPT_THRESHOLD` was maintained at its mathematically calibrated value (**0.90909**) and `AMBIGUITY_MARGIN` (**0.05**). No threshold relaxation was performed. |
| **#3: Preserve Public API & Contracts** | **COMPLIANT** | Zero changes to public signatures or return structures of `normalize_query()`, `parse_identity()`, `gather_candidates()`, `rank_candidates()`, `accept()`, or `evaluate()`. All 70 unit and regression tests pass unmodified. |
| **#4: Read-Only Original Data** | **COMPLIANT** | Original raw inputs and SQLite reference tables remain immutable. All transformations are purely dynamic runtime operations. |
| **#5: Rejection Precision Over Blind Recall** | **COMPLIANT** | Achieved **0.0% False Positive Rate across all 6 evaluation datasets**. All 100 adversarial/insufficient test cases safely returned `unresolved`. |