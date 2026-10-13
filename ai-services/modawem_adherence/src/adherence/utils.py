"""Utility and validation routines for Medication Adherence calculations.

Provides robust, interval-based date arithmetic, data normalization,
and calendar date validation according to clinical pharmacy quality standards.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .models import DrugEquivalenceRule, PrescriptionFill


def parse_date(value: Union[str, date, datetime]) -> date:
    """Parses a date input into a standard datetime.date object.

    Args:
        value: ISO-8601 string ('YYYY-MM-DD'), datetime, or date object.

    Returns:
        datetime.date instance.

    Raises:
        ValueError: If the string format cannot be parsed or value is invalid.
        TypeError: If value is not a string, date, or datetime.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        # Common ISO format
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                pass
        # Fallback to date.fromisoformat (supports YYYY-MM-DD)
        try:
            return date.fromisoformat(cleaned)
        except ValueError as err:
            raise ValueError(
                f"Invalid date string '{value}'. Expected ISO format 'YYYY-MM-DD'."
            ) from err

    raise TypeError(
        f"Unsupported date type: {type(value).__name__}. Expected str, date, or datetime."
    )


def validate_observation_window(
    start_date: Union[str, date, datetime],
    end_date: Union[str, date, datetime],
) -> Tuple[date, date, int]:
    """Validates and normalizes observation window boundaries.

    Adopts inclusive calendar date convention:
    Both start_date and end_date are included in the observation period.

    Args:
        start_date: Start of observation period (inclusive).
        end_date: End of observation period (inclusive).

    Returns:
        Tuple of (parsed_start_date, parsed_end_date, total_observation_days).

    Raises:
        ValueError: If start_date is after end_date.
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    if start > end:
        raise ValueError(
            f"Observation start_date ({start}) cannot be after end_date ({end})."
        )

    # Inclusive calendar days count: (end - start).days + 1
    total_days = (end - start).days + 1
    return start, end, total_days


def normalize_fills(
    fills: Iterable[Union[Dict[str, Any], PrescriptionFill]],
    target_drug: Optional[str] = None,
    equivalence_rule: Optional[DrugEquivalenceRule] = None,
) -> List[PrescriptionFill]:
    """Normalizes and filters raw fill inputs into validated PrescriptionFill objects.

    Applies therapeutic equivalence rules:
    - If target_drug or equivalence_rule is specified, fills for different non-equivalent
      drugs are excluded from the calculation.
    - If neither is provided, all fills are assumed relevant to the adherence calculation.

    Args:
        fills: Iterable of dicts or PrescriptionFill instances.
        target_drug: Optional target drug name.
        equivalence_rule: Optional equivalence rule defining interchangeable drugs.

    Returns:
        List of PrescriptionFill objects sorted chronologically by fill_date.
    """
    eq_checker: Optional[DrugEquivalenceRule] = equivalence_rule
    if eq_checker is None and target_drug is not None:
        eq_checker = DrugEquivalenceRule(target_drug=target_drug)

    normalized: List[PrescriptionFill] = []

    for idx, item in enumerate(fills):
        if isinstance(item, PrescriptionFill):
            fill_obj = item
        elif isinstance(item, dict):
            if "fill_date" not in item:
                raise ValueError(f"Fill at index {idx} missing required key 'fill_date'.")
            if "days_supply" not in item:
                raise ValueError(f"Fill at index {idx} missing required key 'days_supply'.")

            parsed_d = parse_date(item["fill_date"])
            days_sup = item["days_supply"]
            if not isinstance(days_sup, int) or isinstance(days_sup, bool):
                try:
                    days_sup = int(days_sup)
                except (ValueError, TypeError) as err:
                    raise ValueError(
                        f"Fill at index {idx} has non-integer days_supply: {item['days_supply']}"
                    ) from err

            fill_obj = PrescriptionFill(
                fill_date=parsed_d,
                days_supply=days_sup,
                drug_name=item.get("drug_name"),
                quantity=item.get("quantity"),
                refills=item.get("refills"),
            )
        else:
            raise TypeError(
                f"Fill at index {idx} has unsupported type {type(item).__name__}. Expected dict or PrescriptionFill."
            )

        # Therapeutic equivalence check
        if eq_checker is not None:
            if not eq_checker.is_equivalent(fill_obj.drug_name):
                # Different medication not matching equivalence rule -> excluded
                continue

        normalized.append(fill_obj)

    # Sort strictly by fill_date
    normalized.sort(key=lambda f: f.fill_date)
    return normalized


def calculate_stockpiled_intervals(
    fills: List[PrescriptionFill],
) -> List[Tuple[date, date]]:
    """Calculates non-overlapping supply intervals using the same-medication stockpiling rule.

    Stockpiling / Push-Forward Method:
    If a patient refills before previous supply is exhausted, the patient is assumed
    to finish remaining supply first. The new supply start date is shifted forward
    to the calendar day immediately following the end of previous coverage.

    Algorithm complexity: O(N) after sorting, purely interval-based.

    Args:
        fills: Chronologically sorted list of PrescriptionFill objects.

    Returns:
        List of disjoint (interval_start, interval_end) tuples, where each interval
        represents contiguous days of medication coverage.
    """
    if not fills:
        return []

    intervals: List[Tuple[date, date]] = []
    # Tracks the next available day where new supply should begin if stockpiling occurs
    next_available_day: Optional[date] = None

    for fill in fills:
        # Determine actual coverage start for this fill
        if next_available_day is not None and fill.fill_date < next_available_day:
            # Overlap detected: push start to next available day
            start_dt = next_available_day
        else:
            # No overlap / gap occurred: starts on fill_date
            start_dt = fill.fill_date

        # Inclusive interval: start_dt + (days_supply - 1)
        end_dt = start_dt + timedelta(days=fill.days_supply - 1)
        next_available_day = end_dt + timedelta(days=1)

        # Merge contiguous intervals if abutting
        if intervals and intervals[-1][1] + timedelta(days=1) == start_dt:
            prev_start, _ = intervals.pop()
            intervals.append((prev_start, end_dt))
        else:
            intervals.append((start_dt, end_dt))

    return intervals


def clip_intervals_to_window(
    intervals: List[Tuple[date, date]],
    window_start: date,
    window_end: date,
) -> List[Tuple[date, date]]:
    """Clips a list of disjoint intervals strictly to [window_start, window_end].

    Any coverage days falling before window_start or after window_end are truncated.

    Args:
        intervals: List of disjoint (start, end) intervals.
        window_start: Inclusive window start date.
        window_end: Inclusive window end date.

    Returns:
        List of clipped disjoint (start, end) intervals strictly within window.
    """
    clipped: List[Tuple[date, date]] = []

    for start, end in intervals:
        eff_start = max(start, window_start)
        eff_end = min(end, window_end)

        if eff_start <= eff_end:
            clipped.append((eff_start, eff_end))

    return clipped


def extract_gaps_from_intervals(
    intervals: List[Tuple[date, date]],
    window_start: date,
    window_end: date,
) -> List[Tuple[date, date]]:
    """Identifies all uncovered date intervals (gaps) within the observation window.

    Args:
        intervals: List of clipped disjoint intervals within [window_start, window_end].
        window_start: Inclusive observation start.
        window_end: Inclusive observation end.

    Returns:
        List of (gap_start, gap_end) intervals where patient had no medication supply.
    """
    if not intervals:
        return [(window_start, window_end)]

    gaps: List[Tuple[date, date]] = []
    current_cursor = window_start

    for start, end in intervals:
        if start > current_cursor:
            # Gap exists between current_cursor and start - 1 day
            gaps.append((current_cursor, start - timedelta(days=1)))
        current_cursor = end + timedelta(days=1)

    if current_cursor <= window_end:
        gaps.append((current_cursor, window_end))

    return gaps
