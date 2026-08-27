"""Generator: Prescription item extra fields - Frontend Developer Guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = (
    Path(__file__).resolve().parent
    / "frontend-prescription-item-fields-guide.pdf"
)


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Prescription Medicine Fields (Frontend Guide)",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(1)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, title)
        self.ln(1)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5.5, f"  - {text}")

    def callout(self, label: str, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 60, 20)
        self.multi_cell(self.epw, 6, label)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        for line in text.strip("\n").splitlines():
            safe = line.encode("latin-1", "replace").decode("latin-1")
            self.set_x(self.l_margin)
            self.cell(
                self.epw,
                4.5,
                "  " + safe[:110],
                new_x="LMARGIN",
                new_y="NEXT",
                fill=True,
            )
        self.ln(2)

    def table_row(self, cols: list[str], bold: bool = False, widths: list[float] | None = None):
        if widths is None:
            widths = [self.epw / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        y0 = self.get_y()
        x0 = self.l_margin
        row_h = 6
        for i, col in enumerate(cols):
            self.set_xy(x0 + sum(widths[:i]), y0)
            self.cell(widths[i], row_h, col[:48], border=1)
        self.ln()


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, "Prescription Medicine Fields")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Frontend Developer Guide")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body(
        "Date: 26 August 2026. Backend is already shipped. Current doctor / nurse / "
        "pharmacy screens keep working without frontend changes. New fields are "
        "optional. When frontend is ready, send and display them."
    )

    pdf.callout(
        "Compatibility",
        "Old payload (medicine_name, dosage, frequency, duration, instructions) is "
        "still valid. Missing new fields are stored as null and returned as null. "
        "Do not wait on a breaking API version.",
    )

    pdf.section_title("1. What backend added")
    pdf.body(
        "Each prescription item (one medicine row) now has extra optional fields. "
        "Doctor create/update, consultation save (OPD and IPD), pharmacy detail, "
        "and nurse patient medications all return them."
    )
    pdf.bullet("form - Tablet, Capsule, Syrup, Injection, ...")
    pdf.bullet("dose - amount per take, e.g. 1 or 5 ml (NOT the same as dosage)")
    pdf.bullet("route - Oral, IV, IM, Topical, ...")
    pdf.bullet("timing - After food, Before food, Empty stomach, ...")
    pdf.bullet("quantity - integer total to dispense / take, e.g. 10")
    pdf.bullet("quantity_unit - Tablet(s), Capsule(s), ml, ...")

    pdf.section_title("2. UI field vs API key")
    pdf.body("Map the prescription card to these JSON keys. Do not invent new names.")
    w = [38, 32, 28, 52]
    pdf.table_row(["UI label", "API key", "Required", "Example"], bold=True, widths=w)
    rows = [
        ["Medicine", "medicine_name", "Yes", "Amoxicillin"],
        ["Strength", "dosage", "Yes", "500 mg"],
        ["Form", "form", "No*", "Tablet"],
        ["Dose", "dose", "No*", "1"],
        ["Route", "route", "No*", "Oral"],
        ["Frequency", "frequency", "Yes", "1-0-1"],
        ["Timing / When to take", "timing", "No", "After food"],
        ["Duration", "duration", "Yes", "5 Days"],
        ["Quantity number", "quantity", "No*", "10"],
        ["Quantity unit", "quantity_unit", "No*", "Tablet(s)"],
        ["Special instructions", "instructions", "No", "Take with water"],
    ]
    for row in rows:
        pdf.table_row(row, widths=w)
    pdf.ln(2)
    pdf.body(
        "* Backend does not require the new fields, so today's 6-field doctor form "
        "still saves. When you build the new card, treat Form, Dose, Route, Duration "
        "and Quantity as required in the UI."
    )

    pdf.callout(
        "Important: dosage vs dose",
        "dosage = Strength (500 mg). dose = how much to take each time (1 tablet / "
        "5 ml). Do not put both into dosage. Keep them separate in state and in API.",
    )
    pdf.callout(
        "Important: timing vs instructions",
        "timing = After food / Before food. instructions = free-text special notes "
        "(max 200 chars in UI). Today the doctor form puts 'After food' in "
        "instructions. After the UI change, send timing='After food' and keep "
        "instructions for extra notes only.",
    )

    pdf.section_title("3. APIs that already include the new fields")
    pdf.sub_title("Doctor write")
    pdf.bullet("POST /prescriptions  body.items[]")
    pdf.bullet("PUT /prescriptions/{id}  body.items[]")
    pdf.bullet("OPD consultation save  prescription.items[]")
    pdf.bullet("IPD consultation save  prescription.items[]")
    pdf.body(
        "Consultation save already uses PrescriptionItemCreate. No extra nested "
        "wrapper. Put the new keys on each item next to medicine_name."
    )

    pdf.sub_title("Doctor / pharmacy / nurse read")
    pdf.bullet("GET /prescriptions/{id}  items[]")
    pdf.bullet("GET /prescriptions?patient_id=  items[]")
    pdf.bullet("Pharmacy prescription detail  items[]")
    pdf.bullet("GET /nurse/medications/patient/{patient_id}  medications[]")
    pdf.body(
        "Lab has no prescription API. Lab should not call nurse or pharmacy URLs. "
        "If lab later needs medicines, reuse GET /prescriptions with doctor/lab "
        "permissions, or skip until product asks for it."
    )

    pdf.section_title("4. Old payload (still works)")
    pdf.code_block(
        """
{
  "appointment_id": 101,
  "diagnosis": "Acute bronchitis",
  "notes": "",
  "items": [
    {
      "medicine_name": "Amoxicillin",
      "dosage": "500 mg",
      "frequency": "1-0-1",
      "duration": "5",
      "instructions": "After food"
    }
  ]
}
"""
    )
    pdf.body(
        "duration: send number or '5 Days'. Backend stores text like '5 days'. "
        "Empty new fields are omitted; backend stores null."
    )

    pdf.section_title("5. New payload (when frontend is ready)")
    pdf.code_block(
        """
{
  "appointment_id": 101,
  "diagnosis": "Acute bronchitis",
  "notes": "",
  "items": [
    {
      "medicine_name": "Amoxicillin",
      "dosage": "500 mg",
      "form": "Tablet",
      "dose": "1",
      "route": "Oral",
      "frequency": "1-0-1",
      "timing": "After food",
      "duration": "5 Days",
      "quantity": 10,
      "quantity_unit": "Tablet(s)",
      "instructions": "Take with water, avoid cold drinks"
    }
  ]
}
"""
    )
    pdf.body(
        "IPD: send admission_id instead of appointment_id (exactly one parent). "
        "quantity must be an integer >= 1, or omit it. Do not send \"\". "
        "Blank strings for form/dose/route/timing are stored as null."
    )

    pdf.section_title("6. Response shape (item)")
    pdf.code_block(
        """
{
  "id": 55,
  "medicine_name": "Amoxicillin",
  "dosage": "500 mg",
  "form": "Tablet",
  "dose": "1",
  "route": "Oral",
  "frequency": "1-0-1",
  "timing": "After food",
  "duration": "5 Days",
  "quantity": 10,
  "quantity_unit": "Tablet(s)",
  "instructions": "Take with water, avoid cold drinks"
}
"""
    )
    pdf.body(
        "Old rows: form, dose, route, timing, quantity, quantity_unit are null. "
        "UI must render '-' / empty, not crash."
    )

    pdf.section_title("7. Suggested doctor UI state")
    pdf.code_block(
        """
{
  name: "",
  dosage: "",
  form: "Tablet",
  dose: "",
  route: "Oral",
  frequency: "1-0-1",
  timing: "After food",
  durationValue: "",
  durationUnit: "Days",
  quantity: "",
  quantityUnit: "Tablet(s)",
  instructions: ""
}
"""
    )
    pdf.sub_title("Mapper UI -> API")
    pdf.bullet("name -> medicine_name")
    pdf.bullet("dosage -> dosage (Strength, e.g. 500 mg)")
    pdf.bullet("form, dose, route, frequency, timing as-is")
    pdf.bullet("durationValue + durationUnit -> duration string, e.g. '5 Days'")
    pdf.bullet("quantity as Number; omit if empty")
    pdf.bullet("quantityUnit -> quantity_unit")
    pdf.bullet("instructions as-is (special notes only)")

    pdf.sub_title("Mapper API -> UI")
    pdf.bullet("Parse duration '5 Days' back to durationValue=5, durationUnit=Days")
    pdf.bullet("Null new fields -> empty string in form state")
    pdf.bullet("Keep existing medicines[] shape; add the extra keys on each row")

    pdf.section_title("8. Suggested dropdown values")
    pdf.bullet("Form: Tablet, Capsule, Syrup, Injection, Drops, Cream, Ointment, Inhaler")
    pdf.bullet("Route: Oral, IV, IM, SC, Topical, Inhalation, Sublingual")
    pdf.bullet("Frequency: 1-0-1, 1-1-1, 1-0-0, 0-0-1, 1-1-0, SOS, STAT")
    pdf.bullet("Timing: After food, Before food, Empty stomach, With food, At bedtime")
    pdf.bullet("Duration unit: Days, Weeks, Months")
    pdf.bullet("Quantity unit: Tablet(s), Capsule(s), ml, Bottle(s), Tube(s)")
    pdf.body(
        "These are UI lists only. Backend stores free text (max 50 chars). "
        "Medicine name can stay a text input until a medicine catalog exists."
    )

    pdf.section_title("9. Doctor screens to update later")
    pdf.bullet("ConsultationModal Prescription tab (main card from the screenshot)")
    pdf.bullet("PrescriptionDetailModal (view / edit / add medicine)")
    pdf.bullet("QuickPrescribeModal")
    pdf.bullet("clinicalMapper.js uiMedicinesToApiItems and apiToUiPrescription")
    pdf.bullet("DEFAULT_MEDICINE in doctor/constants.js")
    pdf.bullet("Patient history / prescription print if it lists medicines")
    pdf.body(
        "Also add: per-card delete, + Add medicine, info text "
        "'Prescription is saved when you click Save Consultation.', "
        "and 0/200 counter on special instructions."
    )

    pdf.section_title("10. Nurse (read-only display)")
    pdf.body(
        "GET /nurse/medications/patient/{patient_id} medications[] now includes "
        "dosage, dose, form, route, timing, quantity, quantity_unit, instructions."
    )
    pdf.callout(
        "Current nurse mapper",
        "Today nurseMapper maps dose from dosage first (item.dosage ?? item.dose). "
        "After backend returns both, Dosage column still shows Strength until you "
        "change the mapper to: dose: item.dose, and keep dosage/strength separate. "
        "Route already prefers item.route, then instructions. Once doctors send "
        "route, Route column shows Oral instead of After food. That is correct."
    )
    pdf.sub_title("Recommended nurse mapping")
    pdf.code_block(
        """
{
  medicine_name: item.medicine_name,
  strength: item.dosage,          // 500 mg
  dose: item.dose,                // 1
  form: item.form,
  route: item.route,
  timing: item.timing,
  frequency: item.frequency,
  duration: item.duration,
  quantity: item.quantity,
  quantity_unit: item.quantity_unit,
  instructions: item.instructions
}
"""
    )
    pdf.bullet("Do not let nurses create or edit prescription fields")
    pdf.bullet("Null-safe: show '-' when a field is null (old prescriptions)")
    pdf.bullet("Optional extra columns: Form, Timing, Quantity")

    pdf.section_title("11. Pharmacy")
    pdf.body(
        "Pharmacy detail items[] now include form, dose, route, timing, quantity, "
        "quantity_unit. quantity_prescribed uses item.quantity when it is a "
        "positive integer. Old prescriptions still use duration as supply count."
    )
    pdf.bullet("Show Strength from dosage, Dose from dose, Form, Route, Timing")
    pdf.bullet("Total quantity: prefer quantity + quantity_unit when present")
    pdf.bullet("quantity_prescribed / quantity_dispensed / quantity_remaining unchanged")
    pdf.bullet("Do not write prescription fields; pharmacist only dispenses")

    pdf.section_title("12. Lab")
    pdf.body(
        "No backend change for lab. Lab orders stay on the Lab and Follow-up tab. "
        "Do not mix lab test payload with prescription items. If product later "
        "wants lab to see medicines, read the same prescription GET items[] "
        "(read-only): medicine_name, dose, route, timing, instructions."
    )

    pdf.section_title("13. Validation rules (frontend)")
    pdf.bullet("If medicine_name is filled, require duration > 0 (already in UI)")
    pdf.bullet("When new card is live: also require dosage, form, dose, route, frequency, quantity")
    pdf.bullet("quantity integer >= 1; omit key if the row is unused")
    pdf.bullet("instructions max 200 characters")
    pdf.bullet("Do not send duration as 0; backend still requires duration text")
    pdf.bullet("Empty optional strings are OK; backend converts them to null")

    pdf.section_title("14. Files frontend will change (later)")
    pdf.bullet("src/features/doctor/constants.js")
    pdf.bullet("src/features/doctor/components/ConsultationModal.jsx")
    pdf.bullet("src/features/doctor/components/PrescriptionDetailModal.jsx")
    pdf.bullet("src/features/doctor/components/QuickPrescribeModal.jsx")
    pdf.bullet("src/shared/api/mappers/clinicalMapper.js")
    pdf.bullet("src/shared/api/mappers/nurseMapper.js  (dose/route mapping)")
    pdf.bullet("Nurse medication tables / patient overview")
    pdf.bullet("Pharmacy prescription detail / dispense table (optional columns)")

    pdf.section_title("15. QA checklist")
    pdf.bullet("OLD UI: save consultation with only 6 fields still succeeds")
    pdf.bullet("OLD UI: reload prescription; existing 6 fields still populated")
    pdf.bullet("NEW UI: save all extra fields; GET returns the same values")
    pdf.bullet("NEW UI: omit timing/instructions; they come back as null")
    pdf.bullet("Nurse: old Rx still lists medicine/dosage/frequency")
    pdf.bullet("Nurse: new Rx can show route/dose when mapper is updated")
    pdf.bullet("Pharmacy: old Rx quantity_prescribed still derived from duration")
    pdf.bullet("Pharmacy: new Rx with quantity=10 uses 10 as prescribed supply")
    pdf.bullet("IPD consult save with admission_id still works")
    pdf.bullet("Add second medicine; both items persist extra fields")

    pdf.section_title("16. Backend note for local runs")
    pdf.code_block(
        """
cd HM-System-Backend
alembic upgrade head
"""
    )
    pdf.body(
        "Migration c2d3e4f5g6h7 adds nullable columns on prescription_items. "
        "Until it is applied, SQLAlchemy will error on the new fields. "
        "No permission or seed change. No frontend deploy is required for "
        "current screens to keep working after the migration."
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
