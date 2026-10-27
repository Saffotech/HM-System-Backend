import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.department import Department  # noqa: F401
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.lead import Lead
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.role import Role
from Models.subscription_invoice import SubscriptionInvoice
from Models.subscription_plan import SubscriptionPlan
from Models.tenant import Tenant
from Models.user import User
from Schemas.platform_admin_profile_schema import PlatformAdminProfileUpdate
from Schemas.platform_staff_schema import PlatformStaffCreate
from Schemas.tenant_schema import TenantUpdate
from Services.invoice_service import list_invoices
from Services.plan_service import ensure_default_plans, price_for
from Services.platform_admin_profile_service import update_profile
from Services.platform_report_service import crm_analytics, revenue_report
from Services.platform_staff_service import create_platform_staff, list_platform_staff
from Services.tenant_service import update_tenant
from hash import hash_password


def _actor(role_name, user_id=1, tenant_id=None):
    return SimpleNamespace(
        id=user_id,
        email=f"{role_name}@example.com",
        tenant_id=tenant_id,
        role_obj=SimpleNamespace(name=role_name),
    )


class PlatformAdminFeatureTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for table in (
            Tenant.__table__,
            Role.__table__,
            User.__table__,
            SubscriptionPlan.__table__,
            SubscriptionInvoice.__table__,
            Lead.__table__,
            PlatformAdminProfile.__table__,
        ):
            table.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Role(id=1, name="crm"))
        self.db.add(Role(id=2, name="accountant"))
        self.db.add(Role(id=3, name="platform_admin"))
        self.db.add(Role(id=4, name="admin"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_staff_list_returns_only_crm_and_accountant(self):
        admin = _actor("platform_admin")
        with unittest.mock.patch("Services.platform_staff_service.audit_service.log_event"):
            create_platform_staff(
                self.db,
                PlatformStaffCreate(
                    first_name="Meera",
                    email="crm@example.com",
                    password="Secret123",
                    role="crm",
                ),
                admin,
            )
        self.db.add(
            User(
                first_name="Owner",
                email="owner@example.com",
                password=hash_password("Secret123"),
                role_id=3,
                tenant_id=None,
                is_active=True,
            )
        )
        self.db.commit()
        listed = list_platform_staff(self.db, admin)
        self.assertEqual([row.email for row in listed], ["crm@example.com"])
        with self.assertRaises(HTTPException):
            list_platform_staff(self.db, _actor("crm"))

    def test_hospital_update_changes_contract_and_leaves_invoices(self):
        ensure_default_plans(self.db)
        today = date(2026, 10, 1)
        tenant = Tenant(
            name="City Care",
            code="CITY",
            hospital_type="General",
            phone="9000000000",
            address="Old road",
            plan="Starter",
            billing_cycle="Monthly",
            trial_period="None",
            tenant_status="Active",
            subscription_status="Active",
            subscription_started_on=today,
            subscription_renews_on=date(2026, 11, 1),
            subscription_amount=4999,
            is_active=True,
        )
        self.db.add(tenant)
        self.db.flush()
        invoice = SubscriptionInvoice(
            number="INV-OLD",
            tenant_id=tenant.id,
            plan="Starter",
            billing_cycle="Monthly",
            amount=4999,
            invoice_date=today,
            due_date=date(2026, 10, 15),
            status="Paid",
            payment_amount=4999,
        )
        self.db.add(invoice)
        self.db.commit()
        updated = update_tenant(
            self.db,
            _actor("platform_admin"),
            tenant.id,
            TenantUpdate(name="City Care Hospital", plan="Professional", subscription_renews_on=date(2027, 1, 1)),
        )
        self.assertEqual(updated.name, "City Care Hospital")
        self.assertEqual(updated.plan, "Professional")
        self.assertEqual(updated.subscription_amount, price_for(self.db, "Professional", "Monthly"))
        self.assertEqual(updated.subscription_renews_on, date(2027, 1, 1))
        self.db.refresh(invoice)
        self.assertEqual(invoice.amount, 4999)
        self.assertEqual(invoice.plan, "Starter")
        with self.assertRaises(HTTPException):
            update_tenant(self.db, _actor("platform_admin", tenant_id=9), tenant.id, TenantUpdate(name="Nope"))

    def test_unknown_plan_rejected(self):
        with self.assertRaises(ValidationError):
            TenantUpdate(plan="Gold")

    def test_revenue_splits_paid_pending_and_overdue(self):
        today = date.today()
        tenant = Tenant(
            name="Bill Care",
            code="BILL",
            hospital_type="General",
            plan="Starter",
            billing_cycle="Monthly",
            subscription_started_on=today,
            subscription_renews_on=today,
        )
        self.db.add(tenant)
        self.db.flush()
        self.db.add_all(
            [
                SubscriptionInvoice(
                    number="PAID",
                    tenant_id=tenant.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=100,
                    invoice_date=today,
                    due_date=today,
                    status="Paid",
                    payment_amount=100,
                ),
                SubscriptionInvoice(
                    number="OPEN",
                    tenant_id=tenant.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=40,
                    invoice_date=date(2026, 9, 1),
                    due_date=today,
                    status="Pending",
                ),
                SubscriptionInvoice(
                    number="LATE",
                    tenant_id=tenant.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=25,
                    invoice_date=date(2020, 1, 1),
                    due_date=date(2020, 1, 15),
                    status="Pending",
                ),
                SubscriptionInvoice(
                    number="FAIL",
                    tenant_id=tenant.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=999,
                    invoice_date=date(2020, 2, 1),
                    due_date=date(2020, 2, 15),
                    status="Failed",
                ),
            ]
        )
        self.db.commit()
        report = revenue_report(self.db, _actor("platform_admin"))
        self.assertEqual(report["collected_amount"], 100)
        self.assertEqual(report["pending_amount"], 40)
        self.assertEqual(report["overdue_amount"], 25)
        self.assertEqual(report["outstanding_amount"], 65)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(report["failed_amount"], 999)
        self.assertEqual(report["invoice_count"], 4)
        buckets = {row["bucket"] for row in report["invoices"]}
        self.assertEqual(buckets, {"collected", "pending", "overdue", "failed"})
        paid = next(row for row in report["invoices"] if row["bucket"] == "collected")
        self.assertEqual(paid["hospital_name"], "Bill Care")
        self.assertEqual(paid["paid_date"], today.isoformat())
        self.assertEqual(paid["amount"], 100)

    def test_platform_admin_invoice_list_includes_every_hospital(self):
        today = date.today()
        first = Tenant(
            name="Bill Care",
            code="BILL",
            hospital_type="General",
            plan="Starter",
            billing_cycle="Monthly",
            subscription_started_on=today,
            subscription_renews_on=today,
        )
        second = Tenant(
            name="Other Care",
            code="OTHR",
            hospital_type="General",
            plan="Professional",
            billing_cycle="Annual",
            subscription_started_on=today,
            subscription_renews_on=today,
        )
        self.db.add_all([first, second])
        self.db.flush()
        self.db.add_all(
            [
                SubscriptionInvoice(
                    number="PAID",
                    tenant_id=first.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=100,
                    invoice_date=today,
                    due_date=today,
                    status="Paid",
                    payment_amount=100,
                    paid_at=today,
                ),
                SubscriptionInvoice(
                    number="OPEN",
                    tenant_id=first.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=40,
                    invoice_date=date(2026, 9, 1),
                    due_date=today,
                    status="Pending",
                ),
                SubscriptionInvoice(
                    number="LATE",
                    tenant_id=first.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=25,
                    invoice_date=date(2020, 1, 1),
                    due_date=date(2020, 1, 15),
                    status="Pending",
                ),
                SubscriptionInvoice(
                    number="FAIL",
                    tenant_id=first.id,
                    plan="Starter",
                    billing_cycle="Monthly",
                    amount=999,
                    invoice_date=date(2020, 2, 1),
                    due_date=date(2020, 2, 15),
                    status="Failed",
                ),
                SubscriptionInvoice(
                    number="OTHER",
                    tenant_id=second.id,
                    plan="Professional",
                    billing_cycle="Annual",
                    amount=50,
                    invoice_date=date(2026, 8, 1),
                    due_date=date(2026, 8, 15),
                    status="Paid",
                    payment_amount=50,
                ),
            ]
        )
        self.db.commit()

        listed = list_invoices(self.db, _actor("platform_admin"))
        by_number = {row.number: row for row in listed}
        self.assertEqual(set(by_number), {"PAID", "OPEN", "LATE", "FAIL", "OTHER"})
        self.assertEqual(by_number["OTHER"].tenant_id, second.id)
        self.assertNotEqual(by_number["OTHER"].tenant_id, first.id)
        for number in ("PAID", "OPEN", "LATE", "FAIL"):
            row = by_number[number]
            self.assertEqual(row.tenant_id, first.id)
            self.assertEqual(row.plan, "Starter")
            self.assertEqual(row.billing_cycle, "Monthly")
            self.assertIsNotNone(row.invoice_date)
            self.assertIsNotNone(row.due_date)
            self.assertIsNotNone(row.amount)
        self.assertEqual(by_number["PAID"].status, "Paid")
        self.assertEqual(by_number["PAID"].payment_amount, 100)
        self.assertEqual(by_number["PAID"].paid_at, today)
        self.assertEqual(by_number["OPEN"].status, "Pending")
        self.assertEqual(by_number["LATE"].status, "Overdue")
        self.assertEqual(self.db.query(SubscriptionInvoice).filter_by(number="LATE").one().status, "Pending")
        self.assertEqual(by_number["FAIL"].status, "Failed")

        one_hospital = list_invoices(self.db, _actor("platform_admin"), tenant_id=second.id)
        self.assertEqual([row.number for row in one_hospital], ["OTHER"])

        with self.assertRaises(HTTPException) as denied:
            list_invoices(self.db, _actor("admin", tenant_id=first.id))
        self.assertEqual(denied.exception.status_code, 403)

        report = revenue_report(self.db, _actor("platform_admin"))
        self.assertIn("collected_amount", report)
        self.assertNotIn("rows", report)

    def test_crm_counts_include_empty_statuses(self):
        admin = User(
            first_name="Owner",
            email="owner2@example.com",
            password=hash_password("Secret123"),
            role_id=3,
            tenant_id=None,
            is_active=True,
        )
        self.db.add(admin)
        self.db.flush()
        self.db.add(
            Lead(
                hospital_name="One",
                city="Pune",
                contact_person="A",
                contact_phone="1",
                source="Call",
                status="New",
                created_by=admin.id,
            )
        )
        self.db.add(
            Lead(
                hospital_name="Two",
                city="Pune",
                contact_person="B",
                contact_phone="2",
                source="Call",
                status="Not Interested",
                created_by=admin.id,
            )
        )
        self.db.commit()
        counts = crm_analytics(self.db, _actor("platform_admin"))["statuses"]
        self.assertEqual(counts["New"], 1)
        self.assertEqual(counts["Contacted"], 0)
        self.assertEqual(counts["Agreed"], 0)
        self.assertEqual(counts["Registered"], 0)
        self.assertEqual(counts["Not Interested"], 1)
        self.assertEqual(counts["total"], 2)

    def test_profile_rejects_email_and_updates_phone(self):
        user = User(
            first_name="Saffo",
            email="admin@example.com",
            password=hash_password("Secret123"),
            role_id=3,
            tenant_id=None,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        with self.assertRaises(ValidationError):
            PlatformAdminProfileUpdate(email="other@example.com")
        updated = update_profile(
            self.db,
            _actor("platform_admin", user_id=user.id),
            PlatformAdminProfileUpdate(phone="9999999999", job_title="Owner"),
        )
        self.assertEqual(updated.phone, "9999999999")
        self.assertEqual(updated.job_title, "Owner")
        self.assertEqual(updated.email, "admin@example.com")


if __name__ == "__main__":
    unittest.main()
