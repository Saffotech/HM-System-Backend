import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.department import Department  # noqa: F401
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.lead import Lead
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.role import Role
from Models.subscription_invoice import SubscriptionInvoice
from Models.tenant import Tenant
from Models.user import User
from Schemas.crm_profile_schema import CrmProfileUpdate
from Services.crm_profile_service import update_profile
from Services.crm_revenue_service import crm_revenue
from hash import hash_password


def _actor(role_name, user_id, tenant_id=None):
    return SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
        role_obj=SimpleNamespace(name=role_name),
    )


class CrmPendingTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for table in (
            Tenant.__table__,
            Role.__table__,
            User.__table__,
            Lead.__table__,
            SubscriptionInvoice.__table__,
            CrmProfile.__table__,
        ):
            table.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Role(id=1, name="crm"))
        self.db.add(Role(id=2, name="platform_admin"))
        self.me = User(
            first_name="Meera",
            email="meera@example.com",
            password=hash_password("Secret123"),
            role_id=1,
            tenant_id=None,
            is_active=True,
        )
        self.other = User(
            first_name="Other",
            email="other@example.com",
            password=hash_password("Secret123"),
            role_id=1,
            tenant_id=None,
            is_active=True,
        )
        self.db.add_all([self.me, self.other])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _hospital(self, code, name):
        today = date.today()
        tenant = Tenant(
            name=name,
            code=code,
            hospital_type="General",
            plan="Starter",
            billing_cycle="Monthly",
            subscription_started_on=today,
            subscription_renews_on=today,
        )
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def _lead(self, owner_id, hospital_id, status="Registered"):
        self.db.add(
            Lead(
                hospital_name="Lead",
                city="Pune",
                contact_person="A",
                contact_phone="1",
                source="Call",
                status=status,
                assigned_to=owner_id,
                created_by=owner_id,
                hospital_id=hospital_id,
            )
        )

    def test_revenue_is_only_paid_invoices_of_own_hospitals(self):
        mine = self._hospital("MINE", "Mine Care")
        theirs = self._hospital("THEIRS", "Other Care")
        self._lead(self.me.id, mine.id)
        self._lead(self.other.id, theirs.id)
        today = date.today()
        self.db.add_all(
            [
                SubscriptionInvoice(
                    number="MINE-PAID",
                    tenant_id=mine.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=100,
                    payment_amount=100,
                    invoice_date=today,
                    due_date=today,
                    status="Paid",
                ),
                SubscriptionInvoice(
                    number="MINE-OPEN",
                    tenant_id=mine.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=40,
                    invoice_date=date(2026, 1, 2),
                    due_date=today,
                    status="Pending",
                ),
                SubscriptionInvoice(
                    number="THEIRS-PAID",
                    tenant_id=theirs.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=500,
                    payment_amount=500,
                    invoice_date=date(2026, 1, 3),
                    due_date=today,
                    status="Paid",
                ),
            ]
        )
        self.db.commit()
        report = crm_revenue(self.db, _actor("crm", self.me.id))
        self.assertEqual(report["collected_amount"], 100)
        self.assertEqual(report["collected_count"], 1)
        self.assertEqual([row["hospital_name"] for row in report["hospitals"]], ["Mine Care"])
        self.assertEqual(len(report["months"]), 6)
        with self.assertRaises(HTTPException):
            crm_revenue(self.db, _actor("platform_admin", self.me.id))

    def test_profile_updates_phone_and_rejects_email(self):
        with self.assertRaises(ValidationError):
            CrmProfileUpdate(email="new@example.com")
        updated = update_profile(
            self.db,
            _actor("crm", self.me.id),
            CrmProfileUpdate(phone="8888888888", job_title="Executive"),
        )
        self.assertEqual(updated.phone, "8888888888")
        self.assertEqual(updated.job_title, "Executive")
        self.assertEqual(updated.email, "meera@example.com")
        admin = User(
            first_name="Owner",
            email="owner@example.com",
            password=hash_password("Secret123"),
            role_id=2,
            tenant_id=None,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        with self.assertRaises(HTTPException):
            update_profile(self.db, _actor("platform_admin", admin.id), CrmProfileUpdate(phone="1"))


if __name__ == "__main__":
    unittest.main()
