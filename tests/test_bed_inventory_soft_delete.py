"""Soft-deleted beds stay in the database and drop out of active inventory."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import Models.tenant_filter  # noqa: F401  registers hospital row filters
from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory
from Models.opd_billing import Bed
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Schemas.opd_schema import AssignBedRequest
from Services import bed_service
from Services.ipd_helpers import occupy_bed
from Services.nurse_shift_bed_allocation_service import _allocation_out, _get_bed


def _tenant(code: str) -> Tenant:
    today = date.today()
    return Tenant(
        name=code,
        code=code,
        hospital_type="General",
        plan="Professional",
        billing_cycle="Monthly",
        subscription_started_on=today,
        subscription_renews_on=today,
    )


class BedInventorySoftDeleteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for model in (
            Tenant,
            Role,
            Department,
            User,
            Bed,
            NurseShiftBedAllocation,
            NurseShiftBedAllocationHistory,
        ):
            model.__table__.create(engine)
        self.db = sessionmaker(bind=engine, autoflush=False)()
        self.hospital = _tenant("H1")
        self.other = _tenant("H2")
        self.db.add_all([self.hospital, self.other])
        self.db.flush()
        self.nurse_role = Role(name="nurse")
        self.db.add(self.nurse_role)
        self.db.flush()
        self.nurse = User(
            first_name="Nurse",
            last_name="A",
            email="nurse-a@example.com",
            password="hashed",
            role_id=self.nurse_role.id,
            tenant_id=self.hospital.id,
            is_active=True,
        )
        self.db.add(self.nurse)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _bed(self, number, ward, tenant_id=None, **kwargs):
        bed = Bed(
            bed_number=number,
            ward_name=ward,
            tenant_id=self.hospital.id if tenant_id is None else tenant_id,
            status=kwargs.pop("status", "available"),
            is_active=kwargs.pop("is_active", True),
            bed_type="single",
            patient_id=kwargs.pop("patient_id", None),
        )
        self.db.add(bed)
        self.db.commit()
        self.db.refresh(bed)
        return bed

    def _allocation(self, bed, *, active=True, until=None, shift_date=None):
        row = NurseShiftBedAllocation(
            nurse_id=self.nurse.id,
            bed_id=bed.id,
            tenant_id=bed.tenant_id,
            shift_date=shift_date or date(2026, 11, 1),
            assigned_until=until,
            shift_name="Morning",
            is_active=active,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _history(self, allocation, bed):
        row = NurseShiftBedAllocationHistory(
            allocation_id=allocation.id,
            action="created",
            old_bed_id=bed.id,
            new_bed_id=bed.id,
            old_nurse_id=allocation.nurse_id,
            new_nurse_id=allocation.nurse_id,
            shift_date=allocation.shift_date,
            shift_name=allocation.shift_name,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def test_default_and_explicit_filters(self):
        ward = "Filter Ward"
        active = self._bed("A-1", ward)
        inactive = self._bed("A-2", ward, is_active=False)
        occupied = self._bed("A-3", ward, status="occupied")
        self._bed("B-1", "Other Ward")

        default_rows = bed_service.list_beds(self.db, ward=ward)
        active_rows = bed_service.list_beds(self.db, ward=ward, status_filter="active")
        inactive_rows = bed_service.list_beds(self.db, ward=ward, status_filter="inactive")
        all_rows = bed_service.list_beds(self.db, ward=ward, status_filter="all")
        occupied_rows = bed_service.list_beds(
            self.db, ward=ward, status="occupied", status_filter="active"
        )
        searched = bed_service.list_beds(self.db, ward=ward, search="a-2", status_filter="all")

        self.assertEqual([bed.id for bed in default_rows["beds"]], [active.id, occupied.id])
        self.assertEqual([bed.id for bed in active_rows["beds"]], [active.id, occupied.id])
        self.assertEqual([bed.id for bed in inactive_rows["beds"]], [inactive.id])
        self.assertEqual(
            [bed.id for bed in all_rows["beds"]],
            [active.id, inactive.id, occupied.id],
        )
        self.assertEqual(default_rows["stats"], {"total": 2, "available": 1, "occupied": 1})
        self.assertEqual(inactive_rows["stats"], {"total": 1, "available": 1, "occupied": 0})
        self.assertEqual(all_rows["stats"], {"total": 3, "available": 2, "occupied": 1})
        self.assertEqual([bed.id for bed in occupied_rows["beds"]], [occupied.id])
        self.assertEqual([bed.id for bed in searched["beds"]], [inactive.id])
        self.assertTrue(active_rows["beds"][0].is_active)
        self.assertFalse(inactive_rows["beds"][0].is_active)

    def test_invalid_status_filter_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            bed_service.list_beds(self.db, status_filter="deleted")
        self.assertEqual(raised.exception.status_code, 422)

    def test_delete_available_bed_without_history(self):
        bed = self._bed("mate-102", "General Ward")
        result = bed_service.delete_bed(self.db, bed.id)
        self.db.refresh(bed)
        self.assertEqual(
            result,
            {
                "message": "Bed deactivated successfully",
                "bed_number": "mate-102",
                "ward_name": "General Ward",
                "is_active": False,
            },
        )
        self.assertFalse(bed.is_active)
        self.assertIsNotNone(self.db.query(Bed).filter(Bed.id == bed.id).first())
        with self.assertRaises(HTTPException) as raised:
            bed_service.delete_bed(self.db, bed.id)
        self.assertEqual(raised.exception.status_code, 404)

    def test_delete_preserves_allocation_and_history(self):
        bed = self._bed("G-1", "History Ward")
        allocation = self._allocation(bed)
        history = self._history(allocation, bed)
        open_allocation = self._allocation(bed, until=None)
        closed = self._allocation(bed, active=False, until=date(2026, 10, 1))

        result = bed_service.delete_bed(self.db, bed.id)

        self.db.refresh(bed)
        self.db.refresh(allocation)
        self.db.refresh(open_allocation)
        self.db.refresh(closed)
        self.db.refresh(history)
        self.assertFalse(result["is_active"])
        self.assertFalse(bed.is_active)
        self.assertFalse(allocation.is_active)
        self.assertFalse(open_allocation.is_active)
        self.assertEqual(
            open_allocation.assigned_until,
            datetime.now(ZoneInfo("Asia/Kolkata")).date(),
        )
        self.assertEqual(closed.assigned_until, date(2026, 10, 1))
        self.assertEqual(history.allocation_id, allocation.id)
        self.assertEqual(history.action, "created")
        self.assertEqual(history.old_bed_id, bed.id)
        self.assertEqual(history.new_bed_id, bed.id)
        self.assertEqual(self.db.query(NurseShiftBedAllocation).count(), 3)
        self.assertEqual(
            self.db.query(NurseShiftBedAllocationHistory)
            .filter(NurseShiftBedAllocationHistory.action == "created")
            .count(),
            1,
        )
        historical = _allocation_out(self.db, allocation)
        self.assertEqual(historical["bed_id"], bed.id)
        self.assertEqual(historical["bed_number"], "G-1")
        self.assertEqual(historical["ward_name"], "History Ward")
        self.assertFalse(historical["is_active"])
        visible = bed_service.list_beds(self.db, ward="History Ward", status_filter="all")
        self.assertEqual([row.id for row in visible["beds"]], [bed.id])

    def test_occupied_bed_cannot_be_deleted(self):
        bed = self._bed("G-2", "Occupied Ward", status="occupied", patient_id=4)
        with self.assertRaises(HTTPException) as raised:
            bed_service.delete_bed(self.db, bed.id)
        self.assertEqual(raised.exception.status_code, 400)
        self.db.refresh(bed)
        self.assertTrue(bed.is_active)
        self.assertEqual(bed.status, "occupied")

    def test_inactive_bed_cannot_be_assigned(self):
        bed = self._bed("G-3", "Closed Ward", is_active=False)
        with self.assertRaises(HTTPException) as lookup:
            _get_bed(self.db, bed.id)
        self.assertEqual(lookup.exception.status_code, 400)
        with self.assertRaises(HTTPException) as assigned:
            bed_service.assign_bed(
                self.db, AssignBedRequest(bed_id=bed.id, patient_id=1)
            )
        self.assertEqual(assigned.exception.status_code, 400)
        with self.assertRaises(HTTPException) as occupied:
            occupy_bed(self.db, bed, patient_id=1)
        self.assertEqual(occupied.exception.status_code, 400)
        with self.assertRaises(HTTPException) as updated:
            bed_service.update_bed(self.db, bed.id, type("Patch", (), {"bed_number": "G-9", "ward_name": None, "department_id": None, "bed_type": None})())
        self.assertEqual(updated.exception.status_code, 400)

    def test_delete_ward_deactivates_available_beds_and_blocks_occupied(self):
        first = self._bed("W-1", "Blue Ward")
        second = self._bed("W-2", "Blue Ward")
        allocation = self._allocation(first)
        history = self._history(allocation, first)

        result = bed_service.delete_ward(self.db, "blue ward")
        self.db.refresh(first)
        self.db.refresh(second)
        self.db.refresh(allocation)
        self.db.refresh(history)
        self.assertEqual(result["deactivated_beds"], 2)
        self.assertEqual(result["deleted_beds"], 2)
        self.assertFalse(first.is_active)
        self.assertFalse(second.is_active)
        self.assertFalse(allocation.is_active)
        self.assertEqual(history.new_bed_id, first.id)
        self.assertEqual(self.db.query(Bed).count(), 2)

        occupied = self._bed("W-3", "Red Ward", status="occupied", patient_id=8)
        spare = self._bed("W-4", "Red Ward")
        with self.assertRaises(HTTPException) as raised:
            bed_service.delete_ward(self.db, "Red Ward")
        self.assertEqual(raised.exception.status_code, 400)
        self.db.refresh(occupied)
        self.db.refresh(spare)
        self.assertTrue(occupied.is_active)
        self.assertTrue(spare.is_active)

    def test_inventory_statistics_follow_the_active_inventory(self):
        self._bed("S-1", "Stats Ward", status="available")
        self._bed("S-2", "Stats Ward", status="occupied", patient_id=3)
        self._bed("S-3", "Stats Ward", is_active=False)
        summary = bed_service.ward_inventory_summary(self.db)
        stats = bed_service.get_ward_bed_stats(self.db)
        ward = next(row for row in summary["wards"] if row["ward_name"] == "Stats Ward")
        ward_stats = next(row for row in stats if row["ward"] == "Stats Ward")
        self.assertEqual(ward["total"], 2)
        self.assertEqual(ward["available"], 1)
        self.assertEqual(ward["occupied"], 1)
        self.assertEqual(ward_stats["available"], 1)
        self.assertEqual(ward_stats["occupied"], 1)
        self.assertEqual(summary["totals"]["beds"], 2)

    def test_inactive_bed_number_stays_reserved(self):
        bed = self._bed("mate-102", "General Ward")
        bed_service.delete_bed(self.db, bed.id)
        with self.assertRaises(HTTPException) as raised:
            bed_service.create_bed(
                self.db,
                type("NewBed", (), {
                    "ward_name": "General Ward",
                    "bed_number": "MATE-102",
                    "department_id": None,
                    "bed_type": "single",
                })(),
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_tenant_isolation(self):
        own = self._bed("T-1", "Shared Ward", tenant_id=self.hospital.id)
        other = self._bed("T-2", "Shared Ward", tenant_id=self.other.id)
        self.db.info["tenant_id"] = self.hospital.id
        listed = bed_service.list_beds(self.db, ward="Shared Ward", status_filter="all")
        self.assertEqual([bed.id for bed in listed["beds"]], [own.id])
        with self.assertRaises(HTTPException) as raised:
            bed_service.delete_bed(self.db, other.id)
        self.assertEqual(raised.exception.status_code, 404)
        self.db.info.pop("tenant_id", None)
        self.db.refresh(other)
        self.assertTrue(other.is_active)


if __name__ == "__main__":
    unittest.main()
