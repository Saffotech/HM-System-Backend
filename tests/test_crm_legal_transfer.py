import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.lead import Lead, LeadActivity
from Models.legal_case import LegalCase, LegalCaseDecision, LegalChecklistItem, LegalDocument, LegalFinanceTerms
from Models.subscription_plan import SubscriptionPlan
from Models.tenant import Tenant
from Models.user import User
from Schemas.lead_schema import LeadAgree, LeadCreate
from Schemas.legal_case_schema import LegalFinanceUpdate
from Services import lead_service
from Services.lead_service import agree_lead, create_lead
from Services.legal_case_service import get_case, save_finance


def _actor(user_id=1):
    return SimpleNamespace(
        id=user_id,
        tenant_id=None,
        email="crm@example.com",
        role_obj=SimpleNamespace(name="crm"),
    )


class CrmLegalTransferTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        SubscriptionPlan.__table__.create(engine)
        Tenant.__table__.create(engine)
        User.__table__.create(engine)
        Lead.__table__.create(engine)
        LeadActivity.__table__.create(engine)
        LegalCase.__table__.create(engine)
        LegalChecklistItem.__table__.create(engine)
        LegalDocument.__table__.create(engine)
        LegalFinanceTerms.__table__.create(engine)
        LegalCaseDecision.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(User(
            id=1,
            first_name="Meera",
            last_name="Shah",
            email="crm@example.com",
            password="hashed",
        ))
        self.db.commit()
        self.actor = _actor()
        self.audit_calls = []

        def _record(*_args, **kwargs):
            self.audit_calls.append(kwargs)

        self._original_log = lead_service.audit_service.log_event
        lead_service.audit_service.log_event = _record

    def _contact(self, lead_id):
        self.db.query(Lead).filter(Lead.id == lead_id).update({"status": "Contacted"})
        self.db.commit()

    def tearDown(self):
        lead_service.audit_service.log_event = self._original_log
        self.db.close()

    def _create(self, **overrides):
        payload = dict(
            hospital_name="City Care",
            hospital_type="General",
            source="Website",
            priority="High",
            contact_person="Asha Rao",
            designation="Owner",
            contact_phone="9000000000",
            contact_email="asha@city.example",
            hospital_email=overrides.get("hospital_email", "Desk@City.Example"),
            city="Pune",
            state="Maharashtra",
            plan="Starter",
            billing_cycle="Monthly",
            message="Need OPD and billing",
            shared=False,
        )
        payload.update(overrides)
        return create_lead(self.db, LeadCreate(**payload), self.actor)

    def test_hospital_email_is_stored_and_hidden_until_claimed(self):
        owned = self._create()
        self.assertEqual(owned.hospital_email, "desk@city.example")
        shared = self._create(
            hospital_name="Shared Care",
            contact_phone="9000000001",
            contact_email="shared@city.example",
            hospital_email="Shared@City.Example",
            shared=True,
        )
        self.assertIsNone(shared.hospital_email)
        row = self.db.query(Lead).filter(Lead.hospital_name == "Shared Care").one()
        self.assertEqual(row.hospital_email, "shared@city.example")
        self.assertIsNone(row.assigned_to)

    def test_agreement_is_saved_before_the_case_and_snapshot_is_frozen(self):
        lead = self._create()
        self._contact(lead.id)
        agreed = agree_lead(
            self.db,
            lead.id,
            LeadAgree(plan="Professional", billing_cycle="Annual", note="Hand over on Monday", hospital_email="Finance@City.Example"),
            self.actor,
        )
        self.assertEqual(agreed.plan, "Professional")
        self.assertEqual(agreed.billing_cycle, "Annual")
        self.assertEqual(agreed.hospital_email, "finance@city.example")
        self.assertIsNotNone(agreed.agreed_at)
        case = self.db.query(LegalCase).one()
        self.assertEqual(case.plan, "Professional")
        self.assertEqual(case.billing_cycle, "Annual")
        self.assertEqual(case.hospital_email, "finance@city.example")
        self.assertEqual(case.handover_note, "Hand over on Monday")
        self.assertEqual(case.agreed_by_name, "Meera Shah")
        self.assertIsNotNone(case.agreed_at)
        view = get_case(self.db, _actor_legal(), case.id)
        self.assertEqual(view.hospital_type, "General")
        self.assertEqual(view.contact_person, "Asha Rao")
        self.assertEqual(view.lead_source, "Website")
        self.assertEqual(view.priority, "High")
        self.assertEqual(view.requirement, "Need OPD and billing")
        self.assertEqual(view.assigned_employee_id, 1)
        self.assertEqual(view.assigned_employee_name, "Meera Shah")
        self.assertEqual(view.handover_note, "Hand over on Monday")
        finance = self.db.query(LegalFinanceTerms).one()
        self.assertEqual(finance.frequency, "Annual")
        self.assertEqual(finance.standard_price, 8999 * 10)
        self.assertFalse(finance.reviewed)
        self.assertIsNone(finance.invoice_email)
        self.db.query(Lead).filter(Lead.id == lead.id).update({"city": "Mumbai", "handover_note": "Changed later"})
        self.db.commit()
        self.db.expire_all()
        frozen = get_case(self.db, _actor_legal(), case.id)
        self.assertEqual(frozen.city, "Pune")
        self.assertEqual(frozen.handover_note, "Hand over on Monday")

    def test_monthly_and_annual_keep_their_catalog_price(self):
        monthly = self._create(hospital_name="Month Care", contact_phone="9000000002", contact_email="m@city.example", hospital_email="m-desk@city.example")
        self._contact(monthly.id)
        agree_lead(self.db, monthly.id, LeadAgree(plan="Starter", billing_cycle="Monthly", note=None), self.actor)
        annual = self._create(hospital_name="Year Care", contact_phone="9000000003", contact_email="y@city.example", hospital_email="y-desk@city.example")
        self._contact(annual.id)
        agree_lead(self.db, annual.id, LeadAgree(plan="Professional", billing_cycle="Annual", note=None), self.actor)
        prices = {
            row.case.hospital_name: (row.frequency, row.standard_price)
            for row in self.db.query(LegalFinanceTerms).all()
        }
        self.assertEqual(prices["Month Care"], ("Monthly", 4999))
        self.assertEqual(prices["Year Care"], ("Annual", 89990))

    def test_second_agree_updates_the_same_case_and_resets_reviewed_finance(self):
        lead = self._create()
        self._contact(lead.id)
        agree_lead(self.db, lead.id, LeadAgree(plan="Professional", billing_cycle="Annual", note="First"), self.actor)
        case = self.db.query(LegalCase).one()
        document = LegalDocument(case_id=case.id, category="Hospital Registration", file_name="a.pdf", stored_path="a.pdf")
        check = LegalChecklistItem(case_id=case.id, label="Tax and GST details confirmed", status="Pending")
        self.db.add_all([document, check])
        self.db.commit()
        finance = case.finance
        finance.reviewed = True
        finance.discount = 5
        finance.years = 3
        finance.implementation_fee = 1000
        finance.standard_price = 89990
        finance.updated_by = 9
        self.db.commit()
        document_id = document.id
        check_id = check.id
        agree_lead(self.db, lead.id, LeadAgree(plan="Starter", billing_cycle="Monthly", note="Second"), self.actor)
        self.assertEqual(self.db.query(LegalCase).count(), 1)
        self.assertEqual(self.db.query(LegalFinanceTerms).count(), 1)
        saved = self.db.query(LegalCase).one()
        self.assertEqual(saved.id, case.id)
        self.assertEqual(saved.plan, "Starter")
        self.assertEqual(saved.billing_cycle, "Monthly")
        self.assertEqual(self.db.query(LegalDocument).one().id, document_id)
        self.assertEqual(self.db.query(LegalChecklistItem).filter_by(id=check_id).count(), 1)
        terms = self.db.query(LegalFinanceTerms).one()
        self.assertEqual(terms.frequency, "Monthly")
        self.assertEqual(terms.standard_price, 4999)
        self.assertEqual(terms.discount, 5)
        self.assertEqual(terms.years, 3)
        self.assertEqual(terms.implementation_fee, 1000)
        self.assertFalse(terms.reviewed)
        self.assertEqual(terms.updated_by, 9)
        self.assertIn("Professional", saved.commercial_change_note)
        self.assertIn("Monthly", saved.commercial_change_note)
        details = self.audit_calls[-1]["details"]
        self.assertTrue(details["finance_rereview_required"])
        self.assertEqual(details["previous_plan"], "Professional")

    def test_custom_price_is_kept_and_a_decided_case_is_rejected(self):
        lead = self._create()
        self._contact(lead.id)
        agree_lead(self.db, lead.id, LeadAgree(plan="Starter", billing_cycle="Monthly", note="First"), self.actor)
        case = self.db.query(LegalCase).one()
        case.finance.reviewed = True
        case.finance.standard_price = 25000
        self.db.commit()
        agree_lead(self.db, lead.id, LeadAgree(plan="Starter", billing_cycle="Annual", note="Second"), self.actor)
        terms = self.db.query(LegalFinanceTerms).one()
        self.assertEqual(terms.standard_price, 25000)
        self.assertEqual(terms.frequency, "Annual")
        self.assertFalse(terms.reviewed)
        save_finance(self.db, _actor_legal(), case.id, LegalFinanceUpdate(
            standard_price=25000,
            discount=0,
            years=1,
            implementation_fee=0,
            training_fee=0,
            tax_percent=0,
            advance_percent=0,
            credit_days=0,
            frequency="Annual",
            po_required="No",
        ))
        self.db.commit()
        cleared = self.db.query(LegalCase).one()
        self.assertTrue(cleared.finance.reviewed)
        self.assertIsNone(cleared.commercial_change_note)
        cleared.status = "Approved"
        cleared.city = "Pune"
        self.db.commit()
        with self.assertRaises(HTTPException) as blocked:
            agree_lead(self.db, lead.id, LeadAgree(plan="Enterprise", billing_cycle="Monthly", note="Too late"), self.actor)
        self.assertEqual(blocked.exception.status_code, 409)
        self.assertEqual(blocked.exception.detail, "This case already has a decision.")
        untouched = self.db.query(LegalCase).one()
        self.assertEqual(untouched.plan, "Starter")
        self.assertEqual(untouched.city, "Pune")
        self.assertEqual(self.db.query(Lead).one().plan, "Starter")


def _actor_legal():
    return SimpleNamespace(id=2, tenant_id=None, role_obj=SimpleNamespace(name="legal_finance"))


if __name__ == "__main__":
    unittest.main()
