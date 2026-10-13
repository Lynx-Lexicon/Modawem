# Modawem Medication Adherence Engine (Task 2)

A robust, deterministic, interval-based Python engine for calculating **Proportion of Days Covered (PDC)** and **Medication Possession Ratio (MPR)** according to gold-standard pharmacy quality standards (PQA / CMS Star Ratings).

---

## 📌 Features

- **Pure Business Logic**: Zero external dependencies, zero coupling to databases, UI, or external APIs (Python Standard Library only).
- **Proportion of Days Covered (PDC)**:
  - Binary daily coverage (each calendar day counted at most once).
  - Strictly capped at 1.0 (100.0%).
  - PQA same-medication stockpiling (push-forward algorithm for early refills).
  - Days outside observation window are excluded.
- **Medication Possession Ratio (MPR)**:
  - Standard fill-date claims window calculation.
  - Strictly **uncapped** (can exceed 1.0 / 100.0% to accurately indicate over-possession).
  - Optional truncated/modified MPR mode available.
- **High-Performance Interval Arithmetic**:
  - $O(N \log N)$ complexity rather than wasteful day-by-day looping ($O(D \cdot N)$).
  - Evaluates 10-year longitudinal claims histories in under 1 millisecond.
- **Inclusive Calendar Boundaries**:
  - Observation period $[start\_date, end\_date]$ is inclusive: $days = (end - start) + 1$.
  - Explicit and verified handling of boundary fills (start-day and end-day).
- **Therapeutic Equivalence Rules**:
  - Non-equivalent medication fills are filtered out unless an explicit equivalence rule is defined.
- **Zero Intermediate Rounding**:
  - Full floating-point precision maintained internally (`value`), rounded presentation (`percentage`) on export.

---

## 🚀 Quickstart

### Installation
No external libraries needed! Uses Python 3.8+ standard library.

```bash
# Clone or navigate to the project directory
cd modawem_adherence
```

### Run Tests with a Single Command
```bash
python run_tests.py
```

All 22 unit, invariant, and hand-calculated clinical scenario tests will run and report their verification status.

---

## 💻 API Usage

### 1. Calculate PDC (Proportion of Days Covered)
```python
from adherence import calculate_pdc

fills = [
    {"fill_date": "2026-01-01", "days_supply": 30}
]

# 40-day observation window: 2026-01-01 to 2026-02-09 inclusive
result = calculate_pdc(fills, start_date="2026-01-01", end_date="2026-02-09")

print(result)
# Output:
# {
#   "value": 0.75,
#   "percentage": 75.0,
#   "observation_days": 40,
#   "covered_days": 30
# }
```

### 2. Calculate MPR (Medication Possession Ratio)
```python
from adherence import calculate_mpr

# Early refill scenario: 2 fills of 20 days supply within a 30-day window
fills = [
    {"fill_date": "2026-01-01", "days_supply": 20},
    {"fill_date": "2026-01-15", "days_supply": 20},
]

result = calculate_mpr(fills, start_date="2026-01-01", end_date="2026-01-30")

print(result)
# Output:
# {
#   "value": 1.3333333333333333,
#   "percentage": 133.33,
#   "observation_days": 30,
#   "total_days_supply": 40
# }
# Notice: MPR is NOT silently capped; 133.33% reflects true possession.
```

### 3. Detailed Metadata (Gaps & Covered Intervals)
```python
result = calculate_pdc(
    fills,
    start_date="2026-01-01",
    end_date="2026-01-30",
    include_metadata=True
)
print(result)
# Includes "gap_days", "gaps_count", and "covered_intervals"
```

### 4. Therapeutic Equivalence Mapping
```python
from adherence import calculate_pdc, DrugEquivalenceRule

statin_rule = DrugEquivalenceRule(
    target_drug="Atorvastatin",
    equivalent_drugs={"Rosuvastatin", "Simvastatin"}
)

fills = [
    {"fill_date": "2026-01-01", "days_supply": 15, "drug_name": "Atorvastatin"},
    {"fill_date": "2026-01-16", "days_supply": 15, "drug_name": "Rosuvastatin"},
    {"fill_date": "2026-01-20", "days_supply": 30, "drug_name": "Metformin"}, # Excluded
]

result = calculate_pdc(
    fills,
    start_date="2026-01-01",
    end_date="2026-01-30",
    equivalence_rule=statin_rule
)
```

---

## 📂 Project Structure

```
modawem_adherence/
├── src/
│   └── adherence/
│       ├── __init__.py           # Package exports
│       ├── pdc.py                # calculate_pdc (Interval-based stockpiling)
│       ├── mpr.py                # calculate_mpr (Standard fill-date & truncated)
│       ├── models.py             # PrescriptionFill, AdherenceResult, EquivalenceRule
│       └── utils.py              # Interval arithmetic, clipping, gap extractors
├── tests/
│   ├── __init__.py
│   ├── test_scenarios.py         # 10 hand-calculated clinical scenarios
│   ├── test_pdc.py               # PDC invariants, bounds, dual-method randomized test
│   ├── test_mpr.py               # MPR uncapped invariants, boundary dates, modes
│   └── test_performance.py       # Longitudinal 10-year scalability benchmarks
├── examples/
│   ├── basic_usage.py            # Quickstart demo script
│   ├── sample_input_output.json  # Comprehensive verified JSON test vectors
│   └── demo_cli.py               # CLI tool
├── docs/
│   ├── ADHERENCE_METHODOLOGY.md  # Detailed clinical & mathematical documentation
│   └── PR_DESCRIPTION.md         # Pull request description & review evidence
├── run_tests.py                  # One-command automated test runner
└── README.md                     # Project overview and reference manual
```

---

## 🔬 Hand-Calculated Scenarios Matrix

| Scenario | Observation Period | Fills Setup | PDC Result | MPR Result |
|---|---|---|---|---|
| **1. Full Coverage (Single)** | 31 days | Jan 1 (31d) | **100.0%** (31/31) | **100.0%** (31/31) |
| **2. Full Coverage (Sequential)** | 60 days | Jan 1 (30d), Jan 31 (30d) | **100.0%** (60/60) | **100.0%** (60/60) |
| **3. Partial Coverage** | 31 days | Jan 1 (15d) | **48.39%** (15/31) | **48.39%** (15/31) |
| **4. Gaps Between Refills** | 50 days | Jan 1 (20d), Feb 1 (15d) | **70.0%** (35/50) | **70.0%** (35/50) |
| **5. Overlapping & Stockpiling** | 30 days | Jan 1 (20d), Jan 15 (20d) | **100.0%** (30/30) | **133.33%** (40/30) |
| **6. Heavy Over-supply** | 20 days | Jan 1, 5, 10 (15d each) | **100.0%** (20/20) | **225.0%** (45/20) |
| **7. Boundaries (Start & End)** | 10 days | Jan 1 (3d), Jan 10 (5d) | **40.0%** (4/10) | **80.0%** (8/10) |
| **8. Zero Fills (Empty)** | 15 days | None | **0.0%** (0/15) | **0.0%** (0/15) |
| **9. Drug Equivalence** | 20 days | Statin + Eq Statin + Metformin | **100.0%** (20/20) | **100.0%** (20/20) |
| **10. Prior Fill Carry-over** | 31 days | Dec 25 (15d), Jan 20 (10d) | **58.06%** (18/31) | **32.26%** (10/31) |

---

## 🛡️ Acceptance Criteria Fulfillment
All 24 items in the Task 2 Definition of Done are verified, automated, and documented. See `docs/PR_DESCRIPTION.md` for the full audit report.
