"""Tests for GET /opd/appointments list filters and sorting."""
import pytest
from fastapi import HTTPException

from Models.opd_billing import AppointmentStatus
from Services import appointment_service as svc


def test_resolve_list_filter_rejects_invalid():
    with pytest.raises(HTTPException) as exc:
        svc._resolve_list_filter("invalid")
    assert exc.value.status_code == 422


def test_resolve_sort_order_defaults_desc():
    sort_key, order_key = svc._resolve_sort_order(None, None)
    assert sort_key == "scheduled_at"
    assert order_key == "desc"


def test_resolve_sort_order_rejects_invalid_order():
    with pytest.raises(HTTPException) as exc:
        svc._resolve_sort_order("scheduled_at", "sideways")
    assert exc.value.status_code == 422


def test_list_filter_completed_ignores_conflicting_status(db, appointment_seed):
    result = svc.list_appointments(
        db,
        list_filter="completed",
        status="scheduled",
        limit=50,
    )
    assert result["total"] == 1
    assert len(result["appointments"]) == 1
    assert result["appointments"][0].status == "completed"


def test_search_matches_numeric_patient_id(db, appointment_seed):
    patient_id = appointment_seed["patient"].id
    result = svc.list_appointments(db, search=str(patient_id), limit=50)
    assert result["total"] == 3
    assert all(a.patient_id == patient_id for a in result["appointments"])


def test_sort_scheduled_at_desc(db, appointment_seed):
    result = svc.list_appointments(
        db,
        sort="scheduled_at",
        order="desc",
        limit=50,
    )
    times = [a.scheduled_at for a in result["appointments"]]
    assert times == sorted(times, reverse=True)


def test_list_filter_all_excludes_completed(db, appointment_seed):
    result = svc.list_appointments(db, list_filter="all", limit=50)
    assert result["total"] == 2
    assert all(a.status == "scheduled" for a in result["appointments"])


def test_list_counts_reflect_base_filters(db, appointment_seed):
    result = svc.list_appointments(db, list_filter="all", limit=50)
    assert result["list_counts"]["all"] == 2
    assert result["list_counts"]["completed"] == 1
