"""Generator: Nurse MAR OPD/IPD source fields - Frontend Developer Guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = (
    Path(__file__).resolve().parent
    / "nurse-medication-opd-ipd-source-frontend-guide.pdf"
)


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Nurse Medications OPD/IPD Source (Frontend Guide)",
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
            remaining = safe
            while remaining:
                chunk = remaining[:108]
                remaining = remaining[108:]
                self.set_x(self.l_margin)
                self.cell(
                    self.epw,
                    4.5,
                    "  " + chunk,
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
        if self.get_y() > self.h - 28:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        row_h = 6
        max_h = row_h
        for i, col in enumerate(cols):
            lines = max(1, (len(col) // max(1, int(widths[i] / 1.7))) + 1)
            max_h = max(max_h, lines * 4.5)
        for i, col in enumerate(cols):
            self.set_xy(x0 + sum(widths[:i]), y0)
            self.multi_cell(widths[i], 4.5, col[:90], border=1)
        self.set_y(y0 + max(max_h, row_h))


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, "Nurse Medications: OPD vs IPD Source")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Frontend Developer Guide")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body(
        "Date: 31 August 2026. Backend is already shipped. Current nurse screens "
        "keep working with no frontend change. New fields are additive. Extra JSON "
        "keys are ignored until you display them."
    )

    pdf.callout(
        "Compatibility (do not break current UI)",
        "All previous keys on GET /nurse/medications/patient/{patient_id} are "
        "unchanged. Administer APIs are unchanged. The nurse can still see every "
        "medicine (OPD + IPD) and can still administer them. This change only "
        "labels each medicine so the UI can show that it came from OPD and which "
        "doctor prescribed it.",
    )

    pdf.section_title("1. What changed")
    pdf.body(
        "Nurse MAR still returns all prescription items for the patient. Each "
        "item now includes the encounter source and the prescribing doctor."
    )
    pdf.bullet("Workflow: unchanged (view all medicines, administer still allowed).")
    pdf.bullet("New per-item label: source = OPD or IPD.")
    pdf.bullet("New per-item doctor: doctor_id + doctor_name of the doctor who wrote that Rx.")
    pdf.bullet("Frontend was not modified. Display the new fields when you are ready.")

    pdf.section_title("2. Endpoint (no URL change)")
    pdf.body("Permission: nurse_medication:view")
    pdf.code_block("GET /nurse/medications/patient/{patient_id}")
    pdf.body("Unchanged endpoints (no payload change for this feature):")
    pdf.bullet("GET /nurse/medications/patients  (patient list)")
    pdf.bullet("POST /nurse/medications/administer")
    pdf.bullet("PUT /nurse/medications/administer/{administration_id}")
    pdf.bullet("GET /nurse/medications/history and GET /nurse/medications/history/{patient_id}")

    pdf.section_title("3. How to detect OPD vs IPD")
    pdf.body("Use medications[].source. Do not guess from the page-level doctor_name.")
    w = [32, 50, 48, 50]
    pdf.table_row(
        ["source", "Meaning", "appointment_id", "admission_id"],
        bold=True,
        widths=w,
    )
    pdf.table_row(
        ["OPD", "Prescribed in an OPD visit", "number (set)", "null"],
        widths=w,
    )
    pdf.table_row(
        ["IPD", "Prescribed on an IPD admission", "null", "number (set)"],
        widths=w,
    )
    pdf.ln(2)
    pdf.code_block(
        "const isOpd = item.source === 'OPD';\n"
        "const isIpd = item.source === 'IPD';"
    )
    pdf.callout(
        "Do not use top-level doctor_name as the prescriber",
        "Response.doctor_name is still the IPD attending / ward doctor for the "
        "patient (same as before). For each medicine row, use "
        "medications[].doctor_name (the doctor who prescribed that medicine). "
        "An OPD medicine can have a different doctor than the IPD attending.",
    )

    pdf.section_title("4. Field map for the nurse table")
    pdf.body("Keep existing columns. Add Source and Prescribed by when you update UI.")
    w2 = [42, 40, 28, 70]
    pdf.table_row(["UI label", "API key", "Required", "Example"], bold=True, widths=w2)
    rows = [
        ["Medicine", "medicine_name", "Yes (old)", "Paracetamol"],
        ["Strength", "dosage", "Yes (old)", "500 mg"],
        ["Form", "form", "No (old)", "Tablet"],
        ["Duration", "duration", "Yes (old)", "5 Days"],
        ["Frequency", "frequency", "Yes (old)", "1-0-1"],
        ["Route", "route", "No (old)", "Oral"],
        ["Timing", "timing", "No (old)", "After food"],
        ["Instruction", "instructions", "No (old)", "Take with water"],
        ["Source (NEW)", "source", "Always set", "OPD or IPD"],
        ["Prescribed by (NEW)", "doctor_name", "If doctor exists", "Dr. Sharma"],
        ["Prescribing doctor id", "doctor_id", "If doctor exists", "12"],
        ["OPD visit id", "appointment_id", "OPD only", "88"],
        ["IPD admission id", "admission_id", "IPD only", "41"],
        ["Parent prescription id", "prescription_id", "Always set", "301"],
    ]
    for row in rows:
        pdf.table_row(row, widths=w2)
    pdf.ln(2)

    pdf.section_title("5. Suggested UI (when frontend is ready)")
    pdf.body("Recommended on NursePatientMedicationsPage and the patient overview Meds tab:")
    pdf.bullet("Keep the current medicine table and Administer / Record dose buttons.")
    pdf.bullet("On the medicine name cell, show a small badge: OPD or IPD.")
    pdf.bullet("Under the name (or a new column), show Prescribed by: Dr. ...")
    pdf.bullet("Example OPD row: Paracetamol 500 mg  [OPD]  Dr. Sharma")
    pdf.bullet("Example IPD row: Ceftriaxone 1g  [IPD]  Dr. Patel")
    pdf.body(
        "mapper already reads item.doctor_name in mapMedicationToPrescription "
        "(nurseMapper.js). After this API change, that mapped doctor_name is the "
        "prescribing doctor, not the ward attending doctor. You still need to "
        "render source and doctor_name in the table; they are not shown today."
    )

    pdf.section_title("6. Example response")
    pdf.body("Existing keys first; new keys at the end of each medications[] object.")
    pdf.code_block(
        """{
  "patient_id": 15,
  "patient_uid": "P-1028",
  "patient_name": "Anita Desai",
  "bed_number": "B-12",
  "ward_name": "General",
  "doctor_id": 7,
  "doctor_name": "Dr. Patel",
  "medications": [
    {
      "prescription_item_id": 501,
      "prescription_id": 301,
      "medicine_name": "Paracetamol",
      "dosage": "500 mg",
      "form": "Tablet",
      "route": "Oral",
      "timing": "After food",
      "frequency": "1-0-1",
      "duration": "5 Days",
      "quantity": 10,
      "instructions": "Take with water",
      "source": "OPD",
      "appointment_id": 88,
      "admission_id": null,
      "doctor_id": 4,
      "doctor_name": "Dr. Sharma"
    },
    {
      "prescription_item_id": 610,
      "prescription_id": 340,
      "medicine_name": "Ceftriaxone",
      "dosage": "1 g",
      "form": "Injection",
      "route": "IV",
      "timing": null,
      "frequency": "1-0-1",
      "duration": "3 Days",
      "quantity": 6,
      "instructions": null,
      "source": "IPD",
      "appointment_id": null,
      "admission_id": 41,
      "doctor_id": 7,
      "doctor_name": "Dr. Patel"
    }
  ]
}"""
    )

    pdf.section_title("7. What frontend must NOT do")
    pdf.bullet("Do not require the new fields to render the current table.")
    pdf.bullet("Do not hide OPD medicines. Current workflow still shows all items.")
    pdf.bullet("Do not disable Administer for OPD. Backend still allows it.")
    pdf.bullet("Do not copy OPD medicines into a new IPD prescription on the client.")
    pdf.bullet("Do not replace medications[].doctor_name with response.doctor_name.")
    pdf.bullet("Do not treat missing source as an error; default display to IPD if needed.")

    pdf.section_title("8. Optional display snippet")
    pdf.code_block(
        """function sourceBadge(item) {
  const source = String(item.source || '').toUpperCase();
  if (source === 'OPD') return 'OPD';
  if (source === 'IPD') return 'IPD';
  return item.admission_id != null ? 'IPD' : 'OPD';
}

function prescribedBy(item) {
  return item.doctor_name || item.prescribed_by_name || '—';
}

// Medicine cell:
//   {item.medicine_name}
//   [{sourceBadge(item)}]  {prescribedBy(item)}
"""
    )

    pdf.section_title("9. Current nurse pages to update later")
    pdf.bullet("NursePatientMedicationsPage.jsx  (MAR / Administer table)")
    pdf.bullet("NursePatientOverviewPage.jsx  (Meds tab also has Administer)")
    pdf.bullet("shared/api/mappers/nurseMapper.js  (mapMedicationToPrescription already maps doctor_name)")
    pdf.body(
        "No API client URL change is needed. getPatientMedications already calls "
        "GET /nurse/medications/patient/{id}."
    )

    pdf.callout(
        "Summary",
        "Backend added source + prescribing doctor on each MAR medicine. Old UI "
        "keeps working. When frontend is ready, show an OPD/IPD badge and the "
        "prescribing doctor name next to each medicine.",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
