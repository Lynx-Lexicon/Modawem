"""Unit tests and invariant verifications for MPR calculation."""

import unittest

from medication_management import calculate_mpr


class TestMPRInvariantsAndEdges(unittest.TestCase):
    """Rigorous invariant and edge-case testing for calculate_mpr."""

    def test_mpr_can_exceed_100_percent_no_silent_capping(self):
        """Invariant: MPR must NOT be capped at 1.0 / 100% when supply exceeds window."""
        start = "2026-01-01"
        end = "2026-01-30"  # 30 days
        # 60 days supply dispensed in the window
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 30},
            {"fill_date": "2026-01-15", "days_supply": 30},
        ]

        res = calculate_mpr(fills, start, end)
        self.assertEqual(res["observation_days"], 30)
        self.assertEqual(res["total_days_supply"], 60)
        self.assertEqual(res["value"], 2.0)
        self.assertEqual(res["percentage"], 200.0)
        self.assertGreater(res["value"], 1.0)
        self.assertGreater(res["percentage"], 100.0)

    def test_mpr_excludes_fills_outside_window(self):
        """Fills occurring strictly before start_date or after end_date are excluded."""
        start = "2026-02-01"
        end = "2026-02-28"  # 28 days

        fills = [
            {"fill_date": "2026-01-31", "days_supply": 30},  # Day before start
            {"fill_date": "2026-02-10", "days_supply": 14},  # Inside window
            {"fill_date": "2026-03-01", "days_supply": 30},  # Day after end
        ]

        res = calculate_mpr(fills, start, end)
        self.assertEqual(res["observation_days"], 28)
        self.assertEqual(res["total_days_supply"], 14)
        self.assertAlmostEqual(res["value"], 14 / 28)
        self.assertEqual(res["percentage"], 50.0)

    def test_mpr_boundary_dates_inclusive(self):
        """Fills on the exact start_date and exact end_date are both counted."""
        start = "2026-01-01"
        end = "2026-01-10"  # 10 days

        fills = [
            {"fill_date": "2026-01-01", "days_supply": 5},
            {"fill_date": "2026-01-10", "days_supply": 5},
        ]

        res = calculate_mpr(fills, start, end)
        self.assertEqual(res["observation_days"], 10)
        self.assertEqual(res["total_days_supply"], 10)
        self.assertEqual(res["value"], 1.0)
        self.assertEqual(res["percentage"], 100.0)

    def test_mpr_truncate_at_end_mode(self):
        """Tests optional Modified MPR where supply extending beyond window is truncated."""
        start = "2026-01-01"
        end = "2026-01-10"  # 10 days

        # Fill on Jan 8 with 10 days supply -> extends to Jan 17 (7 days beyond window)
        # Inside window: Jan 8, 9, 10 = 3 days.
        fills = [{"fill_date": "2026-01-08", "days_supply": 10}]

        # Standard rule: counts all 10 days
        std_res = calculate_mpr(fills, start, end, truncate_at_end=False)
        self.assertEqual(std_res["total_days_supply"], 10)
        self.assertEqual(std_res["value"], 1.0)

        # Truncated rule: counts 3 days
        trunc_res = calculate_mpr(fills, start, end, truncate_at_end=True)
        self.assertEqual(trunc_res["total_days_supply"], 3)
        self.assertAlmostEqual(trunc_res["value"], 0.3)

    def test_mpr_invalid_inputs(self):
        """Validation errors on bad inputs return is_valid=False gracefully."""
        # Test: Start date after end date
        res = calculate_mpr([], "2026-05-01", "2026-04-01")
        self.assertFalse(res["is_valid"])
        self.assertIn("cannot be after", res["error_message"])

        # Test: Negative days supply
        res = calculate_mpr(
            [{"fill_date": "2026-01-01", "days_supply": -10}],
            "2026-01-01",
            "2026-01-31",
        )
        self.assertFalse(res["is_valid"])
        self.assertIn("days_supply must be a positive integer", res["error_message"])


if __name__ == "__main__":
    unittest.main()
