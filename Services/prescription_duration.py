"""Shared prescription duration parsing (doctor stores text e.g. '5 days')."""
from __future__ import annotations

import re

_DURATION_UNIT_RE = re.compile(r"(?i)\b(days?|weeks?|months?|years?)\b")
_DURATION_PARSE_RE = re.compile(
    r"(?i)^\s*(\d+)\s*(days?|weeks?|months?|years?)?\s*$"
)

# Approximate supply units when duration uses weeks/months/years.
_UNIT_TO_DAYS = {
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}


def normalize_duration(value) -> str:
    """
    Keep full duration text when unit is present.
    Bare numbers default to days (matches doctor prescription schema).
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        return f"{text} days"
    digits = "".join(c for c in text if c.isdigit())
    if digits and not _DURATION_UNIT_RE.search(text):
        return f"{digits} days"
    return text


def duration_to_supply_quantity(value) -> int:
    """
    Convert duration text to an integer supply quantity for pharmacy dispense limits.

    Uses day-equivalent units: 2 weeks -> 14, 1 month -> 30, bare 5 -> 5.
    """
    text = normalize_duration(value)
    if not text:
        return 1

    match = _DURATION_PARSE_RE.match(text)
    if match:
        amount = int(match.group(1))
        unit = (match.group(2) or "days").lower()
        multiplier = _UNIT_TO_DAYS.get(unit, 1)
        return max(amount * multiplier, 1)

    fallback = re.search(r"\d+", text)
    if fallback:
        return max(int(fallback.group()), 1)
    return 1
