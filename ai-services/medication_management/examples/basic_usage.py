"""Basic usage demonstration of Modawem Medication Adherence module."""

import json

from medication_management import DrugEquivalenceRule, calculate_mpr, calculate_pdc


def run_demo():
    print("=" * 70)
    print("1. Standard Sample Case (30 days supply in 40 days observation window)")
    print("=" * 70)
    fills = [{"fill_date": "2026-01-01", "days_supply": 30}]
    start_date = "2026-01-01"
    end_date = "2026-02-09"  # exactly 40 inclusive calendar days

    pdc_result = calculate_pdc(fills, start_date, end_date)
    mpr_result = calculate_mpr(fills, start_date, end_date)

    print("PDC Output:")
    print(json.dumps(pdc_result, indent=2))
    print("\nMPR Output:")
    print(json.dumps(mpr_result, indent=2))

    print("\n" + "=" * 70)
    print("2. Early Refill with Overlap & Stockpiling (PDC capped at 100%, MPR > 100%)")
    print("=" * 70)
    overlapping_fills = [
        {"fill_date": "2026-01-01", "days_supply": 20},
        {"fill_date": "2026-01-15", "days_supply": 20},
    ]
    obs_start = "2026-01-01"
    obs_end = "2026-01-30"  # 30 days

    pdc_stockpile = calculate_pdc(
        overlapping_fills, obs_start, obs_end, include_metadata=True
    )
    mpr_stockpile = calculate_mpr(overlapping_fills, obs_start, obs_end)

    print("PDC with Stockpiling Output:")
    print(json.dumps(pdc_stockpile, indent=2))
    print("\nMPR Output (Uncapped):")
    print(json.dumps(mpr_stockpile, indent=2))

    print("\n" + "=" * 70)
    print("3. Multi-Drug Regimen with Therapeutic Equivalence Rule")
    print("=" * 70)
    statin_fills = [
        {"fill_date": "2026-01-01", "days_supply": 15, "drug_name": "Atorvastatin"},
        {"fill_date": "2026-01-16", "days_supply": 15, "drug_name": "Rosuvastatin"},
        {
            "fill_date": "2026-01-20",
            "days_supply": 30,
            "drug_name": "Metformin",
        },  # Excluded
    ]
    statin_rule = DrugEquivalenceRule(
        target_drug="Atorvastatin",
        equivalent_drugs={"Rosuvastatin", "Simvastatin"},
    )
    pdc_multi = calculate_pdc(
        statin_fills, "2026-01-01", "2026-01-30", equivalence_rule=statin_rule
    )
    print("Equivalence Filtered PDC Output:")
    print(json.dumps(pdc_multi, indent=2))


if __name__ == "__main__":
    run_demo()
