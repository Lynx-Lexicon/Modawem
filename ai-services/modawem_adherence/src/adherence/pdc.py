"""Proportion of Days Covered (PDC) calculation module.

PDC is a pharmacy quality measure that estimates the proportion of days within
a defined observation window on which a patient has medication available.

Formula:
    PDC = (Number of unique covered days in observation window) / (Number of days in observation window)

Key rules implemented:
1. Each calendar day is counted at most once (PDC <= 100%).
2. Days outside the observation period are strictly excluded.
3. Overlapping refills of the same medication are handled using the stockpiling
   (push-forward) methodology: when refilled early, new supply start date shifts
   to the day after previous supply ends.
4. Different medications do not cover the target medication unless explicitly linked
   via a therapeutic equivalence rule.
5. Calculated via high-efficiency interval arithmetic (O(N log N)) without wasteful
   day-by-day looping over long date spans.
6. Boundaries use inclusive calendar dates [start_date, end_date].
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Union

from .models import AdherenceResult, DrugEquivalenceRule, PrescriptionFill
from .utils import (
    calculate_stockpiled_intervals,
    clip_intervals_to_window,
    extract_gaps_from_intervals,
    normalize_fills,
    validate_observation_window,
)


def calculate_pdc(
    fills: Iterable[Union[Dict[str, Any], PrescriptionFill]],
    start_date: Union[str, date, datetime],
    end_date: Union[str, date, datetime],
    target_drug: Optional[str] = None,
    equivalence_rule: Optional[DrugEquivalenceRule] = None,
    include_prior_fills: bool = True,
    as_dict: bool = True,
    include_metadata: bool = False,
) -> Union[Dict[str, Any], AdherenceResult]:
    """Calculates Proportion of Days Covered (PDC) over an inclusive observation window.

    Args:
        fills: List or iterable of fills. Each fill can be a dict with keys
            'fill_date' (ISO string or date) and 'days_supply' (positive int),
            or a PrescriptionFill dataclass.
        start_date: Start of observation window (inclusive).
        end_date: End of observation window (inclusive).
        target_drug: Optional drug name to filter fills by.
        equivalence_rule: Optional equivalence rule to allow multi-drug coverage.
        include_prior_fills: If True, fills occurring before start_date whose
            stockpiled supply extends into [start_date, end_date] contribute
            coverage days inside the window. If False, only fills with fill_date >= start_date
            are considered. Defaults to True.
        as_dict: If True (default), returns a dictionary matching the required deliverable.
            If False, returns an AdherenceResult object.
        include_metadata: If True, includes gaps_count, gap_days, and covered_intervals.

    Returns:
        Dictionary (or AdherenceResult) containing:
            - 'value': Float between 0.0 and 1.0 (full unrounded precision).
            - 'percentage': Float between 0.0 and 100.0 (rounded to 2 decimal places).
            - 'observation_days': Total days in observation period.
            - 'covered_days': Count of unique covered days within window.

    Raises:
        ValueError: On invalid dates, start_date > end_date, or days_supply <= 0.
        TypeError: On unsupported data types.

    Observation Boundary Rules:
        - Fill on first day (fill_date == start_date): Coverage begins on start_date.
          All days supply within [start_date, end_date] count toward covered_days.
        - Fill on last day (fill_date == end_date): Exactly 1 day (end_date itself)
          is covered within the observation window; the remaining days_supply - 1
          extend past end_date and are truncated (excluded).
        - Fill after end_date: Completely excluded from PDC.
    """
    # 1. Validate and compute observation window
    window_start, window_end, total_obs_days = validate_observation_window(
        start_date, end_date
    )

    # 2. Normalize and filter fills
    sorted_fills = normalize_fills(
        fills, target_drug=target_drug, equivalence_rule=equivalence_rule
    )

    # Filter out fills occurring after window_end (they can never cover days in window)
    relevant_fills = [f for f in sorted_fills if f.fill_date <= window_end]

    if not include_prior_fills:
        relevant_fills = [f for f in relevant_fills if f.fill_date >= window_start]

    # 3. Calculate stockpiled intervals (Interval-based O(N))
    all_intervals = calculate_stockpiled_intervals(relevant_fills)

    # 4. Clip intervals strictly to [window_start, window_end]
    clipped_intervals = clip_intervals_to_window(
        all_intervals, window_start, window_end
    )

    # 5. Calculate covered days
    covered_days = 0
    for s, e in clipped_intervals:
        covered_days += (e - s).days + 1

    # Safety check: PDC cannot exceed total observation days
    if covered_days > total_obs_days:
        covered_days = total_obs_days

    # 6. Compute metrics (no intermediate rounding)
    pdc_value = covered_days / total_obs_days if total_obs_days > 0 else 0.0
    # PDC is strictly bounded between 0.0 and 1.0
    pdc_value = min(1.0, max(0.0, pdc_value))
    pdc_percentage = round(pdc_value * 100.0, 2)

    # 7. Calculate gap information
    gap_intervals = extract_gaps_from_intervals(
        clipped_intervals, window_start, window_end
    )
    gap_days = total_obs_days - covered_days
    gaps_count = len(gap_intervals) if gap_days > 0 else 0

    result = AdherenceResult(
        metric="PDC",
        value=pdc_value,
        percentage=pdc_percentage,
        observation_days=total_obs_days,
        covered_days=covered_days,
        gaps_count=gaps_count,
        gap_days=gap_days,
        covered_intervals=[(s.isoformat(), e.isoformat()) for s, e in clipped_intervals],
    )

    if as_dict:
        return result.to_dict(include_metadata=include_metadata)
    return result
