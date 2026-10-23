import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Schemas.platform_staff_schema import PlatformStaffCreate
from Services.platform_staff_service import create_platform_staff
from hash import verify_password


def _actor(role_name: str):
    return SimpleNamespace(
        id=1,
        email=f"{role_name}@example.com",
        tenant_id=None,
        role_obj=SimpleNamespace(name=role_name),
    )


class PlatformStaffTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Tenant.__table__.create(engine)
        Department.__table__.create(engine)
        Role.__table__.create(engine)
        User.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Role(name="crm"))
        self.db.add(Role(name="accountant"))
        self.db.add(Role(name="admin"))
        self.db.commit()
        self.audit = patch("Services.platform_staff_service.audit_service.log_event")
        self.audit.start()

    def tearDown(self):
        self.audit.stop()
        self.db.close()

    def test_platform_admin_creates_crm_and_accountant(self):
        admin = _actor("platform_admin")
        crm = create_platform_staff(
            self.db,
            PlatformStaffCreate(
                first_name="Meera",
                last_name="Iyer",
                email="Meera@Example.com",
                password="Secret123",
                role="crm",
            ),
            admin,
        )
        accountant = create_platform_staff(
            self.db,
            PlatformStaffCreate(
                first_name="Priya",
                email="accounts@example.com",
                password="Secret123",
                role="accountant",
            ),
            admin,
        )
        self.assertEqual(crm.role, "crm")
        self.assertEqual(accountant.role, "accountant")
        self.assertIsNone(crm.tenant_id)
        self.assertIsNone(accountant.tenant_id)
        self.assertEqual(crm.email, "meera@example.com")
        stored = self.db.query(User).filter(User.email == "meera@example.com").one()
        self.assertNotEqual(stored.password, "Secret123")
        self.assertTrue(verify_password("Secret123", stored.password))
        self.assertEqual(stored.role_id, self.db.query(Role).filter(Role.name == "crm").one().id)

    def test_other_roles_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            create_platform_staff(
                self.db,
                PlatformStaffCreate(
                    first_name="A",
                    email="a@example.com",
                    password="Secret123",
                    role="crm",
                ),
                _actor("crm"),
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_unsupported_role_rejected(self):
        with self.assertRaises(ValidationError):
            PlatformStaffCreate(
                first_name="A",
                email="a@example.com",
                password="Secret123",
                role="admin",
            )

    def test_duplicate_email_rejected(self):
        admin = _actor("platform_admin")
        payload = dict(first_name="A", email="dup@example.com", password="Secret123", role="crm")
        create_platform_staff(self.db, PlatformStaffCreate(**payload), admin)
        with self.assertRaises(HTTPException) as raised:
            create_platform_staff(
                self.db,
                PlatformStaffCreate(**{**payload, "role": "accountant"}),
                admin,
            )
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
