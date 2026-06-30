"""Tests for GET /opd/dashboard ward bed statistics."""
from Models.opd_billing import Bed
from Services import bed_service
from Services.opd_service import get_dashboard


def test_get_ward_bed_stats_groups_by_ward(db):
    db.add_all(
        [
            Bed(bed_number="G-101", ward_name="General", status="occupied"),
            Bed(bed_number="G-102", ward_name="General", status="available"),
            Bed(bed_number="ICU-1", ward_name="ICU", status="occupied"),
            Bed(bed_number="ICU-2", ward_name="ICU", status="occupied"),
            Bed(bed_number="P-201", ward_name="Private", status="available"),
        ]
    )
    db.commit()

    stats = bed_service.get_ward_bed_stats(db)

    assert stats == [
        {"ward": "General", "occupied": 1, "available": 1},
        {"ward": "ICU", "occupied": 2, "available": 0},
        {"ward": "Private", "occupied": 0, "available": 1},
    ]


def test_get_dashboard_includes_ward_bed_stats(db):
    db.add_all(
        [
            Bed(bed_number="G-101", ward_name="General", status="occupied"),
            Bed(bed_number="G-102", ward_name="General", status="available"),
        ]
    )
    db.commit()

    payload = get_dashboard(db)

    assert "ward_bed_stats" in payload
    assert payload["ward_bed_stats"] == [
        {"ward": "General", "occupied": 1, "available": 1},
    ]
    assert payload["beds_total"] == 2
    assert payload["beds_free"] == 1
