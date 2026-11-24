import unittest
from datetime import timedelta
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
from Models.lead import Lead
from Models.legal_case import LegalCase, LegalCaseDecision, LegalChecklistItem, LegalDocument, LegalFinanceTerms
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.role import Role  # noqa: F401
from Models.subscription_plan import SubscriptionPlan  # noqa: F401
from Models.tenant import Tenant  # noqa: F401
from Models.user import User
from Schemas.legal_case_schema import EscalationDecision, LegalChecklistUpdate, LegalDecision, LegalFinanceUpdate, ChecklistItemUpdate
from Services.legal_case_service import (
    _now,
    case_ready_for_registration,
    confirm_advance,
    decide_case,
    decide_escalation,
    get_case,
    list_cases,
    open_case_for_agreed_lead,
    request_escalation,
    resubmit_case,
    save_checklist,
    save_finance,
    set_document_status,
)
from Services.registration_service import list_registrations


def _actor(role_name):
    return SimpleNamespace(id=1, tenant_id=None, role_obj=SimpleNamespace(name=role_name))


class LegalFinancePathTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        SubscriptionPlan.__table__.create(engine)
        Lead.__table__.create(engine)
        LegalCase.__table__.create(engine)
        LegalChecklistItem.__table__.create(engine)
        LegalDocument.__table__.create(engine)
        LegalFinanceTerms.__table__.create(engine)
        LegalCaseDecision.__table__.create(engine)
        User.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.lead = Lead(
            hospital_name="City Care",
            hospital_type="General",
            city="Pune",
            contact_person="Asha",
            contact_phone="9000000000",
            source="Website",
            status="Agreed",
            created_by=1,
            plan="Starter",
            billing_cycle="Monthly",
        )
        self.db.add(self.lead)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_agreed_lead_opens_one_case_and_accounts_waits(self):
        first = open_case_for_agreed_lead(self.db, self.lead)
        second = open_case_for_agreed_lead(self.db, self.lead)
        self.db.commit()
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.status, "New from CRM")
        self.assertEqual(first.lead_id, self.lead.id)
        self.assertEqual(first.hospital_name, "City Care")
        self.assertEqual(first.city, "Pune")
        self.assertEqual(first.plan, "Starter")
        self.assertEqual(first.billing_cycle, "Monthly")
        self.assertEqual(first.discount, 0)
        finance_rows = self.db.query(LegalFinanceTerms).filter_by(case_id=first.id).all()
        self.assertEqual(len(finance_rows), 1)
        self.assertEqual(finance_rows[0].frequency, "Monthly")
        self.assertEqual(finance_rows[0].standard_price, 4999)
        self.assertFalse(finance_rows[0].reviewed)
        self.assertEqual(self.db.query(LegalDocument).filter_by(case_id=first.id).count(), 0)
        checks = self.db.query(LegalChecklistItem).filter_by(case_id=first.id).all()
        self.assertEqual(len(checks), 7)
        self.assertTrue(all(item.status == "Pending" for item in checks))
        self.assertFalse(case_ready_for_registration(self.db, self.lead.id))
        self.assertEqual(list_registrations(self.db, _actor("accountant"), "agreed"), [])

        with self.assertRaises(HTTPException) as paid_too_soon:
            confirm_advance(self.db, _actor("accountant"), first.id)
        self.assertEqual(paid_too_soon.exception.status_code, 409)

        with self.assertRaises(HTTPException) as incomplete:
            decide_case(
                self.db,
                _actor("legal_finance"),
                first.id,
                LegalDecision(status="Approved", reason="Too early."),
            )
        self.assertEqual(incomplete.exception.status_code, 422)

        self.db.add_all([
            LegalDocument(
                case_id=first.id,
                category="Hospital Registration",
                file_name=f"doc-{index}.pdf",
                stored_path=f"missing-{index}.pdf",
                status="Verified",
            )
            for index in range(4)
        ])
        self.db.commit()
        saved = save_checklist(
            self.db,
            _actor("legal_finance"),
            first.id,
            LegalChecklistUpdate(items=[
                ChecklistItemUpdate(id=item.id, status="Verified", note=None)
                for item in self.db.query(LegalChecklistItem).filter_by(case_id=first.id).all()
            ]),
        )
        self.assertTrue(all(item.updated_by == 1 and item.updated_at for item in saved.checklist))
        priced = save_finance(self.db, _actor("legal_finance"), first.id, LegalFinanceUpdate(discount=18))
        self.assertEqual(priced.finance.updated_by, 1)
        self.assertEqual(priced.escalation, "Not requested")
        with self.assertRaises(HTTPException) as not_asked:
            decide_escalation(
                self.db,
                _actor("legal_finance"),
                first.id,
                EscalationDecision(status="Approved"),
            )
        self.assertEqual(not_asked.exception.status_code, 409)
        requested = request_escalation(self.db, _actor("legal_finance"), first.id)
        self.assertEqual(requested.escalation, "Pending")
        self.assertEqual(requested.escalation_by, 1)
        with self.assertRaises(HTTPException) as needs_head:
            decide_case(
                self.db,
                _actor("legal_finance"),
                first.id,
                LegalDecision(status="Approved", reason="Discount is open."),
            )
        self.assertEqual(needs_head.exception.status_code, 422)
        escalated = decide_escalation(
            self.db,
            _actor("legal_finance"),
            first.id,
            EscalationDecision(status="Approved"),
        )
        self.assertEqual(escalated.escalation_by, 1)
        self.assertTrue(escalated.escalation_at)

        approved = decide_case(
            self.db,
            _actor("legal_finance"),
            first.id,
            LegalDecision(status="Approved", reason="Papers and price are fine."),
        )
        self.assertEqual(approved.status, "Approved")
        self.assertEqual(approved.decision.status, "Approved")
        self.assertEqual(approved.finance.discount, 18)
        self.assertFalse(approved.advance_received)
        self.assertTrue(approved.ready_to_register)
        self.assertTrue(case_ready_for_registration(self.db, self.lead.id))
        self.assertEqual([row.id for row in list_registrations(self.db, _actor("accountant"), "agreed")], [self.lead.id])

        ready = confirm_advance(self.db, _actor("accountant"), first.id)
        self.assertTrue(ready.advance_received)
        self.assertTrue(ready.ready_to_register)
        listed = list_registrations(self.db, _actor("accountant"), "agreed")
        self.assertEqual([row.id for row in listed], [self.lead.id])

        with self.assertRaises(HTTPException) as crm_denied:
            decide_case(
                self.db,
                _actor("crm"),
                first.id,
                LegalDecision(status="Rejected", reason="No."),
            )
        self.assertEqual(crm_denied.exception.status_code, 403)
        self.assertEqual(self.db.query(LegalCase).count(), 1)

    def test_three_documents_conditional_owner_and_resubmit(self):
        case = open_case_for_agreed_lead(self.db, self.lead)
        self.db.commit()
        self.db.add_all([
            LegalDocument(
                case_id=case.id,
                category="Hospital Registration",
                file_name=f"short-{index}.pdf",
                stored_path=f"short-{index}.pdf",
                status="Verified",
            )
            for index in range(3)
        ])
        self.db.commit()
        save_checklist(
            self.db,
            _actor("legal_finance"),
            case.id,
            LegalChecklistUpdate(items=[
                ChecklistItemUpdate(id=item.id, status="Verified", note=None)
                for item in self.db.query(LegalChecklistItem).filter_by(case_id=case.id).all()
            ]),
        )
        save_finance(self.db, _actor("legal_finance"), case.id, LegalFinanceUpdate(discount=0))
        with self.assertRaises(HTTPException) as three_docs:
            decide_case(
                self.db,
                _actor("legal_finance"),
                case.id,
                LegalDecision(status="Approved", reason="Not enough papers."),
            )
        self.assertEqual(three_docs.exception.status_code, 422)

        self.db.add(LegalDocument(
            case_id=case.id,
            category="Entity Registration",
            file_name="fourth.pdf",
            stored_path="fourth.pdf",
            status="Verified",
        ))
        self.db.commit()
        with self.assertRaises(HTTPException) as missing_owner:
            decide_case(
                self.db,
                _actor("legal_finance"),
                case.id,
                LegalDecision(status="Conditionally Approved", reason="Pay later.", condition="Send the licence."),
            )
        self.assertEqual(missing_owner.exception.status_code, 422)

        sent_back = decide_case(
            self.db,
            _actor("legal_finance"),
            case.id,
            LegalDecision(status="Changes Requested", reason="Signatory letter is missing."),
        )
        self.assertEqual(sent_back.status, "Changes Requested")
        self.assertFalse(sent_back.advance_received)
        reviewed = resubmit_case(self.db, _actor("legal_finance"), case.id)
        self.assertEqual(reviewed.status, "In Review")

    def _checklist(self, case_id, label):
        return self.db.query(LegalChecklistItem).filter_by(case_id=case_id, label=label).one()

    def test_document_and_checklist_status_stay_together(self):
        self.db.add(User(id=1, first_name="Krishna", last_name="Singh", email="krishna@example.com", password="x"))
        case = open_case_for_agreed_lead(self.db, self.lead)
        self.db.commit()
        document = LegalDocument(
            case_id=case.id,
            category="Entity Registration",
            file_name=r"C:\papers\licence.pdf",
            stored_path="licence.pdf",
            status="Pending Review",
            uploaded_by=1,
        )
        self.db.add(document)
        self.db.commit()

        pending = set_document_status(self.db, _actor("legal_finance"), case.id, document.id, "Pending Review")
        identity = next(item for item in pending.checklist if item.label == "Legal entity identity verified")
        shown = next(row for row in pending.documents if row.id == document.id)
        self.assertEqual(identity.status, "Pending")
        self.assertEqual(shown.file_name, "licence.pdf")
        self.assertEqual(shown.uploaded_by_name, "Krishna Singh")
        self.assertTrue(shown.uploaded_at)

        verified = set_document_status(self.db, _actor("legal_finance"), case.id, document.id, "Verified")
        identity = next(item for item in verified.checklist if item.label == "Legal entity identity verified")
        self.assertEqual(identity.status, "Verified")

        rejected = set_document_status(self.db, _actor("legal_finance"), case.id, document.id, "Changes Requested")
        identity = next(item for item in rejected.checklist if item.label == "Legal entity identity verified")
        self.assertEqual(identity.status, "Issue Found")

        item = self._checklist(case.id, "Legal entity identity verified")
        saved = save_checklist(
            self.db,
            _actor("legal_finance"),
            case.id,
            LegalChecklistUpdate(items=[ChecklistItemUpdate(id=item.id, status="Verified", note=None)]),
        )
        shown = next(row for row in saved.documents if row.id == document.id)
        self.assertEqual(shown.status, "Verified")

    def test_loading_cases_repairs_a_stale_mismatch(self):
        case = open_case_for_agreed_lead(self.db, self.lead)
        self.db.commit()
        now = _now()
        document = LegalDocument(
            case_id=case.id,
            category="Hospital License",
            file_name="licence.pdf",
            stored_path="licence.pdf",
            status="Verified",
            reviewed_at=now,
        )
        self.db.add(document)
        item = self._checklist(case.id, "Relevant licenses checked (where applicable)")
        item.status = "Pending"
        item.updated_at = now - timedelta(minutes=5)
        self.db.commit()

        loaded = get_case(self.db, _actor("legal_finance"), case.id)
        identity = next(row for row in loaded.checklist if row.label == item.label)
        self.assertEqual(identity.status, "Verified")

        item = self._checklist(case.id, item.label)
        item.status = "Issue Found"
        item.updated_at = _now() + timedelta(minutes=5)
        self.db.commit()
        listed = list_cases(self.db, _actor("legal_finance"))
        shown = next(row for row in listed[0].documents if row.category == "Hospital License")
        self.assertEqual(shown.status, "Changes Requested")
