"""Cashless insurance split: what the insurer covers and what the patient owes.

Pure functions only, so billing, discharge, and payment history share one rule.
"""
from __future__ import annotations

from typing import Optional


def _money(value) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def coverage_limit(approved, estimate, claimed) -> tuple[float, Optional[str]]:
    """Coverage limit and where it came from: approved, then estimate, then claimed."""
    for source, value in (
        ("approved", approved),
        ("estimate", estimate),
        ("claimed", claimed),
    ):
        amount = _money(value)
        if amount > 0:
            return amount, source
    return 0.0, None


def insurance_split(
    bill_total,
    *,
    approved=0,
    estimate=None,
    claimed=0,
    patient_paid=0,
) -> dict:
    """Insurer share is min(bill, limit). The patient owes the rest, less what they paid."""
    bill = max(_money(bill_total), 0.0)
    limit, source = coverage_limit(approved, estimate, claimed)
    insurance_share = round(min(bill, limit), 2)
    patient_share = round(max(bill - insurance_share, 0.0), 2)
    paid = max(_money(patient_paid), 0.0)
    return {
        "bill_total": bill,
        "coverage_limit": limit,
        "coverage_source": source,
        "insurance_share": insurance_share,
        "patient_share": patient_share,
        "patient_paid": paid,
        "patient_balance": round(max(patient_share - paid, 0.0), 2),
    }


def coverage_status(insurance_share, insurer_received) -> str:
    """paid, partly_paid, or pending — based on money actually received from the insurer."""
    share = _money(insurance_share)
    received = max(_money(insurer_received), 0.0)
    if share > 0 and received >= share - 0.01:
        return "paid"
    if received > 0.009:
        return "partly_paid"
    return "pending"
