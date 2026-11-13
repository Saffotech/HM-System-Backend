"""Delete unused beds. Deactivate beds that have had a patient."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import Models.tenant_filter  # noqa: F401
from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd import IpdAdmission
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
from Services import bed_service


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


class BedDeleteModeTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for model in (
            Tenant,
            Role,
            Department,
            User,
            Bed,
            IpdAdmission,
            NurseShiftBedAllocation,
            NurseShiftBedAllocationHistory,
        ):
            model.__table__.create(engine)
        self.db = sessionmaker(bind=engine, autoflush=False)()
        self.hospital = _tenant("H1")
        self.db.add(self.hospital)
        self.db.flush()
        role = Role(name="nurse")
        self.db.add(role)
        self.db.flush()
        self.nurse = User(
            first_name="Nurse",
            email="nurse-a@example.com",
            password="hashed",
            role_id=role.id,
            tenant_id=self.hospital.id,
            is_active=True,
        )
        self.db.add(self.nurse)
        self.db.commit()
        self.db.info["tenant_id"] = self.hospital.id

    def tearDown(self):
        self.db.close()

    def _bed(self, number, ward, **kwargs):
        bed = Bed(
            bed_number=number,
            ward_name=ward,
            tenant_id=self.hospital.id,
            status=kwargs.get("status", "available"),
            is_active=True,
            bed_type="single",
            patient_id=kwargs.get("patient_id"),
        )
        self.db.add(bed)
        self.db.commit()
        self.db.refresh(bed)
        return bed

    def _admission(self, bed, status):
        row = IpdAdmission(
            tenant_id=bed.tenant_id,
            admission_no=f"IPD-{bed.id}-{status}",
            patient_id=1,
            bed_id=bed.id,
            status=status,
            payment_type="self",
            admitted_at=datetime.now(ZoneInfo("Asia/Kolkata")),
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_unused_bed_is_deleted_and_number_can_be_reused(self):
        bed = self._bed("G-1", "General")
        allocation = NurseShiftBedAllocation(
            nurse_id=self.nurse.id,
            bed_id=bed.id,
            tenant_id=bed.tenant_id,
            shift_date=date(2026, 11, 1),
            shift_name="Morning",
            is_active=True,
        )
        self.db.add(allocation)
        self.db.commit()
        result = bed_service.delete_bed(self.db, bed.id)
        self.assertEqual(result["message"], "Bed deleted")
        self.assertFalse(result["has_patient_history"])
        self.assertIsNone(self.db.query(Bed).filter(Bed.id == bed.id).first())
        self.assertEqual(self.db.query(NurseShiftBedAllocation).count(), 0)
        created = bed_service.create_bed(
            self.db,
            type("New", (), {
                "ward_name": "General",
                "bed_number": "G-1",
                "department_id": None,
                "bed_type": "single",
            })(),
        )
        self.assertFalse(created.has_patient_history)

    def test_discharged_or_admitted_bed_is_only_deactivated(self):
        discharged = self._bed("G-2", "General")
        self._admission(discharged, "discharged")
        admitted = self._bed("G-3", "General", status="occupied")
        self._admission(admitted, "admitted")
        listed = bed_service.list_beds(self.db, ward="General", status_filter="all")
        flags = {bed.bed_number: bed.has_patient_history for bed in listed["beds"]}
        self.assertEqual(flags, {"G-2": True, "G-3": True})

        result = bed_service.delete_bed(self.db, discharged.id)
        self.db.refresh(discharged)
        self.assertEqual(result["message"], "Bed deactivated successfully")
        self.assertFalse(discharged.is_active)
        self.assertEqual(self.db.query(IpdAdmission).filter(IpdAdmission.bed_id == discharged.id).count(), 1)

        with self.assertRaises(HTTPException) as raised:
            bed_service.delete_bed(self.db, admitted.id)
        self.assertEqual(raised.exception.status_code, 400)
        self.db.refresh(admitted)
        self.assertTrue(admitted.is_active)

    def test_ward_with_any_patient_deactivates_every_bed(self):
        used = self._bed("W-1", "Blue")
        unused = self._bed("W-2", "Blue")
        self._admission(used, "discharged")
        result = bed_service.delete_ward(self.db, "Blue")
        self.db.refresh(used)
        self.db.refresh(unused)
        self.assertEqual(result["message"], "Ward deactivated successfully")
        self.assertEqual(result["deleted_beds"], 0)
        self.assertEqual(result["deactivated_beds"], 2)
        self.assertFalse(used.is_active)
        self.assertFalse(unused.is_active)

    def test_unused_ward_is_deleted(self):
        first = self._bed("W-3", "Green")
        second = self._bed("W-4", "Green")
        result = bed_service.delete_ward(self.db, "Green")
        self.assertEqual(result["message"], "Ward deleted")
        self.assertEqual(result["deleted_beds"], 2)
        self.assertEqual(result["deactivated_beds"], 0)
        self.assertIsNone(self.db.query(Bed).filter(Bed.id == first.id).first())
        self.assertIsNone(self.db.query(Bed).filter(Bed.id == second.id).first())

    def test_inactive_bed_and_ward_can_be_activated(self):
        used = self._bed("W-5", "Yellow")
        unused = self._bed("W-6", "Yellow")
        self._admission(used, "discharged")
        bed_service.delete_ward(self.db, "Yellow")
        self.db.refresh(used)
        self.db.refresh(unused)
        self.assertFalse(used.is_active)
        self.assertFalse(unused.is_active)

        bed_result = bed_service.activate_bed(self.db, used.id)
        self.db.refresh(used)
        self.assertEqual(bed_result["message"], "Bed activated successfully")
        self.assertTrue(used.is_active)
        self.assertFalse(unused.is_active)

        ward_result = bed_service.activate_ward(self.db, "Yellow")
        self.db.refresh(unused)
        self.assertEqual(ward_result["message"], "Ward activated successfully")
        self.assertEqual(ward_result["activated_beds"], 1)
        self.assertTrue(unused.is_active)

        with self.assertRaises(HTTPException) as raised:
            bed_service.activate_bed(self.db, used.id)
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
