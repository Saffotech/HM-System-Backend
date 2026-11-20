"""OPD consultation enable flag and duplicate extra-item guard."""
import unittest

from fastapi import HTTPException

from Schemas.opd_settings_schema import DoctorConsultationFee, PricingOut
from Services import opd_settings_service as settings


def _pricing(**overrides) -> PricingOut:
    data = {
        "registration_fee": 200,
        "consultation_fee": 500,
        "gst_percent": 5,
        "department_consultation_fees": [
            {"department_id": 1, "department_name": "Cardiology", "fee": 600},
        ],
        "doctor_consultation_fees": [
            DoctorConsultationFee(doctor_id=10, fee=700),
            DoctorConsultationFee(doctor_id=11, fee=0),
        ],
    }
    data.update(overrides)
    return PricingOut.model_validate(data)


class ConsultationEnabledTests(unittest.TestCase):
    def test_missing_flag_defaults_on(self):
        pricing = settings.normalize_pricing({"consultation_fee": 500})
        self.assertTrue(pricing.consultation_enabled)

    def test_doctor_overrides_department_and_hospital(self):
        _, consult, _ = settings.resolve_visit_fees(
            _pricing(), doctor_id=10, department_id=1, registration_fee=200
        )
        self.assertEqual(consult, 700)

    def test_department_used_when_doctor_has_no_row(self):
        _, consult, _ = settings.resolve_visit_fees(
            _pricing(), doctor_id=99, department_id=1, registration_fee=200
        )
        self.assertEqual(consult, 600)

    def test_hospital_default_when_neither_override(self):
        _, consult, _ = settings.resolve_visit_fees(
            _pricing(), doctor_id=99, department_id=9, registration_fee=200
        )
        self.assertEqual(consult, 500)

    def test_explicit_zero_doctor_fee_is_kept(self):
        _, consult, _ = settings.resolve_visit_fees(
            _pricing(), doctor_id=11, department_id=1, registration_fee=200
        )
        self.assertEqual(consult, 0)

    def test_off_zeroes_consultation_and_keeps_registration(self):
        pricing = _pricing(consultation_enabled=False)
        reg, consult, gst = settings.resolve_visit_fees(
            pricing, doctor_id=10, department_id=1, registration_fee=200
        )
        self.assertEqual(reg, 200)
        self.assertEqual(consult, 0)
        self.assertEqual(gst, 5)
        self.assertEqual(
            settings.resolve_consultation_fee(pricing, doctor_id=10, department_id=1),
            700,
        )

    def test_reenable_uses_saved_doctor_fee(self):
        stored = _pricing(consultation_enabled=False).model_dump()
        stored["consultation_enabled"] = True
        pricing = settings.normalize_pricing(stored)
        _, consult, _ = settings.resolve_visit_fees(
            pricing, doctor_id=10, department_id=1, registration_fee=200
        )
        self.assertEqual(consult, 700)

    def test_duplicate_consultation_extra_rejected_even_with_manual_prices(self):
        pricing = _pricing(allow_manual_price_entry=True)
        with self.assertRaises(HTTPException) as raised:
            settings.validate_extra_bill_items(
                pricing,
                [{"description": "Doctor Consultation", "qty": 1, "unit_price": 500}],
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_other_extra_item_still_allowed(self):
        rows = settings.validate_extra_bill_items(
            _pricing(consultation_enabled=False, allow_manual_price_entry=True),
            [{"description": "Blood Test", "qty": 1, "unit_price": 600}],
        )
        self.assertEqual(rows[0]["description"], "Blood Test")
        self.assertEqual(rows[0]["unit_price"], 600)


if __name__ == "__main__":
    unittest.main()
