"""Modawem Medication Adherence Package.

Provides deterministic, interval-based calculations for:
- Proportion of Days Covered (PDC)
- Medication Possession Ratio (MPR)
"""

from .models import AdherenceResult, DrugEquivalenceRule, PrescriptionFill
from .mpr import calculate_mpr
from .pdc import calculate_pdc
from .utils import (
    calculate_stockpiled_intervals,
    clip_intervals_to_window,
    extract_gaps_from_intervals,
    normalize_fills,
    parse_date,
    validate_observation_window,
)

__all__ = [
    "calculate_pdc",
    "calculate_mpr",
    "PrescriptionFill",
    "AdherenceResult",
    "DrugEquivalenceRule",
    "parse_date",
    "validate_observation_window",
    "normalize_fills",
    "calculate_stockpiled_intervals",
    "clip_intervals_to_window",
    "extract_gaps_from_intervals",
]
