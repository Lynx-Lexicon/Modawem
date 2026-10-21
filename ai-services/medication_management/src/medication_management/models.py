"""Data models and structures for Medication Adherence calculation (PDC & MPR).

This module defines type-safe data containers for prescription fills,
equivalence rules, and adherence calculation results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple


def validate_days_supply(value: Any) -> int:
    """Validate a days_supply value without coercing it."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"days_supply must be a positive integer, got {value!r} "
            f"({type(value).__name__})."
        )
    if value <= 0:
        raise ValueError(
            f"days_supply must be a positive integer greater than 0, got {value}."
        )
    return value


def validate_drug_name(value: Optional[str]) -> Optional[str]:
    """Validate an optional medication name without coercing it."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(
            f"drug_name must be a non-empty string or None, got {value!r} "
            f"({type(value).__name__})."
        )
    if not value.strip():
        raise ValueError("drug_name cannot be empty or whitespace-only.")
    return value


@dataclass(frozen=True)
class PrescriptionFill:
    """Represents a single medication dispensing / refill event.

    Attributes:
        fill_date: The calendar date the medication was dispensed.
        days_supply: Number of days of medication provided (must be > 0).
        drug_name: Optional medication name or NDC code.
        quantity: Optional number of units dispensed.
        refills: Optional remaining refills.
    """

    fill_date: date
    days_supply: int
    drug_name: Optional[str] = None
    quantity: Optional[float] = None
    refills: Optional[int] = None

    def __post_init__(self) -> None:
        validate_days_supply(self.days_supply)
        validate_drug_name(self.drug_name)


@dataclass
class AdherenceResult:
    """Standardized output container for adherence metrics.

    Maintains unrounded high-precision values internally while providing
    formatted percentage presentation and complete JSON serialization.

    Attributes:
        metric: Metric name ('PDC' or 'MPR').
        value: Full floating-point precision adherence ratio (e.g., 0.8333333333).
        percentage: Presentation-ready percentage rounded to 2 decimal places (e.g., 83.33).
        observation_days: Total calendar days in the observation window [start_date, end_date] inclusive.
        covered_days: Number of unique days covered by medication supply (PDC only).
        total_days_supply: Total sum of days' supply dispensed (MPR only).
        gaps_count: Number of distinct uncovered gap intervals within observation window.
        gap_days: Total number of uncovered calendar days within observation window.
        covered_intervals: List of (start, end) date intervals covering the period.
    """

    metric: str
    value: float = 0.0
    percentage: float = 0.0
    observation_days: int = 0
    covered_days: Optional[int] = None
    total_days_supply: Optional[int] = None
    gaps_count: Optional[int] = None
    gap_days: Optional[int] = None
    covered_intervals: List[Tuple[str, str]] = field(default_factory=list)
    #Error handling fields
    is_valid: bool = True
    error_message: Optional[str] = None

    def to_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        """Convert result to dictionary matching the required deliverable shape.

        Args:
            include_metadata: If True, include detailed gap and interval breakdown.
        """
        if not self.is_valid:
            return {
                "is_valid": False,
                "error_message": self.error_message,
                "metric": self.metric
            }
        
        base: Dict[str, Any] = {
            "is_valid":True,
            "value": self.value,
            "percentage": self.percentage,
            "observation_days": self.observation_days,
        }

        if self.metric == "PDC":
            base["covered_days"] = self.covered_days
        elif self.metric == "MPR":
            base["total_days_supply"] = self.total_days_supply

        if include_metadata:
            base["metric"] = self.metric
            if self.gap_days is not None:
                base["gap_days"] = self.gap_days
            if self.gaps_count is not None:
                base["gaps_count"] = self.gaps_count
            if self.covered_intervals:
                base["covered_intervals"] = self.covered_intervals

        return base

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like subscript access for backward compatibility."""
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


@dataclass
class DrugEquivalenceRule:
    """Defines which drug names/identifiers are therapeutically equivalent.

    Rule:
    Supply from a different medication is not considered coverage for the target
    medication unless an explicit equivalence rule connects them.
    """

    target_drug: str
    equivalent_drugs: Set[str] = field(default_factory=set)

    def is_equivalent(self, candidate_drug: Optional[str]) -> bool:
        """Check if candidate drug is equivalent to target."""
        if candidate_drug is None:
            # A fill with no drug name cannot be assumed to be the target drug.
            return False
        norm_target = self.target_drug.strip().lower()
        norm_candidate = candidate_drug.strip().lower()
        if norm_candidate == norm_target:
            return True
        return norm_candidate in {d.strip().lower() for d in self.equivalent_drugs}
