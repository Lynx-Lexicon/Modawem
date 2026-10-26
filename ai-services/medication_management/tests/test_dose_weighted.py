"""Unit tests for Dose-Weighted Adherence (DWA)"""

import unittest

from medication_management.dose_weighted import (
    DoseRecord,
    calculate_dose_weighted_adherence,
)


class TestDoseWeightedAdherence(unittest.TestCase):
    """Tests for the Dose-Weighted Adherence metric."""

    def test_perfect_adherence_single_dose(self):
        """Scenario: 100% adherence with 1 dose per day."""
        required = {"2026-01-01": 1, "2026-01-02": 1}
        records = [
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-02", status="taken"),
        ]
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertTrue(res.is_valid)
        self.assertEqual(res.observation_days, 2)
        self.assertEqual(res.value, 1.0)
        self.assertEqual(res.percentage, 100.0)

    def test_weighted_adherence_multiple_doses(self):
        """Scenario: The core Task 2 requirement. 
        
        A missed dose on a 3-dose day should impact the score differently 
        than a missed dose on a 1-dose day.
        
        Day 1: 3 required, 2 taken.
        Day 2: 1 required, 1 taken.
        Total required: 4. Total taken: 3. Score = 3/4 = 75%.
        """
        required = {"2026-01-01": 3, "2026-01-02": 1}
        records = [
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="missed"), # 1 missed
            DoseRecord(day="2026-01-02", status="taken"),
        ]
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertTrue(res.is_valid)
        self.assertEqual(res.observation_days, 2)
        self.assertAlmostEqual(res.value, 0.75)
        self.assertEqual(res.percentage, 75.0)

    def test_unknown_doses_are_excluded_from_denominator(self):
        """Scenario: Unknown doses should not penalize the patient.
        
        Day 1: 2 required. 1 taken, 1 unknown.
        The denominator should drop to 1 (since we don't know about the 2nd dose).
        Score = 1 / 1 = 100%.
        """
        required = {"2026-01-01": 2}
        records = [
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="unknown"),
        ]
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertTrue(res.is_valid)
        self.assertEqual(res.observation_days, 1)
        self.assertEqual(res.value, 1.0)
        self.assertEqual(res.percentage, 100.0)

    def test_zero_required_doses_are_excluded(self):
        """Scenario: Days with 0 required doses should not cause errors or affect math."""
        required = {"2026-01-01": 2, "2026-01-02": 0}
        records = [
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="taken"),
        ]
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertTrue(res.is_valid)
        # Jan 2 should be skipped entirely
        self.assertEqual(res.observation_days, 1)
        self.assertEqual(res.value, 1.0)

    def test_over_logging_is_capped(self):
        """Scenario: Patient logs more doses than required.
        
        Required: 2. Taken: 2, Unknown: 1. (Total 3 logged).
        The code should cap the 'taken' at 1 (2 required - 1 unknown).
        Score = 1 / 1 = 100%.
        """
        required = {"2026-01-01": 2}
        records = [
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="taken"),
            DoseRecord(day="2026-01-01", status="unknown"),
        ]
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertFalse(res.is_valid)
        self.assertEqual(res.value, 1.0)
        # The result should still contain the warning about capping
        self.assertIn("capping", res.error_message.lower())

    def test_no_measurable_doses_returns_invalid(self):
        """Scenario: The patient has no required doses at all."""
        required = {}
        records = []
        
        res = calculate_dose_weighted_adherence(records, required)
        
        self.assertFalse(res.is_valid)
        self.assertIn("no measurable doses", res.error_message.lower())

    def test_invalid_data_is_handled_gracefully(self):
        """Scenario: Invalid days, negative required doses, or bad statuses."""
        # Invalid required doses
        res = calculate_dose_weighted_adherence([], {"2026-01-01": -5})
        self.assertFalse(res.is_valid)
        self.assertIn("bad required count", res.error_message.lower())

        # Invalid record day
        res = calculate_dose_weighted_adherence(
            [DoseRecord(day="not-a-date", status="taken")], 
            {"2026-01-01": 1}
        )
        self.assertFalse(res.is_valid)
        self.assertIn("bad record day", res.error_message.lower())


if __name__ == "__main__":
    unittest.main()