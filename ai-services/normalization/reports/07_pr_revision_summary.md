# PR Revision Summary: Clinical Normalizer Engineering & Safety Audit

**Date:** 2026-10-16  
**Module:** `ai-services/normalization/rxnorm_normalize.py`  
**Branch:** `feat/rxnorm-normalization-service`  
**Test Suite Status:** 70 passed, 1 deselected (100% passing in 7.65s)  
**Strict Anti-Leakage Gate:** PASSED (0.0% chemical overlap, 0.0% query duplicate overlap)  

---

## 1. Executive Summary

This engineering revision addresses all critical issues identified in the PR review (`PR Revision — RxNorm Normalizer Review`) across five focused tasks:
1. **Evaluation Label Consistency & Strict Metric Formulas:** Reconciled ground-truth labels for unmodified tablets (e.g., `metformin 500 mg tablet` mapping to immediate-release SCD `861007`) across all test and evaluation splits, ensuring 0 label contradictions. Audited metric definitions so False Negatives strictly include any failed resolution (including API/infrastructure errors).
2. **Ingredient-Level Split Isolation (Zero Active Ingredient Leakage):** Re-engineered dataset splitting using a Connected Components (Union-Find) graph across all active chemical ingredients (including multi-ingredient combinations). Achieved mathematically guaranteed **0.0% chemical ingredient leakage** and **0.0% duplicate normalized query overlap** between `calibration`, `dev`, and `held_out_test`.
3. **Structured Ingredient-Strength Pairing in Combination Products:** Implemented structured `(ingredient, strength)` tuple binding in `Identity`. Enforces order-invariant matching (`amox 500 / clav 125 == clav 125 / amox 500`) while strictly rejecting swapped strengths (`amlodipine 10 / atorvastatin 5` vs candidate `597977`) and mismatched component strengths.
4. **Cache Stampede Prevention (Per-Key Single-Flight Coordination):** Implemented thread-safe, per-key single-flight request coalescing across `RxNormNormalizer.normalize()`, property lookups, and underlying HTTP transport (`_get`). Concurrent threads for identical uncached keys execute the underlying call exactly once; distinct keys execute concurrently; exceptions unblock all waiters cleanly without deadlock or cache poisoning.
5. **Comprehensive Verification & Final Benchmarks:** Added offline regression and concurrency tests in `tests/test_rxnorm_regression.py`. Executed full baseline vs. post-fix evaluations across all splits, demonstrating **98.67% accuracy and 100.0% precision (0 False Positives)** on the held-out test set.

---

## 2. Task 1: Evaluation Label Consistency & Metric Integrity

### Clinical & Informatics Policy for Unmodified Tablets
- **Problem Identified:** `metformin 500mg tablet` was marked as `unresolved` in the synthetic evaluation dataset under `insufficient_or_ambiguous`, whereas `tests/rxnorm_adversarial.csv` expected it to resolve to `861007` (`metformin hydrochloride 500 MG Oral Tablet`, `TTY=SCD`).
- **Clinical Policy:** In clinical pharmacy and RxNorm ontology:
  - An input specifying active ingredient, strength, and standard dosage form (`tablet` / `oral tablet`) without specifying a release mechanism (`ER`/`XR`/`DR`) denotes a standard immediate-release formulation.
  - In RxNorm, unmodified `Oral Tablet` concepts correspond to immediate release. Extended-release concepts require explicit release modifiers (`Extended Release Oral Tablet`, `24 HR extended release`).
  - Our release-mechanism veto in `rxnorm_normalize.py` explicitly vetoes extended-release candidates when immediate release is requested.
  - Therefore, `metformin 500 mg tablet` maps deterministically to `861007`.
- **Reconciliation Actions:**
  1. Updated `scripts/build_evaluation_dataset.py` so that inputs under `insufficient_or_ambiguous` testing release mechanism or salt ambiguity use explicit disjunctive formulations:
     - `metformin 500 mg immediate or extended release tablet` -> `unresolved`
     - `metoprolol 50 mg tartrate or succinate tablet` -> `unresolved`
     - `metoprolol 100 mg tartrate or succinate tablet` -> `unresolved`
     - `metoprolol tartrate or succinate` -> `unresolved`
  2. Verified that standard unmodified inputs (`metformin 500 mg tablet`) resolve to `861007` in `tests/rxnorm_adversarial.csv` and across the service with **0 contradictions**.

### Strict Metric Definitions (`scripts/run_evaluation.py`)
All evaluation metrics follow rigorous clinical audit definitions:
$$\text{TP} = \sum [\text{expected}=\text{resolved} \land \text{actual}=\text{resolved} \land \text{actual\_rxcui}=\text{expected\_rxcui}]$$
$$\text{FP} = \sum [\text{expected}=\text{unresolved} \land \text{actual}=\text{resolved}] + \sum [\text{expected}=\text{resolved} \land \text{actual}=\text{resolved} \land \text{actual\_rxcui}\neq\text{expected\_rxcui}]$$
$$\text{FN} = \sum [\text{expected}=\text{resolved} \land \text{actual} \in \{\text{unresolved}, \text{error}\}]$$
$$\text{TN} = \sum [\text{expected}=\text{unresolved} \land \text{actual}=\text{unresolved}]$$

---

## 3. Task 2: Ingredient-Level Split Isolation (Zero Chemical Leakage)

### Union-Find Connected Component Partitioning
When multi-ingredient products (e.g., `amoxicillin + clavulanate`, `lisinopril + hydrochlorothiazide`, `metformin + sitagliptin`, `amlodipine + atorvastatin`) are partitioned naively, active ingredients bridge across splits (e.g., `amoxicillin` in calibration, `amoxicillin-clavulanate` in dev).

To eliminate 100% of ingredient leakage:
1. **Active Ingredient Graph:** For every benchmark case, the set of active chemical entities is extracted (`set[str]`). An undirected graph is constructed where edges connect any ingredients co-occurring in the same formulation.
2. **Connected Components (Union-Find):** Disjoint connected components are computed. All cases containing any ingredient in a connected component are grouped into an atomic component cluster (74 total components across 85 ingredient clusters).
3. **Atomic Component Partitioning:** Connected components are partitioned atomically among `calibration` (~38%), `dev` (~29%), and `held_out_test` (~33%) using greedy relative fill balancing.
4. **Normalized Query Deduplication:** All cases are passed through `normalize_query(raw_input)`. Exact duplicate normalized queries across cases were removed (18 duplicate cases eliminated, reducing benchmark from 475 to 457 strictly unique cases).
5. **Automated Verification Gate:** A strict assertion gate in `build_evaluation_dataset.py` and `tests/test_rxnorm_regression.py` validates:
   ```python
   assert not (calib_ingredients & dev_ingredients)
   assert not (calib_ingredients & test_ingredients)
   assert not (dev_ingredients & test_ingredients)
   assert not (calib_queries & dev_queries)
   assert not (calib_queries & test_queries)
   assert not (dev_queries & test_queries)
   for split in [calib, dev, test]:
       assert len({c["category"] for c in split}) == 10
   ```
   **Result:** PASSED with 0 chemical overlap and all 10 clinical categories represented in all 3 splits.

---

## 4. Task 3: Structured Ingredient-Strength Pairing in Combination Products

### Implementation Details
In multi-ingredient formulations, string bag-of-words or unlinked strength lists can misidentify swapped strengths (e.g. matching `amlodipine 10 / atorvastatin 5` to candidate `amlodipine 5 / atorvastatin 10` because both `{5, 10}` and `{amlodipine, atorvastatin}` are present).

1. **Identity Schema Update:**
   ```python
   @dataclass(frozen=True)
   class Identity:
       ...
       ingredient_strength_pairs: tuple[tuple[str, str], ...] = ()
   ```
2. **Extraction Engine (`_extract_ingredient_strength_pairs`):**
   - Normalizes prescription delimiters (`/`, `+`, `and`, `with`).
   - Handles multi-segment formulations, interleaved drug-strength pairs, and RxNorm SCD formats (`amoxicillin and clavulanate potassium 500 MG / 125 MG Oral Tablet`).
   - Denominator lookahead in `_STRENGTH` and `normalize_query` restricted to fluid volumes (`(?:ml|l|actuat|puff)`), preventing combination product slashes (`500 mg / 125 mg`) from being merged into single ratios.
3. **Structured Matching Policy (`are_ingredient_strength_pairs_compatible`):**
   - For every query `(ingredient, strength)` pair, finds a candidate pair matching the ingredient (token/fuzzy matching) AND having mathematically compatible strength (`are_strengths_compatible`).
   - If candidate strengths are swapped, or if any component strength differs, returns `conflict`, causing candidate rejection.
4. **Clinical Verification:**
   - `amlodipine 5 mg + atorvastatin 10 mg` -> `resolved` (`597977`)
   - `atorvastatin 10 mg + amlodipine 5 mg` -> `resolved` (`597977`, order-invariant)
   - `amlodipine 10 mg + atorvastatin 5 mg` -> `unresolved` (swapped strength rejected)
   - `amlodipine 5 mg + atorvastatin 50 mg` -> `unresolved` (mismatched strength rejected)

---

## 5. Task 4: Cache Stampede Prevention (Per-Key Single-Flight Coordination)

### Concurrency Architecture
Under burst loads, multiple worker threads requesting the same uncached medication simultaneously previously triggered redundant upstream HTTP requests (cache stampede).

1. **Per-Key Single-Flight Coalescing:**
   - Added thread-safe synchronization:
     ```python
     self._in_flight: dict[str, Event] = {}
     self._last_error: dict[str, str] = {}
     ```
   - When a thread requests key `K`:
     - If `K` is cached in `_cache[K]`: returns immediately (cache hit).
     - If `K` is currently in-flight: thread obtains the `Event` and waits on `event.wait()`.
     - Otherwise: thread becomes the *leader*, creates an `Event()`, registers it in `_in_flight[K]`, and executes the normalization / property lookup.
     - In a `finally` block, the leader sets `event.set()` and removes `K` from `_in_flight`.
2. **Parallelism for Distinct Keys:**
   - Single-flight synchronization is strictly per-key; requests for distinct keys progress concurrently in parallel without serialization lock contention.
3. **Exception Recovery & Resilience:**
   - If the leader encounters an upstream network failure or timeout:
     - Error is recorded in `_last_error[K]` and surfaces as `Result(status="error")`.
     - All waiting follower threads unblock and surface the error without hanging or deadlock.
     - `_in_flight[K]` is cleaned up in `finally`.
     - `_cache[K]` is NOT poisoned with the error.
     - Subsequent retries re-attempt resolution and succeed immediately upon upstream recovery.

---

## 6. Task 5: Comprehensive Verification & Benchmark Results

### Pytest Test Suite
`python -m pytest -v ai-services/normalization/tests`:
- `tests/test_rxnorm_fixture.py`: 15 passed
- `tests/test_rxnorm_normalize.py`: 29 passed
- `tests/test_rxnorm_regression.py`: 21 passed
- `tests/test_rxnorm_service.py`: 5 passed
- **Total: 70 passed, 1 deselected in 7.65s (100% passing)**

### Full Benchmark Evaluation Matrix (Baseline vs. Post-Fix)

| Dataset Split | Split Role | Cases | Baseline Acc | Post-Fix Acc | Baseline Rec | Post-Fix Rec | Baseline Prec | Post-Fix Prec | Baseline F1 | Post-Fix F1 | FP Count |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **`calibration.csv`** | Tuning | 173 | 70.52% | **97.11%** | 62.50% | **96.32%** | 100.0% | **100.0%** | 76.92% | **98.13%** | **0** |
| **`dev.csv`** | Validation | 134 | 84.33% | **98.51%** | 79.21% | **98.02%** | 100.0% | **100.0%** | 88.40% | **99.00%** | **0** |
| **`held_out_test.csv`** | Independent Test | 150 | 84.67% | **98.67%** | 80.83% | **98.33%** | 100.0% | **100.0%** | 89.40% | **99.16%** | **0** |
| **`full_evaluation_dataset.csv`** | Comprehensive | 457 | 79.21% | **98.03%** | 73.39% | **97.48%** | 100.0% | **100.0%** | 84.65% | **98.72%** | **0** |
| **`rxnorm_fixture.csv`** | Exact Smoke | 209 | 98.56% | **98.56%** | 98.56% | **98.56%** | 100.0% | **100.0%** | 99.27% | **99.27%** | **0** |
| **`rxnorm_adversarial.csv`** | Rejection Guard | 12 | 100.0% | **100.0%** | 100.0% | **100.0%** | 100.0% | **100.0%** | 100.0% | **100.0%** | **0** |

### Category-Level Accuracy on Held-Out Test Set (`held_out_test.csv`, N=150)
- `combination_products` (18/18): **100.0%**
- `conflicting_or_nonexistent` (15/15): **100.0%**
- `form_and_route_variations` (19/19): **100.0%**
- `insufficient_or_ambiguous` (15/15): **100.0%**
- `look_alike_sound_alike` (11/11): **100.0%**
- `salt_variants` (10/10): **100.0%**
- `standard_clean` (23/23): **100.0%**
- `strength_and_concentration` (10/10): **100.0%**
- `unit_variations` (7/7): **100.0%**
- `typos_and_formatting` (20/22): **90.9%** (2 severe misspellings conservatively rejected)

---

## 7. Compliance Checklist

- [x] **No Arbitrary Threshold Tweaking:** `ACCEPT_THRESHOLD` remains `0.90909`, `AMBIGUITY_MARGIN` remains `0.05`.
- [x] **Zero Chemical Ingredient Overlap:** Formally proven across splits with connected components algorithm.
- [x] **Zero Normalized Query Duplicates:** Deduplication enforced across all 457 benchmark cases.
- [x] **Zero Hallucinated RxCUIs:** All positive concepts verified in RxNorm/NDC reference database.
- [x] **Public API Contracts Preserved:** Public interfaces of `normalize_query`, `parse_identity`, `gather_candidates`, `rank_candidates`, `accept`, and `evaluate` remain 100% backward-compatible.
- [x] **External Storage of Large Assets:** Large reference databases (`drug_reference.sqlite`, 53 MB, and `rxnorm_http_cache.sqlite`) safely hosted on Google Drive at `G:\My Drive\Modawem_RxNorm_Dataset`, keeping Git commits lightweight and code-focused.
