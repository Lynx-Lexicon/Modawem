"""Dose-Weighted Adherence (DWA).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Literal, Optional, Union

from .models import AdherenceResult
from .utils import parse_date


UNKNOWN_IN_DENOMINATOR: bool = False
DWA_METRIC_NAME: str = "DWA"

Status = Literal["taken", "missed", "unknown"]


@dataclass(frozen=True)
class DoseRecord:
    """One dose event: taken, missed, or unknown."""
    day: Union[str, date]
    status: Status


def calculate_dose_weighted_adherence(
    records: Iterable[DoseRecord],
    required_per_day: Dict[Union[str, date], int],
) -> AdherenceResult:
    """Return a dose-weighted adherence score.

    score = total doses taken / total doses required, weighted by daily dose count.
    Days with 0 required doses are excluded.
    """
    errors: List[str] = []

    # 1. Normalize the schedule: {required>0}
    schedule: Dict[date, int] = {}
    for raw_day, n in required_per_day.items():
        try:
            day = parse_date(raw_day)
        except (ValueError, TypeError) as e:
            errors.append(f"Bad day {raw_day!r}: {e}")
            continue
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            errors.append(f"Bad required count for {day}: {n!r}")
            continue
        if n == 0:
            continue
        schedule[day] = n

    # 2. Tally doses per day
    taken: Dict[date, int] = {}
    unknown: Dict[date, int] = {}

    for rec in records:
        if not isinstance(rec, DoseRecord):
            errors.append(f"Not a DoseRecord: {rec!r}")
            continue
        try:
            day = parse_date(rec.day)
        except (ValueError, TypeError) as e:
            errors.append(f"Bad record day {rec.day!r}: {e}")
            continue
        if day not in schedule:
            errors.append(f"Record on non-scheduled day: {day}")
            continue
        if rec.status == "taken":
            taken[day] = taken.get(day, 0) + 1
        elif rec.status == "unknown":
            unknown[day] = unknown.get(day, 0) + 1
        elif rec.status == "missed":
            pass
        else:
            errors.append(f"Bad status {rec.status!r} on {day}")

    # 3. Aggregate with dose weighting
    doses_required = 0
    doses_taken = 0
    days_evaluated = 0

    for day, required in schedule.items():
        t = taken.get(day, 0)
        u = unknown.get(day, 0)

        if t + u > required:
            errors.append(f"{day}: taken+unknown > required; capping.")
            t = max(0, required - u)

        effective_required = required if UNKNOWN_IN_DENOMINATOR else max(0, required - u)
        if effective_required == 0:
            continue

        doses_required += effective_required
        doses_taken += t
        days_evaluated += 1

    # 4. Score
    if doses_required == 0:
        error_msg = "Cannot Calculate DWA: No Measurable Doses Found."
        if errors:
            error_msg += " | Details: " + "; ".join(errors)
        return AdherenceResult(
            metric=DWA_METRIC_NAME,
            is_valid=False,
            error_message=error_msg
        )

    value = doses_taken/doses_required
    percentage = round(value *100,2)

    is_valid = len(errors) == 0
    error_message = "; ".join(errors) if errors else None

    return AdherenceResult(
        metric=DWA_METRIC_NAME,
        value=value,
        percentage=percentage,
        observation_days=days_evaluated,
        is_valid=is_valid,
        error_message=error_message
    )