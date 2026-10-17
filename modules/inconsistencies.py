"""Stable public API for inconsistency detection."""

from modules.inconsistency_detector import (
    detect_inconsistencies as _detect_inconsistencies,
)


def detect_inconsistencies(case_data: dict) -> dict:
    """Return potential inconsistencies in the agreed dictionary format."""
    return {"inconsistencies": _detect_inconsistencies(case_data)}


__all__ = ["detect_inconsistencies"]
