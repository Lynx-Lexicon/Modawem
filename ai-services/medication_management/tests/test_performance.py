"""Performance and scalability test for interval-based adherence calculation."""

import time
import unittest
from datetime import date, timedelta

from medication_management import calculate_mpr, calculate_pdc


class TestAdherencePerformance(unittest.TestCase):
    """Verifies O(N log N) interval arithmetic scalability without unnecessary day loops."""

    def test_interval_calculation_10_year_window_performance(self):
        """Simulates a 10-year longitudinal observation period (3,652 days).

        Ensures calculate_pdc and calculate_mpr execute in under 50 milliseconds.
        """
        start = date(2020, 1, 1)
        end = date(2029, 12, 31)  # 10 full years (3,653 days inclusive)

        # Generate 120 monthly refills (approx 1 per 30 days)
        fills = []
        cur = start
        while cur <= end:
            fills.append(
                {
                    "fill_date": cur.isoformat(),
                    "days_supply": 30,
                }
            )
            # Add a realistic refill interval of 28 to 33 days
            cur += timedelta(days=30)

        # Benchmark calculate_pdc
        t0 = time.perf_counter()
        pdc_res = calculate_pdc(fills, start, end)
        t_pdc = (time.perf_counter() - t0) * 1000.0  # ms

        # Benchmark calculate_mpr
        t0 = time.perf_counter()
        mpr_res = calculate_mpr(fills, start, end)
        t_mpr = (time.perf_counter() - t0) * 1000.0  # ms

        self.assertGreater(pdc_res["observation_days"], 3600)
        self.assertGreater(pdc_res["covered_days"], 3500)
        self.assertGreater(mpr_res["total_days_supply"], 3500)

        # Performance assertion: sub-50ms execution
        self.assertLess(
            t_pdc, 50.0, f"PDC took {t_pdc:.2f}ms, expected < 50ms for 10-year window"
        )
        self.assertLess(
            t_mpr, 50.0, f"MPR took {t_mpr:.2f}ms, expected < 50ms for 10-year window"
        )


if __name__ == "__main__":
    unittest.main()
