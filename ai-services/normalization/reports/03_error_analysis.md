# Deliverable 5: Comprehensive Error Analysis Report

**Audit Date:** 2026-10-14  
**Target Module:** `ai-services/normalization/rxnorm_normalize.py`  
**Total Evaluated Records Analyzed:** 565  
**Total Discrepancies/Errors Identified:** 115  

---

## 1. Error Classification by Bucket

| Error Classification Bucket | Count | Percentage of Errors | Severity & Risk |
|---|---|---|---|
| **`False Negative`** | 114 | 99.1% | MODERATE: Valid clinical drug returned unresolved; clinical friction |
| **`False Positive`** | 1 | 0.9% | CRITICAL: Incorrect medication concept mapped; high patient safety risk |

---

## 2. Failure Attribution by Pipeline Stage

| Pipeline Stage | Function in `rxnorm_normalize.py` | Error Count | Primary Mechanism of Failure |
|---|---|---|---|
| `parse_identity` | `parse_identity(text)` | 74 | Inability to parse ratio strengths (`250 mg/5 mL`), convert `mcg`<->`mg`, or extract multi-component identities |
| `accept` | `accept(...)` | 38 | Conservative threshold floor rejection, or `_attribute_state` rejecting valid equivalents |
| `gather_candidates` | `gather_candidates(term)` | 3 | Query string misses exact RxCUI, approximate search truncated before valid SCD is reached |

---

## 3. In-Depth Root-Cause Analysis with Concrete Examples

### 3.1 Failure Pattern 1: Liquid Concentration Ratios (`strength_and_concentration`)
**Root Cause:** `_canon_strength()` extracts `250 mg/5 ml` as a literal string. In `_attribute_state()`, it checks whether `250 mg/5 ml` appears in the candidate name. But RxNorm clinical drug concepts are stored in canonical `50 mg/ml` format.

**Concrete Examples from Evaluation Run:**
- Input: `amoxicillin 250 mg/5 ml oral suspension`  
  Expected: `239191` (`amoxicillin 50 MG/ML Oral Suspension`)  
  Actual: `unresolved` | Reason: *'Best candidate does not match parsed query attributes'*
- Input: `prednisolone 15 mg/5 ml oral solution`  
  Expected: `283077` (`prednisolone 3 MG/ML Oral Solution`)  
  Actual: `unresolved` | Reason: *'Best candidate does not match parsed query attributes'*

### 3.2 Failure Pattern 2: Unit Conversions (`mcg` vs `mg` in `unit_variations`)
**Root Cause:** `_canon_strength()` replaces `µg` with `mcg`, but performs no mathematical conversion between `mcg` and `mg`. When a doctor writes `levothyroxine 50 mcg`, `query_identity.strengths` contains `('50mcg',)` while the RxNorm concept contains `0.05 mg`. The attribute comparator marks them incompatible.

**Concrete Examples:**
- Input: `levothyroxine sodium 50 mcg oral tablet`  
  Expected: `313990` (`levothyroxine sodium 0.05 MG Oral Tablet`)  
  Actual: `unresolved`
- Input: `digoxin 125 mcg oral tablet`  
  Expected: `310020` (`digoxin 0.125 MG Oral Tablet`)  
  Actual: `unresolved`

### 3.3 Failure Pattern 3: Component Reordering in Multi-Ingredient Drugs (`combination_products`)
**Root Cause:** Lexical similarity (`fuzz.ratio` and token sort) in `rank_candidates()` scores reordered inputs lower. Additionally, `parse_identity()` relies on a simple slash check without parsing separate ingredient-strength pairings, causing multi-ingredient candidates to be rejected.

**Concrete Examples:**
- Input: `hydrochlorothiazide / lisinopril 20 mg / 12.5 mg oral tablet`  
  Expected: `197886` (`hydrochlorothiazide 12.5 MG / lisinopril 20 MG Oral Tablet`)  
  Actual: `unresolved`

---

## 4. Remediation Roadmap for Phase 4
To resolve these empirical failure modes without sacrificing precision or rejection safety:
1. **Mathematical Ratio Equivalence in `parse_identity`:** Parse liquid concentrations `X mg / Y mL` and normalize to `(X/Y) mg/mL`.
2. **Unit Normalization (`mcg` <-> `mg`):** Store strengths in standardized SI base units (milligrams) for direct attribute comparison.
3. **Permutation-Invariant Combination Parsing:** Parse multi-ingredient sets and strengths as unordered maps.