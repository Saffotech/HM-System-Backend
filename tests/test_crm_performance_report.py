import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.department import Department  # noqa: F401
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.lead import Lead, LeadActivity
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
from Services.platform_report_service import crm_performance
from hash import hash_password


def _actor(role_name, user_id=1):
    return SimpleNamespace(id=user_id, tenant_id=None, role_obj=SimpleNamespace(name=role_name))


class CrmPerformanceReportTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for table in (
            Tenant.__table__,
            Role.__table__,
            User.__table__,
            Lead.__table__,
            LeadActivity.__table__,
            SubscriptionInvoice.__table__,
        ):
            table.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Role(id=1, name="crm"))
        self.crm = User(
            first_name="Meera",
            last_name="Iyer",
            email="meera@example.com",
            password=hash_password("Secret123"),
            role_id=1,
            tenant_id=None,
            is_active=True,
        )
        self.db.add(self.crm)
        self.db.flush()
        today = date.today()
        self.hospital = Tenant(
            name="City Care",
            code="CITY",
            hospital_type="General",
            plan="Starter",
            billing_cycle="Monthly",
            subscription_started_on=today,
            subscription_renews_on=today,
        )
        self.db.add(self.hospital)
        self.db.flush()
        self.db.add(
            Lead(
                hospital_name="City Care",
                city="Pune",
                contact_person="A",
                contact_phone="1",
                source="Call",
                status="Registered",
                assigned_to=self.crm.id,
                created_by=self.crm.id,
                hospital_id=self.hospital.id,
                follow_up_date=date(2026, 1, 1),
            )
        )
        self.db.add(
            SubscriptionInvoice(
                number="PAID-1",
                tenant_id=self.hospital.id,
                plan="Starter",
                billing_cycle="Monthly",
                amount=4999,
                payment_amount=4999,
                invoice_date=today,
                due_date=today,
                status="Paid",
            )
        )
        self.db.add(
            SubscriptionInvoice(
                number="OPEN-1",
                tenant_id=self.hospital.id,
                plan="Starter",
                billing_cycle="Monthly",
                amount=100,
                invoice_date=date(2026, 2, 1),
                due_date=today,
                status="Pending",
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_report_includes_every_lead_assignee_and_paid_invoice(self):
        report = crm_performance(self.db, _actor("platform_admin"))
        self.assertEqual(report["employees"], [{"id": self.crm.id, "name": "Meera Iyer"}])
        self.assertEqual(len(report["leads"]), 1)
        self.assertEqual(report["leads"][0]["assignee_name"], "Meera Iyer")
        self.assertEqual(report["leads"][0]["hospital_id"], self.hospital.id)
        self.assertEqual(len(report["paid_invoices"]), 1)
        self.assertEqual(report["paid_invoices"][0]["amount"], 4999)
        with self.assertRaises(HTTPException):
            crm_performance(self.db, _actor("crm", self.crm.id))


if __name__ == "__main__":
    unittest.main()
