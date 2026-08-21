"""Lightweight checks for receptionist board helpers (no DB required)."""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Models.opd_billing import AppointmentStatus
from Services.receptionist_service import (
    _canonical_group_key,
    _canonical_rank,
    _dedupe_canonical_rows,
    _filter_canonical_rows,
    _paginate_rows,
)

IST = ZoneInfo("Asia/Kolkata")


def _apt(pid, did, apt_id, hour=10, status=AppointmentStatus.scheduled):
    return SimpleNamespace(
        id=apt_id,
        patient_id=pid,
        doctor_id=did,
        status=status,
        scheduled_at=datetime(2026, 8, 12, hour, 0, tzinfo=IST),
    )


def _visit(paid=True):
    return SimpleNamespace(
        payment_status="paid" if paid else "pending",
        grand_total=500.0,
        appointment_id=None,
    )


def test_dedupe_prefers_paid_same_patient_doctor_day():
    unpaid = (_apt(1, 5, 10, hour=9), None, None, None, None, None)
    paid = (_apt(1, 5, 11, hour=14), None, _visit(True), None, None, None)
    out = _dedupe_canonical_rows([unpaid, paid])
    assert len(out) == 1
    assert out[0][0].id == 11


def test_canonical_rank_paid_beats_unpaid():
    a = _apt(1, 5, 1)
    assert _canonical_rank(a, _visit(True)) > _canonical_rank(a, _visit(False))
    assert _canonical_rank(a, _visit(True)) > _canonical_rank(a, None)


def test_filter_payment_and_paginate():
    rows = [
        (_apt(1, 1, 1), None, _visit(True), None, None, None),
        (_apt(2, 1, 2), None, None, None, None, None),
        (_apt(3, 1, 3), None, _visit(False), None, None, None),
    ]
    paid = _filter_canonical_rows(rows, payment_filter="paid")
    unpaid = _filter_canonical_rows(rows, payment_filter="unpaid")
    assert len(paid) == 1
    assert len(unpaid) == 2
    page, total, p, lim = _paginate_rows(
        unpaid, 1, 1, sort_key=lambda r: (r[0].scheduled_at, r[0].id)
    )
    assert total == 2 and len(page) == 1 and p == 1 and lim == 1


def test_group_key_same_day():
    a = _apt(1, 5, 1, hour=9)
    b = _apt(1, 5, 2, hour=16)
    assert _canonical_group_key(a) == _canonical_group_key(b)


if __name__ == "__main__":
    test_dedupe_prefers_paid_same_patient_doctor_day()
    test_canonical_rank_paid_beats_unpaid()
    test_filter_payment_and_paginate()
    test_group_key_same_day()
    print("ok")
