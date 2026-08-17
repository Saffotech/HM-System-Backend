"""Generator: Lab OPD/IPD + ward/bed frontend guide (matches shipped backend)."""
from pathlib import Path

from fpdf import FPDF

OUT = (
    Path(__file__).resolve().parent
    / "frontend-lab-opd-ipd-ward-bed-changes.pdf"
)


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Lab Module: OPD / IPD, Ward and Bed (Frontend Guide)",
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
                "  " + safe[:105],
                new_x="LMARGIN",
                new_y="NEXT",
                fill=True,
            )
        self.ln(2)

    def table_row(
        self,
        cols: list[str],
        bold: bool = False,
        widths: list[float] | None = None,
    ):
        if widths is None:
            widths = [self.epw / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        y0 = self.get_y()
        x0 = self.l_margin
        for i, col in enumerate(cols):
            self.set_xy(x0 + sum(widths[:i]), y0)
            self.cell(widths[i], 6, col[:55], border=1)
        self.ln()


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, "Lab Orders: OPD / IPD, Ward and Bed")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Frontend Developer Guide")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body(
        "Date: 17 August 2026  |  Audience: Frontend (Lab module)  |  "
        "Scope: Show visit type, ward and bed on lab ordered tests."
    )
    pdf.callout(
        "IMPORTANT",
        "Backend for these fields is ALREADY DONE. Do not change backend files. "
        "Lab screens still hide the data because the mapper and UI were not updated. "
        "This PDF is frontend-only work.",
    )

    # ------------------------------------------------------------------
    pdf.section_title("1. Status of the original gaps")
    pdf.body(
        "Earlier, none of this was visible in lab. Backend now returns the visit "
        "fields. Frontend still does not map or display them."
    )
    w = [pdf.epw * 0.42, pdf.epw * 0.22, pdf.epw * 0.36]
    pdf.table_row(["Requirement", "Backend", "Frontend / Lab UI"], bold=True, widths=w)
    pdf.table_row(
        ["Lab sees OPD or IPD on ordered test", "DONE", "MISSING - not mapped, not shown"],
        widths=w,
    )
    pdf.table_row(
        ["Lab sees ward", "DONE", "MISSING - not mapped, not shown"],
        widths=w,
    )
    pdf.table_row(
        ["Lab sees bed", "DONE", "MISSING - not mapped, not shown"],
        widths=w,
    )
    pdf.table_row(
        ["Source = this visit (not UHID desk)", "DONE", "MISSING - use encounter_type"],
        widths=w,
    )
    pdf.ln(2)
    pdf.body(
        "registration_source was already on the lab API before this work. "
        "It is still returned. Do NOT use it for the OPD/IPD badge on lab screens. "
        "Use encounter_type."
    )

    # ------------------------------------------------------------------
    pdf.section_title("2. What the technician should see")
    pdf.body(
        "Doctor orders a test. Lab already receives that order on Pending Tests. "
        "On that same row, lab must know if the patient is currently OPD or IPD, "
        "and if IPD, which ward and bed to collect the sample from."
    )
    w4 = [pdf.epw * 0.28, pdf.epw * 0.14, pdf.epw * 0.28, pdf.epw * 0.14, pdf.epw * 0.16]
    pdf.table_row(["Patient", "Visit", "Ward", "Bed", "Test"], bold=True, widths=w4)
    pdf.table_row(["Rahul Sharma", "IPD", "General Ward", "G-02", "CBC"], widths=w4)
    pdf.table_row(["Priya Nair", "OPD", "-", "-", "LFT"], widths=w4)
    pdf.ln(2)
    pdf.bullet("OPD: patient comes to the lab. Ward and bed show as dash (-).")
    pdf.bullet("IPD: patient is admitted. Lab goes to the ward and bed.")
    pdf.bullet(
        "Location is live. If the patient is transferred before collection, "
        "the next GET /lab/orders shows the new bed."
    )

    # ------------------------------------------------------------------
    pdf.section_title("3. registration_source vs encounter_type")
    pdf.body(
        "Both fields are strings: OPD or IPD. They answer different questions. "
        "Using the wrong one will send lab to the wrong place."
    )
    w3 = [pdf.epw * 0.28, pdf.epw * 0.36, pdf.epw * 0.36]
    pdf.table_row(["Field", "Meaning", "Use on lab UI?"], bold=True, widths=w3)
    pdf.table_row(
        [
            "registration_source",
            "Which desk created the UHID. Permanent.",
            "No. Do not badge this.",
        ],
        widths=w3,
    )
    pdf.table_row(
        [
            "encounter_type",
            "This visit now. IPD if admitted, else OPD.",
            "YES. This is the badge.",
        ],
        widths=w3,
    )
    pdf.table_row(
        [
            "ward_name / bed_number",
            "From active IPD admission.",
            "YES. Empty for OPD.",
        ],
        widths=w3,
    )
    pdf.ln(2)
    pdf.sub_title("Why registration_source is wrong for lab")
    pdf.bullet(
        "UHID created in OPD, later admitted: registration_source stays OPD, "
        "but encounter_type is IPD with a real ward and bed."
    )
    pdf.bullet(
        "UHID created in IPD, later discharged, OPD test: registration_source "
        "stays IPD, but encounter_type is OPD and ward/bed are null."
    )
    pdf.callout(
        "RULE",
        "Badge = encounter_type. Ward/bed only when encounter_type is IPD. "
        "If ward/bed are null, show dash. Never invent a ward from registration_source.",
    )

    # ------------------------------------------------------------------
    pdf.section_title("4. Backend contract (already live)")
    pdf.body("No new lab routes. Existing responses gained extra fields.")
    pdf.sub_title("4.1 Endpoints")
    we = [pdf.epw * 0.42, pdf.epw * 0.58]
    pdf.table_row(["Method / URL", "Where the new fields sit"], bold=True, widths=we)
    pdf.table_row(["GET /lab/orders", "Each item in items[]"], widths=we)
    pdf.table_row(["GET /lab/orders/{id}", "Top-level order object"], widths=we)
    pdf.table_row(["GET /lab/reports", "Each item in items[]"], widths=we)
    pdf.table_row(["GET /lab/reports/{id}", "Nested object: order"], widths=we)
    pdf.ln(2)
    pdf.sub_title("4.2 New / relevant fields")
    wf = [pdf.epw * 0.28, pdf.epw * 0.18, pdf.epw * 0.54]
    pdf.table_row(["JSON field", "Type", "Notes"], bold=True, widths=wf)
    pdf.table_row(
        ["encounter_type", "string", "OPD or IPD. Default OPD if omitted."],
        widths=wf,
    )
    pdf.table_row(
        ["ward_name", "string|null", "Null for OPD. Ward name, not a number."],
        widths=wf,
    )
    pdf.table_row(
        ["bed_number", "string|null", "Null for OPD. Example: G-02"],
        widths=wf,
    )
    pdf.table_row(
        ["admission_id", "int|null", "Null for OPD. Optional for UI."],
        widths=wf,
    )
    pdf.table_row(
        ["registration_source", "string", "Still present. Ignore for badge."],
        widths=wf,
    )
    pdf.ln(2)
    pdf.body(
        "encounter_type: str = \"OPD\" in the schema is only a fallback when the "
        "field is missing. The service sets IPD when an active admission exists."
    )

    pdf.sub_title("4.3 Example: OPD patient")
    pdf.code_block(
        """
{
  "id": 184,
  "patient_name": "Priya Nair",
  "patient_uid": "P-1205",
  "registration_source": "OPD",
  "encounter_type": "OPD",
  "admission_id": null,
  "ward_name": null,
  "bed_number": null,
  "test_name": "LFT"
}
"""
    )

    pdf.sub_title("4.4 Example: IPD patient (UHID may still be OPD)")
    pdf.code_block(
        """
{
  "id": 185,
  "patient_name": "Rahul Sharma",
  "patient_uid": "P-1188",
  "registration_source": "OPD",
  "encounter_type": "IPD",
  "admission_id": 42,
  "ward_name": "General Ward",
  "bed_number": "G-02",
  "test_name": "CBC"
}
"""
    )
    pdf.body(
        "In 4.4 registration_source is OPD (UHID desk) but encounter_type is IPD. "
        "Lab must show IPD + General Ward + G-02."
    )

    # ------------------------------------------------------------------
    pdf.add_page()
    pdf.section_title("5. What is missing in the Lab frontend")
    pdf.callout(
        "CURRENT STATE",
        "API already sends the fields. labMapper.js drops them. Lab pages never "
        "render Source, Ward or Bed. Extra JSON does not break the UI; it is ignored.",
    )

    pdf.sub_title("5.1 Mapper (must do first)")
    wm = [pdf.epw * 0.52, pdf.epw * 0.48]
    pdf.table_row(["File", "Gap"], bold=True, widths=wm)
    pdf.table_row(
        [
            "src/shared/api/mappers/labMapper.js",
            "apiToUiLabOrder ignores the new fields",
        ],
        widths=wm,
    )
    pdf.table_row(
        [
            "same file: apiToUiLabReport",
            "Drops encounter_type, ward, bed",
        ],
        widths=wm,
    )
    pdf.table_row(
        [
            "same file: apiToUiLabReportDetail",
            "Reads order.* but not visit location",
        ],
        widths=wm,
    )
    pdf.ln(2)
    pdf.body("No new API client file is required. GET /lab/orders is already wired.")

    pdf.sub_title("5.2 Screens that must show the fields")
    ws = [pdf.epw * 0.52, pdf.epw * 0.48]
    pdf.table_row(["File", "What is missing"], bold=True, widths=ws)
    pdf.table_row(
        [
            "features/lab/pages/LabOrderListPage.jsx",
            "No Source / Ward / Bed columns",
        ],
        widths=ws,
    )
    pdf.table_row(
        [
            "features/lab/components/LabDashboardRemainingTests.jsx",
            "Only name, test, UHID, time",
        ],
        widths=ws,
    )
    pdf.table_row(
        [
            "features/lab/pages/LabUploadReportPage.jsx",
            "Info panel has no visit / location",
        ],
        widths=ws,
    )
    pdf.ln(2)

    pdf.sub_title("5.3 Screens that should also show them (recommended)")
    pdf.table_row(["File", "What is missing"], bold=True, widths=ws)
    pdf.table_row(
        [
            "features/lab/pages/LabCompletedReportsPage.jsx",
            "Archive table has no Source/Ward/Bed",
        ],
        widths=ws,
    )
    pdf.table_row(
        [
            "features/lab/components/LabReportDetailModal.jsx",
            "Detail panel has no visit / location",
        ],
        widths=ws,
    )
    pdf.table_row(
        [
            "features/lab/utils/labReportUtils.js",
            "Print + CSV omit visit / location",
        ],
        widths=ws,
    )
    pdf.ln(2)

    pdf.sub_title("5.4 Do not change")
    pdf.bullet("HM-System-Backend (already shipped)")
    pdf.bullet("Lab routes, hooks, query keys, GET URLs")
    pdf.bullet("Doctor consultation / create-lab-test flow")
    pdf.bullet("IPD admission create/edit screens")

    # ------------------------------------------------------------------
    pdf.section_title("6. Frontend implementation")
    pdf.sub_title("6.1 Mapper - add to apiToUiLabOrder")
    pdf.body(
        "apiToUiLabOrderDetail already spreads apiToUiLabOrder, so order detail "
        "and upload page pick this up automatically after this change."
    )
    pdf.code_block(
        """
encounterType: row.encounter_type ?? row.encounterType ?? 'OPD',
admissionId: row.admission_id ?? row.admissionId ?? null,
wardName: row.ward_name ?? row.wardName ?? null,
bedNumber: row.bed_number ?? row.bedNumber ?? null,
"""
    )
    pdf.body(
        "Also add the same four fields in apiToUiLabReport (from the report row) "
        "and apiToUiLabReportDetail (from row.order)."
    )
    pdf.callout(
        "DO NOT",
        "Do not map registration_source into the badge. You may keep "
        "registrationSource for debugging, but the UI label must be encounterType.",
    )

    pdf.sub_title("6.2 Display helper (suggested)")
    pdf.code_block(
        """
function visitLocationLabel(order) {
  const visit = order.encounterType === 'IPD' ? 'IPD' : 'OPD';
  if (visit !== 'IPD') return { visit, ward: '-', bed: '-' };
  return {
    visit: 'IPD',
    ward: order.wardName || '-',
    bed: order.bedNumber || '-',
  };
}
"""
    )

    pdf.sub_title("6.3 Pending Tests table (required)")
    pdf.body("LabOrderListPage.jsx current columns: Request ID, Patient Name, Patient ID, Doctor, Test, Priority, Requested, Status, Action.")
    pdf.body("Add three columns after Patient ID (or after Patient Name):")
    pdf.bullet("Source  -> badge from encounterType (OPD / IPD)")
    pdf.bullet("Ward    -> wardName or dash")
    pdf.bullet("Bed     -> bedNumber or dash")
    pdf.body(
        "If the table is too wide, one column 'Ward / Bed' is OK: "
        "'General Ward / G-02' for IPD, dash for OPD."
    )

    pdf.sub_title("6.4 Dashboard remaining tests (required)")
    pdf.body(
        "LabDashboardRemainingTests.jsx: under the patient name or in meta, "
        "show OPD, or IPD plus ward and bed. Example: 'IPD · General Ward · G-02'."
    )

    pdf.sub_title("6.5 Upload report header (required)")
    pdf.body(
        "LabUploadReportPage.jsx info panel: add Source, Ward, Bed next to "
        "Patient Name / Patient ID. Technicians need location while working the sample."
    )

    pdf.sub_title("6.6 Completed reports (recommended)")
    pdf.body(
        "Add the same fields on LabCompletedReportsPage and LabReportDetailModal. "
        "If the patient is already discharged, encounter_type will be OPD and "
        "ward/bed null (live join). Show dash. Do not hide the report."
    )

    # ------------------------------------------------------------------
    pdf.add_page()
    pdf.section_title("7. UI rules")
    pdf.bullet("Badge text: exactly OPD or IPD (uppercase, from encounter_type).")
    pdf.bullet("OPD: ward and bed must be dash, never 'N/A ward'.")
    pdf.bullet("IPD with missing ward/bed: still show IPD, dash for empty location.")
    pdf.bullet("Do not filter the list by OPD/IPD unless product asks later.")
    pdf.bullet("There is no encounter_type query param on GET /lab/orders yet.")
    pdf.bullet("Do not call IPD or nurse bed APIs from lab. Lab payload is enough.")
    pdf.ln(1)
    pdf.sub_title("Suggested badge styling")
    pdf.bullet("OPD: existing lab-badge style, neutral / blue.")
    pdf.bullet("IPD: distinct colour (match IPD patient list chips if possible).")
    pdf.bullet("Ward / bed: match IPD chips on IpdPatientListPage if easy; plain text is fine.")

    # ------------------------------------------------------------------
    pdf.section_title("8. Test plan")
    pdf.bullet(
        "OPD-only patient with a lab order: Source=OPD, Ward=-, Bed=-. "
        "Pending Tests, dashboard remaining, and upload header all agree."
    )
    pdf.bullet(
        "Admitted IPD patient with a lab order: Source=IPD and the current "
        "ward/bed from IPD (same values nurse/IPD see)."
    )
    pdf.bullet(
        "Patient registered in OPD then admitted: registration_source may be OPD, "
        "but the badge MUST be IPD with ward/bed."
    )
    pdf.bullet("Transfer bed in IPD, refresh lab list: new ward/bed appear.")
    pdf.bullet("Discharge the patient, refresh lab list: badge becomes OPD, location dash.")
    pdf.bullet("Existing lab actions still work: sample collected, upload, complete.")
    pdf.bullet("Lab dashboard counts and filters are unchanged.")

    # ------------------------------------------------------------------
    pdf.section_title("9. Out of scope (do not build in this ticket)")
    pdf.bullet(
        "Doctors ordering tests from an IPD visit (lab orders still require an "
        "OPD appointment_id). If the patient is also admitted, lab still sees IPD + bed."
    )
    pdf.bullet("New lab census / ward board. Stay on the existing order worklist.")
    pdf.bullet("Backend schema, lab_service, or new query filters.")
    pdf.bullet("Using registration_source as the visible Source column.")

    # ------------------------------------------------------------------
    pdf.section_title("10. File checklist")
    wc = [pdf.epw * 0.12, pdf.epw * 0.52, pdf.epw * 0.36]
    pdf.table_row(["Need", "File", "Change"], bold=True, widths=wc)
    pdf.table_row(
        ["MUST", "shared/api/mappers/labMapper.js", "Map encounterType, ward, bed"],
        widths=wc,
    )
    pdf.table_row(
        ["MUST", "features/lab/pages/LabOrderListPage.jsx", "Columns: Source, Ward, Bed"],
        widths=wc,
    )
    pdf.table_row(
        ["MUST", "lab/.../LabDashboardRemainingTests.jsx", "Show visit + location"],
        widths=wc,
    )
    pdf.table_row(
        ["MUST", "features/lab/pages/LabUploadReportPage.jsx", "Info panel location"],
        widths=wc,
    )
    pdf.table_row(
        ["NICE", "features/lab/pages/LabCompletedReportsPage.jsx", "Archive columns"],
        widths=wc,
    )
    pdf.table_row(
        ["NICE", "lab/.../LabReportDetailModal.jsx", "Detail location fields"],
        widths=wc,
    )
    pdf.table_row(
        ["NICE", "features/lab/utils/labReportUtils.js", "Print/CSV columns"],
        widths=wc,
    )
    pdf.ln(2)
    pdf.callout(
        "DONE WHEN",
        "A lab technician opening Pending Tests can tell, for every ordered test, "
        "whether the patient is OPD or IPD, and if IPD, the ward name and bed number, "
        "without opening IPD or nurse screens.",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
