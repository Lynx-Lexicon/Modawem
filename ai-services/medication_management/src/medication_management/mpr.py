"""Medication Possession Ratio (MPR) calculation module.

MPR is an adherence metric representing the ratio of the total days of medication
dispensed to the number of days in the observation window.

Formula:
    MPR = (Total days' supply dispensed) / (Number of days in observation period)

Key rules implemented:
1. Dispensed supply within the observation window is calculated according to the
   standard fill-date rule (fills with fill_date in [start_date, end_date] inclusive).
2. Unlike PDC, MPR CAN EXCEED 100% (e.g. when patients refill early or accumulate supply).
3. No silent capping: MPR is NEVER capped at 1.0 / 100%.
4. Boundary rule:
   - Fill on start_date: Counted in dispensed supply.
   - Fill on end_date: Counted in dispensed supply (fill_date falls on the boundary).
   - Optional truncated mode available for comparative studies.
5. Equivalence rules supported: Supply from a different medication is excluded
   unless explicitly mapped via therapeutic equivalence.
6. Boundaries use inclusive calendar dates [start_date, end_date].
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Union

from .models import AdherenceResult, DrugEquivalenceRule, PrescriptionFill
from .utils import (
    normalize_fills,
    validate_observation_window,
)


def calculate_mpr(
    fills: Iterable[Union[Dict[str, Any], PrescriptionFill]],
    start_date: Union[str, date, datetime],
    end_date: Union[str, date, datetime],
    target_drug: Optional[str] = None,
    equivalence_rule: Optional[DrugEquivalenceRule] = None,
    truncate_at_end: bool = False,
    as_dict: bool = True,
    include_metadata: bool = False,
) -> Union[Dict[str, Any], AdherenceResult]:
    """Calculates Medication Possession Ratio (MPR) over an inclusive observation window.

    Args:
        fills: List or iterable of fills. Each fill can be a dict with keys
            'fill_date' (ISO string or date) and 'days_supply' (positive int),
            or a PrescriptionFill dataclass.
        start_date: Start of observation window (inclusive).
        end_date: End of observation window (inclusive).
        target_drug: Optional drug name to filter fills by.
        equivalence_rule: Optional equivalence rule to allow multi-drug coverage.
        truncate_at_end: If True, truncates supply extending past end_date
            (Modified/Truncated MPR). If False (default standard fill-date rule),
            counts full days_supply for all fills occurring within [start_date, end_date].
        as_dict: If True (default), returns a dictionary matching the required deliverable.
            If False, returns an AdherenceResult object.
        include_metadata: If True, includes fill count and breakdown metadata.

    Returns:
        Dictionary (or AdherenceResult) containing:
            - 'value': Float >= 0.0 (full unrounded precision, CAN EXCEED 1.0).
            - 'percentage': Float >= 0.0 (rounded to 2 decimal places, CAN EXCEED 100.0%).
            - 'observation_days': Total days in observation period.
            - 'total_days_supply': Total days of medication supply dispensed.

    Raises:
        ValueError: On invalid dates, start_date > end_date, or days_supply <= 0.
        TypeError: On unsupported data types.

    Observation Boundary & Overlap Rules:
        - Fill on first day (fill_date == start_date): Included in dispensed supply.
        - Fill on last day (fill_date == end_date): Included in dispensed supply.
        - Fills before start_date or after end_date: Excluded under fill-date rule.
        - Overlapping fills: MPR does not deduplicate days; days are summed directly,
          allowing MPR to accurately reflect total dispensed possession ratio > 100%.
    """
    # 1. Validate and compute observation window
    window_start, window_end, total_obs_days = validate_observation_window(
        start_date, end_date
    )

    # 2. Normalize and filter fills
    sorted_fills = normalize_fills(
        fills, target_drug=target_drug, equivalence_rule=equivalence_rule
    )

    # 3. Sum days' supply dispensed inside observation period (fill-date rule)
    total_days_supply = 0
    qualifying_fills_count = 0

    for fill in sorted_fills:
        if window_start <= fill.fill_date <= window_end:
            qualifying_fills_count += 1
            if truncate_at_end:
                # Truncate supply extending beyond window_end
                # Days from fill_date to window_end inclusive
                days_until_end = (window_end - fill.fill_date).days + 1
                effective_supply = min(fill.days_supply, days_until_end)
                total_days_supply += effective_supply
            else:
                total_days_supply += fill.days_supply

    # 4. Compute metrics without intermediate rounding
    mpr_value = total_days_supply / total_obs_days if total_obs_days > 0 else 0.0
    # Note: MPR is NEVER capped at 1.0 / 100%
    mpr_percentage = round(mpr_value * 100.0, 2)

    result = AdherenceResult(
        metric="MPR",
        value=mpr_value,
        percentage=mpr_percentage,
        observation_days=total_obs_days,
        total_days_supply=total_days_supply,
    )

    if as_dict:
        res_dict = result.to_dict(include_metadata=include_metadata)
        if include_metadata:
            res_dict["qualifying_fills_count"] = qualifying_fills_count
            res_dict["truncate_at_end"] = truncate_at_end
        return res_dict

    return result
