"""Hand-calculated clinical test scenarios for Medication Adherence (PDC & MPR).

This suite validates at least 8 explicitly documented and hand-calculated scenarios
covering:
1. Full coverage (single fill)
2. Full coverage (multiple sequential fills)
3. Partial coverage (under-adherence)
4. Gaps between refills
5. Overlapping fills (stockpiling push-forward, MPR > 100%)
6. Heavy over-supply (MPR >> 100%, PDC strictly 100%)
7. Observation boundaries (fill on start date, fill on end date)
8. Zero fills (completely uncovered)
9. Therapeutic equivalence rule filtering
10. Prior fill carry-over into observation window
"""

import sys
import unittest
from pathlib import Path

# Add src to path for direct test execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from adherence import DrugEquivalenceRule, calculate_mpr, calculate_pdc


class TestHandCalculatedScenarios(unittest.TestCase):
    """Test cases verified against manual mathematical calculations."""

    def test_scenario_1_full_coverage_single_fill(self):
        """Scenario 1: Full Coverage - Single Fill.

        Observation Period: 2026-01-01 to 2026-01-31 (31 calendar days).
        Fills:
            - 2026-01-01: 31 days supply (covers Jan 1 to Jan 31).
        Manual Calculation:
            - Observation Days = 31
            - Covered Days = 31
            - PDC = 31 / 31 = 1.0 (100.0%)
            - Total Days Dispensed = 31
            - MPR = 31 / 31 = 1.0 (100.0%)
        """
        start = "2026-01-01"
        end = "2026-01-31"
        fills = [{"fill_date": "2026-01-01", "days_supply": 31}]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 31)
        self.assertEqual(pdc["covered_days"], 31)
        self.assertAlmostEqual(pdc["value"], 1.0)
        self.assertEqual(pdc["percentage"], 100.0)

        self.assertEqual(mpr["observation_days"], 31)
        self.assertEqual(mpr["total_days_supply"], 31)
        self.assertAlmostEqual(mpr["value"], 1.0)
        self.assertEqual(mpr["percentage"], 100.0)

    def test_scenario_2_full_coverage_sequential_fills(self):
        """Scenario 2: Full Coverage - Multiple Sequential Fills (No Overlap, No Gaps).

        Observation Period: 2026-01-01 to 2026-03-01 (60 calendar days: 31 Jan + 28 Feb + 1 Mar).
        Fills:
            - Fill 1: 2026-01-01, 30 days supply -> covers 2026-01-01 to 2026-01-30 (30 days).
            - Fill 2: 2026-01-31, 30 days supply -> covers 2026-01-31 to 2026-03-01 (30 days).
        Manual Calculation:
            - Observation Days = 60
            - Covered Days = 30 + 30 = 60
            - PDC = 60 / 60 = 1.0 (100.0%)
            - Total Days Dispensed = 60
            - MPR = 60 / 60 = 1.0 (100.0%)
        """
        start = "2026-01-01"
        end = "2026-03-01"
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 30},
            {"fill_date": "2026-01-31", "days_supply": 30},
        ]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 60)
        self.assertEqual(pdc["covered_days"], 60)
        self.assertAlmostEqual(pdc["value"], 1.0)
        self.assertEqual(pdc["percentage"], 100.0)

        self.assertEqual(mpr["observation_days"], 60)
        self.assertEqual(mpr["total_days_supply"], 60)
        self.assertAlmostEqual(mpr["value"], 1.0)
        self.assertEqual(mpr["percentage"], 100.0)

    def test_scenario_3_partial_coverage(self):
        """Scenario 3: Partial Coverage (Under-adherence / single short fill).

        Observation Period: 2026-01-01 to 2026-01-31 (31 calendar days).
        Fills:
            - 2026-01-01: 15 days supply -> covers Jan 1 to Jan 15.
        Manual Calculation:
            - Observation Days = 31
            - Covered Days = 15
            - PDC = 15 / 31 = 0.4838709677419355 (48.39%)
            - Total Days Dispensed = 15
            - MPR = 15 / 31 = 0.4838709677419355 (48.39%)
        """
        start = "2026-01-01"
        end = "2026-01-31"
        fills = [{"fill_date": "2026-01-01", "days_supply": 15}]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 31)
        self.assertEqual(pdc["covered_days"], 15)
        self.assertAlmostEqual(pdc["value"], 15 / 31)
        self.assertEqual(pdc["percentage"], 48.39)

        self.assertEqual(mpr["observation_days"], 31)
        self.assertEqual(mpr["total_days_supply"], 15)
        self.assertAlmostEqual(mpr["value"], 15 / 31)
        self.assertEqual(mpr["percentage"], 48.39)

    def test_scenario_4_gaps_between_refills(self):
        """Scenario 4: Gaps Between Refills (Delayed refill).

        Observation Period: 2026-01-01 to 2026-02-19 (50 calendar days: 31 Jan + 19 Feb).
        Fills:
            - Fill 1: 2026-01-01, 20 days supply -> covers Jan 1 to Jan 20 (20 days).
            - Gap 1: Jan 21 to Jan 31 (11 uncovered days).
            - Fill 2: 2026-02-01, 15 days supply -> covers Feb 1 to Feb 15 (15 days).
            - Gap 2: Feb 16 to Feb 19 (4 uncovered days).
        Manual Calculation:
            - Observation Days = 50
            - Covered Days = 20 + 15 = 35 days
            - Total Gap Days = 11 + 4 = 15 days
            - PDC = 35 / 50 = 0.70 (70.0%)
            - Total Days Dispensed = 35
            - MPR = 35 / 50 = 0.70 (70.0%)
        """
        start = "2026-01-01"
        end = "2026-02-19"
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 20},
            {"fill_date": "2026-02-01", "days_supply": 15},
        ]

        pdc = calculate_pdc(fills, start, end, include_metadata=True)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 50)
        self.assertEqual(pdc["covered_days"], 35)
        self.assertEqual(pdc["gap_days"], 15)
        self.assertEqual(pdc["gaps_count"], 2)
        self.assertAlmostEqual(pdc["value"], 0.70)
        self.assertEqual(pdc["percentage"], 70.0)

        self.assertEqual(mpr["observation_days"], 50)
        self.assertEqual(mpr["total_days_supply"], 35)
        self.assertAlmostEqual(mpr["value"], 0.70)
        self.assertEqual(mpr["percentage"], 70.0)

    def test_scenario_5_overlapping_fills_stockpiling(self):
        """Scenario 5: Overlapping Fills with Stockpiling.

        Observation Period: 2026-01-01 to 2026-01-30 (30 calendar days).
        Fills:
            - Fill 1: 2026-01-01, 20 days supply -> covers Jan 1 to Jan 20 (20 days).
            - Fill 2: 2026-01-15, 20 days supply.
              Stockpiling rule shifts Fill 2 start to 2026-01-21 (after Fill 1 ends).
              Fill 2 covers Jan 21 to Feb 9 (20 days).
              Within observation window (ending Jan 30): Jan 21 to Jan 30 = 10 days.
              10 days extend beyond observation window into February.
        Manual Calculation:
            - Observation Days = 30
            - PDC Covered Days in window = 20 (Fill 1) + 10 (Fill 2) = 30 days.
            - PDC = 30 / 30 = 1.0 (100.0%) [Strictly capped at 100%].
            - Total Days Dispensed in period = 20 + 20 = 40 days.
            - MPR = 40 / 30 = 1.3333333333333333 (133.33%).
            - Demonstrates: MPR exceeds 100%, while PDC remains capped at 100%.
        """
        start = "2026-01-01"
        end = "2026-01-30"
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 20},
            {"fill_date": "2026-01-15", "days_supply": 20},
        ]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 30)
        self.assertEqual(pdc["covered_days"], 30)
        self.assertAlmostEqual(pdc["value"], 1.0)
        self.assertEqual(pdc["percentage"], 100.0)

        self.assertEqual(mpr["observation_days"], 30)
        self.assertEqual(mpr["total_days_supply"], 40)
        self.assertAlmostEqual(mpr["value"], 40 / 30)
        self.assertEqual(mpr["percentage"], 133.33)
        self.assertGreater(mpr["value"], 1.0, "MPR must exceed 1.0 when over-supplied.")

    def test_scenario_6_heavy_over_supply(self):
        """Scenario 6: Significant Over-supply (Multiple overlapping fills).

        Observation Period: 2026-01-01 to 2026-01-20 (20 calendar days).
        Fills:
            - Fill 1: 2026-01-01, 15 days supply (Jan 1 to Jan 15).
            - Fill 2: 2026-01-05, 15 days supply (shifts to Jan 16 to Jan 30).
            - Fill 3: 2026-01-10, 15 days supply (shifts to Jan 31 to Feb 14).
        Manual Calculation:
            - Observation Days = 20
            - PDC Covered Days in window = 20 (All days Jan 1 to Jan 20 covered).
            - PDC = 20 / 20 = 1.0 (100.0%).
            - MPR Total Days Dispensed = 15 + 15 + 15 = 45 days.
            - MPR = 45 / 20 = 2.25 (225.0%).
        """
        start = "2026-01-01"
        end = "2026-01-20"
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 15},
            {"fill_date": "2026-01-05", "days_supply": 15},
            {"fill_date": "2026-01-10", "days_supply": 15},
        ]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 20)
        self.assertEqual(pdc["covered_days"], 20)
        self.assertEqual(pdc["value"], 1.0)
        self.assertEqual(pdc["percentage"], 100.0)

        self.assertEqual(mpr["observation_days"], 20)
        self.assertEqual(mpr["total_days_supply"], 45)
        self.assertEqual(mpr["value"], 2.25)
        self.assertEqual(mpr["percentage"], 225.0)

    def test_scenario_7_boundary_fills(self):
        """Scenario 7: Observation Boundaries (Fill on start date and fill on end date).

        Observation Period: 2026-01-01 to 2026-01-10 (10 calendar days).
        Fills:
            - Fill 1 (first day): 2026-01-01, 3 days supply -> covers Jan 1, 2, 3 (3 days).
            - Fill 2 (last day):  2026-01-10, 5 days supply -> covers Jan 10..14.
              In observation window, only Jan 10 is inside (1 day). Days 11..14 are truncated.
            - Uncovered Gap: Jan 4 to Jan 9 (6 days).
        Manual Calculation:
            - Observation Days = 10
            - PDC Covered Days = 3 (Jan 1..3) + 1 (Jan 10) = 4 days.
            - PDC = 4 / 10 = 0.40 (40.0%).
            - MPR Total Days Dispensed in period (fill-date rule) = 3 + 5 = 8 days.
            - MPR = 8 / 10 = 0.80 (80.0%).
        """
        start = "2026-01-01"
        end = "2026-01-10"
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 3},
            {"fill_date": "2026-01-10", "days_supply": 5},
        ]

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 10)
        self.assertEqual(pdc["covered_days"], 4)
        self.assertAlmostEqual(pdc["value"], 0.40)
        self.assertEqual(pdc["percentage"], 40.0)

        self.assertEqual(mpr["observation_days"], 10)
        self.assertEqual(mpr["total_days_supply"], 8)
        self.assertAlmostEqual(mpr["value"], 0.80)
        self.assertEqual(mpr["percentage"], 80.0)

    def test_scenario_8_zero_fills(self):
        """Scenario 8: Completely Uncovered / Zero Fills.

        Observation Period: 2026-01-01 to 2026-01-15 (15 calendar days).
        Fills: [] (empty list).
        Manual Calculation:
            - Observation Days = 15
            - Covered Days = 0
            - PDC = 0 / 15 = 0.0 (0.0%)
            - Total Days Dispensed = 0
            - MPR = 0 / 15 = 0.0 (0.0%)
        """
        start = "2026-01-01"
        end = "2026-01-15"
        fills = []

        pdc = calculate_pdc(fills, start, end)
        mpr = calculate_mpr(fills, start, end)

        self.assertEqual(pdc["observation_days"], 15)
        self.assertEqual(pdc["covered_days"], 0)
        self.assertEqual(pdc["value"], 0.0)
        self.assertEqual(pdc["percentage"], 0.0)

        self.assertEqual(mpr["observation_days"], 15)
        self.assertEqual(mpr["total_days_supply"], 0)
        self.assertEqual(mpr["value"], 0.0)
        self.assertEqual(mpr["percentage"], 0.0)

    def test_scenario_9_drug_equivalence_rule(self):
        """Scenario 9: Therapeutic Equivalence Rule.

        Observation Period: 2026-01-01 to 2026-01-20 (20 calendar days).
        Fills:
            - Fill 1: 2026-01-01, 10 days supply, drug: "Atorvastatin" (Target).
            - Fill 2: 2026-01-11, 10 days supply, drug: "Rosuvastatin" (Equivalent Statin).
            - Fill 3: 2026-01-15, 10 days supply, drug: "Metformin" (Non-equivalent Antidiabetic).
        Manual Calculation:
            - Equivalence rule permits "Rosuvastatin" to cover "Atorvastatin".
            - "Metformin" is excluded.
            - Fills 1 & 2 cover Jan 1 to Jan 20 (20 days).
            - PDC = 20 / 20 = 1.0 (100.0%).
            - MPR dispensed (Statin only) = 10 + 10 = 20 days. MPR = 20 / 20 = 1.0 (100.0%).
        """
        start = "2026-01-01"
        end = "2026-01-20"
        statin_rule = DrugEquivalenceRule(
            target_drug="Atorvastatin",
            equivalent_drugs={"Rosuvastatin", "Simvastatin"},
        )
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "Atorvastatin"},
            {"fill_date": "2026-01-11", "days_supply": 10, "drug_name": "Rosuvastatin"},
            {"fill_date": "2026-01-15", "days_supply": 10, "drug_name": "Metformin"},
        ]

        pdc = calculate_pdc(fills, start, end, equivalence_rule=statin_rule)
        mpr = calculate_mpr(fills, start, end, equivalence_rule=statin_rule)

        self.assertEqual(pdc["covered_days"], 20)
        self.assertEqual(pdc["percentage"], 100.0)
        self.assertEqual(mpr["total_days_supply"], 20)
        self.assertEqual(mpr["percentage"], 100.0)

    def test_scenario_10_prior_fill_carry_over(self):
        """Scenario 10: Prior Fill Carry-over into Observation Window.

        Observation Period: 2026-01-01 to 2026-01-31 (31 calendar days).
        Fills:
            - Fill 1: 2025-12-25, 15 days supply (Dec 25 to Jan 8).
              Days Dec 25..31 are outside window. Days Jan 1..8 (8 days) fall inside window.
            - Fill 2: 2026-01-20, 10 days supply (Jan 20 to Jan 29).
        Manual Calculation:
            - Observation Days = 31
            - Covered Days inside window = 8 (from Fill 1) + 10 (from Fill 2) = 18 days.
            - PDC = 18 / 31 = 0.5806451612903226 (58.06%).
        """
        start = "2026-01-01"
        end = "2026-01-31"
        fills = [
            {"fill_date": "2025-12-25", "days_supply": 15},
            {"fill_date": "2026-01-20", "days_supply": 10},
        ]

        pdc = calculate_pdc(fills, start, end, include_prior_fills=True)
        self.assertEqual(pdc["covered_days"], 18)
        self.assertAlmostEqual(pdc["value"], 18 / 31)
        self.assertEqual(pdc["percentage"], 58.06)


if __name__ == "__main__":
    unittest.main()
