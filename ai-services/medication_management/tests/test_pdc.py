"""Unit tests and invariant verifications for PDC calculation."""

import random
import unittest
from datetime import date, timedelta

from medication_management import calculate_pdc


class TestPDCInvariantsAndEdges(unittest.TestCase):
    """Rigorous invariant and edge-case testing for calculate_pdc."""

    def test_pdc_never_exceeds_100_percent(self):
        """Invariant: PDC must NEVER exceed 1.0 (100%), even with overwhelming supply."""
        start = "2026-01-01"
        end = "2026-01-10"  # 10 days
        # Supply of 365 days
        fills = [{"fill_date": "2026-01-01", "days_supply": 365}]

        res = calculate_pdc(fills, start, end)
        self.assertEqual(res["observation_days"], 10)
        self.assertEqual(res["covered_days"], 10)
        self.assertEqual(res["value"], 1.0)
        self.assertEqual(res["percentage"], 100.0)
        self.assertLessEqual(res["value"], 1.0)

    def test_pdc_days_outside_observation_period_excluded(self):
        """Days before start_date and after end_date must be strictly excluded."""
        start = "2026-02-01"
        end = "2026-02-10"  # 10 days in Feb

        # Fill 1 is strictly in Jan (finished Jan 25)
        # Fill 2 is in March (starts Mar 1)
        fills = [
            {"fill_date": "2026-01-01", "days_supply": 25},
            {"fill_date": "2026-03-01", "days_supply": 30},
        ]

        res = calculate_pdc(fills, start, end)
        self.assertEqual(res["covered_days"], 0)
        self.assertEqual(res["value"], 0.0)
        self.assertEqual(res["percentage"], 0.0)

    def test_invalid_observation_window_handled_gracefully(self):
        """start_date after end_date must return is_valid=False."""
        res = calculate_pdc([], "2026-02-01", "2026-01-01")
        self.assertFalse(res["is_valid"])
        self.assertIn("cannot be after", res["error_message"])

    def test_invalid_days_supply_handled_gracefully(self):
        """Non-positive days_supply must return is_valid=False."""
        res_zero = calculate_pdc(
            [{"fill_date": "2026-01-01", "days_supply": 0}],
            "2026-01-01",
            "2026-01-31",
        )
        self.assertFalse(res_zero["is_valid"])
        self.assertIn("days_supply must be a positive integer", res_zero["error_message"])

        res_neg = calculate_pdc(
            [{"fill_date": "2026-01-01", "days_supply": -5}],
            "2026-01-01",
            "2026-01-31",
        )
        self.assertFalse(res_neg["is_valid"])
        self.assertIn("days_supply must be a positive integer", res_neg["error_message"])

    def test_invalid_date_format_handled_gracefully(self):
        """Unparseable date string must return is_valid=False."""
        res = calculate_pdc(
            [{"fill_date": "not-a-date", "days_supply": 30}],
            "2026-01-01",
            "2026-01-31",
        )
        self.assertFalse(res["is_valid"])
        self.assertIn("Invalid date string", res["error_message"])

    def test_dual_method_verification_against_naive_daily_set(self):
        """Verifies interval method produces identical results to naive day-set iteration.

        Generates 20 distinct randomized fill patterns and verifies interval math matches
        exact naive calendar day-by-day simulation.
        """
        rng = random.Random(42)
        base_date = date(2026, 1, 1)

        for _ in range(20):
            obs_start = base_date + timedelta(days=rng.randint(0, 30))
            obs_len = rng.randint(15, 60)
            obs_end = obs_start + timedelta(days=obs_len - 1)

            # Generate 1 to 5 random fills
            fills = []
            for _ in range(rng.randint(1, 5)):
                f_date = obs_start + timedelta(days=rng.randint(-10, obs_len + 5))
                days_sup = rng.randint(5, 30)
                fills.append({"fill_date": f_date.isoformat(), "days_supply": days_sup})

            fills.sort(key=lambda x: x["fill_date"])

            # 1. Interval calculation under test
            res_interval = calculate_pdc(
                fills, obs_start, obs_end, include_prior_fills=True
            )

            # 2. Naive day-set simulation with stockpiling
            covered_days_set = set()
            cur_available = None
            for f in fills:
                fd = date.fromisoformat(f["fill_date"])
                ds = f["days_supply"]
                if cur_available is not None and fd < cur_available:
                    st = cur_available
                else:
                    st = fd
                for d in range(ds):
                    cov_d = st + timedelta(days=d)
                    if obs_start <= cov_d <= obs_end:
                        covered_days_set.add(cov_d)
                cur_available = st + timedelta(days=ds)

            expected_covered = len(covered_days_set)
            self.assertEqual(
                res_interval["covered_days"],
                expected_covered,
                f"Interval math {res_interval['covered_days']} != Naive set {expected_covered}",
            )


if __name__ == "__main__":
    unittest.main()
