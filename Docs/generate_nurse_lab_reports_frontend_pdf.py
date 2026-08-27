"""Generator: Nurse Lab Reports (read-only) - Frontend Developer Guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "nurse-lab-reports-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Nurse Lab Reports Frontend Guide",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, title)
        self.ln(1)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, f"  - {text}")

    def callout(self, label: str, text: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 60, 20)
        self.multi_cell(0, 6, label)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)
        self.ln(1)

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        usable = self.w - self.l_margin - self.r_margin
        for line in text.strip("\n").splitlines():
            safe = line.encode("latin-1", "replace").decode("latin-1")
            while len(safe) > 95:
                self.cell(
                    usable,
                    4.5,
                    "  " + safe[:95],
                    new_x="LMARGIN",
                    new_y="NEXT",
                    fill=True,
                )
                safe = safe[95:]
            self.cell(
                usable,
                4.5,
                "  " + safe,
                new_x="LMARGIN",
                new_y="NEXT",
                fill=True,
            )
        self.ln(2)

    def table_row(self, cols: list[str], widths: list[float] | None = None, bold: bool = False):
        usable = self.w - self.l_margin - self.r_margin
        if widths is None:
            widths = [usable / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        if self.get_y() > self.h - 28:
            self.add_page()
        x_start = self.l_margin
        y_start = self.get_y()
        row_h = 6
        max_h = row_h
        for i, col in enumerate(cols):
            lines = max(1, (len(col) // max(1, int(widths[i] / 1.7))) + 1)
            max_h = max(max_h, lines * 4.5)
        for i, col in enumerate(cols):
            self.set_xy(x_start + sum(widths[:i]), y_start)
            self.multi_cell(widths[i], 4.5, col, border=1)
        self.set_y(y_start + max(max_h, row_h))


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(0, 11, "Nurse Lab Reports\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: 24 August 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System-Backend (FastAPI)  |  Auth: JWT Bearer token\n"
        "Nurse prefix: /nurse/lab-reports  |  Read-only (view + download)",
    )
    pdf.ln(3)

    pdf.callout(
        "BACKEND IS DONE - FRONTEND IS NOT WIRED",
        "Use this guide to add a Nurse Lab Reports screen the same way Vitals and "
        "Nursing Notes work. Do NOT call lab technician APIs (/lab/reports). "
        "Do NOT add upload, edit, complete, or delete actions for nurses.",
    )

    pdf.section_title("1. Purpose")
    pdf.body(
        "Nurses must be able to view and download completed lab reports for patients "
        "who currently occupy a hospital bed. This matches the nurse clinical workflow "
        "(patient name + ward + bed + doctor), not the Lab Technician work queue."
    )
    pdf.bullet("VIEW list and report detail: YES")
    pdf.bullet("DOWNLOAD report file (PDF/image): YES")
    pdf.bullet("UPLOAD / UPDATE / DELETE / COMPLETE: NO")
    pdf.bullet("No new database tables. Reuses lab_test_orders + lab_results")
    pdf.bullet("No Alembic migration. After pull, run: python seed.py")

    pdf.section_title("2. Critical: do not reuse Lab Technician APIs")
    pdf.table_row(["Wrong (lab tech)", "Correct (nurse)"], [95, 95], bold=True)
    pdf.table_row(["GET /lab/reports", "GET /nurse/lab-reports"], [95, 95])
    pdf.table_row(["GET /lab/reports/{id}", "GET /nurse/lab-reports/{report_id}"], [95, 95])
    pdf.table_row(
        ["GET /lab/reports/{id}/file", "GET /nurse/lab-reports/{report_id}/file"],
        [95, 95],
    )
    pdf.ln(1)
    pdf.body(
        "GET /lab/reports is filtered by the lab technician department "
        "(Laboratory vs Radiology). A nurse token will 403 or see the wrong data. "
        "Do not reuse useLabReportsQuery, lab.js, or LabCompletedReportsPage."
    )

    pdf.section_title("3. Permission (one key only)")
    pdf.table_row(["Permission", "Role", "Used for"], [55, 30, 105], bold=True)
    pdf.table_row(
        ["nurse_lab_reports:view", "nurse", "List, detail, and file download"],
        [55, 30, 105],
    )
    pdf.ln(1)
    pdf.body(
        "All requests require: Authorization: Bearer <access_token>\n"
        "401 = token missing/expired. 403 = permission missing.\n"
        "There is NO nurse_lab_reports:create / update / delete."
    )
    pdf.bullet("Add key to useNursePermission.js (labReportsView)")
    pdf.bullet("Add key to seedPermissions.js and adminEditLocks.js nurse_clinical")
    pdf.bullet("Add a View-only group in nurseManagementConfig.js (Lab Reports)")
    pdf.bullet("Hide the nav item when the nurse does not have this permission")

    pdf.section_title("4. API endpoints (3 total)")
    pdf.table_row(["#", "Method", "URL", "Purpose"], [8, 18, 85, 79], bold=True)
    for row in [
        ("1", "GET", "/nurse/lab-reports", "Paginated report list"),
        ("2", "GET", "/nurse/lab-reports/{report_id}", "Report detail + parameters"),
        ("3", "GET", "/nurse/lab-reports/{report_id}/file", "Download file (blob)"),
    ]:
        pdf.table_row(list(row), [8, 18, 85, 79])
    pdf.ln(1)
    pdf.body("No POST / PUT / PATCH / DELETE under /nurse/lab-reports.")

    pdf.section_title("5. Patient scope (same All / Allocated bar as Vitals)")
    pdf.body(
        "Reuse NursePatientScopeContext. Pass ...scopeFilters on EVERY call "
        "(list, detail, and file). Detail and file also honor allocated_only. "
        "If you omit it on detail/file, the nurse can open a report that is not "
        "in the current Allocated list."
    )
    pdf.table_row(["Mode", "Query", "Who the nurse sees"], [32, 48, 110], bold=True)
    pdf.table_row(
        [
            "All (default)",
            "allocated_only omitted or false",
            "Reports for patients currently occupying ANY hospital bed",
        ],
        [32, 48, 110],
    )
    pdf.table_row(
        [
            "Allocated",
            "allocated_only=true",
            "Reports for patients on THIS nurse's allocated occupied beds",
        ],
        [32, 48, 110],
    )
    pdf.ln(1)
    pdf.callout(
        "NOT THE SAME AS LAB TECH OR OPD LAB HISTORY",
        "OPD patients with no occupied bed are excluded. Discharged patients "
        "drop out of the list when the bed is freed. This is intentional: "
        "nurses see reports for patients currently assigned to beds.",
    )
    pdf.body("Optional with allocated_only=true (same as vitals/notes):")
    pdf.bullet("assignment_date  (defaults to today IST)")
    pdf.bullet("shift_name       (defaults to current duty shift)")

    pdf.add_page()
    pdf.section_title("6. GET /nurse/lab-reports  List")
    pdf.sub_title("Query parameters")
    pdf.table_row(["Param", "Type", "Default", "Description"], [38, 22, 28, 102], bold=True)
    for row in [
        ("search", "string", "-", "Patient name, UHID, or test name"),
        ("patient_id", "int", "-", "Internal patient id (must be in scope)"),
        ("patient_uid", "string", "-", "UHID e.g. P-1037"),
        ("patient_name", "string", "-", "Name contains"),
        ("test_name", "string", "-", "Test name contains"),
        ("from_date", "date", "-", "YYYY-MM-DD (report created_at)"),
        ("to_date", "date", "-", "YYYY-MM-DD inclusive"),
        ("allocated_only", "bool", "false", "Allocated beds only"),
        ("assignment_date", "date", "-", "With allocated_only"),
        ("shift_name", "string", "-", "With allocated_only"),
        ("page", "int", "1", "Page number"),
        ("page_size", "int", "20", "Max 100"),
    ]:
        pdf.table_row(list(row), [38, 22, 28, 102])

    pdf.sub_title("Example request")
    pdf.code_block(
        "GET /nurse/lab-reports?search=CBC&allocated_only=true&page=1&page_size=20\n"
        "Authorization: Bearer <nurse_token>"
    )

    pdf.sub_title("Success response (200)")
    pdf.code_block(
        """{
  "success": true,
  "total": 2,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "report_id": 41,
      "order_id": 88,
      "patient_id": 1037,
      "patient_name": "Sumit Sharma",
      "patient_uid": "P-1037",
      "registration_source": "IPD",
      "encounter_type": "IPD",
      "admission_id": 12,
      "ward_name": "General",
      "bed_number": "G-12",
      "doctor_id": 9,
      "doctor_name": "Dr. Arora",
      "test_name": "CBC",
      "uploaded_by": 22,
      "uploaded_by_name": "Lab Tech One",
      "report_file": "uploads/lab_reports/....pdf",
      "uploaded_at": "2026-08-24T10:15:00+05:30",
      "status": "completed",
      "source": "BOTH"
    }
  ]
}"""
    )

    pdf.sub_title("List item fields to display")
    pdf.table_row(["API field", "UI label", "Notes"], [50, 40, 100], bold=True)
    for row in [
        ("patient_uid", "Patient ID", "Show UHID, never internal patient_id"),
        ("patient_name", "Patient Name", "Required column"),
        ("ward_name", "Ward", "From occupied bed; may be null"),
        ("bed_number", "Bed", "From occupied bed; may be null"),
        ("doctor_name", "Doctor", "Attending / ordering doctor with Dr. prefix"),
        ("test_name", "Test", "e.g. CBC, X-Ray Chest"),
        ("source", "Type", "PARAMETERS | PDF | BOTH | NONE"),
        ("uploaded_at", "Reported at", "ISO datetime IST"),
        ("status", "Status", "Usually completed"),
        ("report_file", "Has file", "Non-null => show Download"),
    ]:
        pdf.table_row(list(row), [50, 40, 100])
    pdf.ln(1)
    pdf.body(
        "source meaning: PARAMETERS = result values only, PDF = file only, "
        "BOTH = values + file, NONE = empty (rare; hide download)."
    )

    pdf.add_page()
    pdf.section_title("7. GET /nurse/lab-reports/{report_id}  Detail")
    pdf.body(
        "Use for a detail page or modal. Pass the same allocated_only / "
        "assignment_date / shift_name as the list that opened this report."
    )
    pdf.sub_title("Path")
    pdf.bullet("report_id = items[].report_id from the list (integer, not RPT-41)")
    pdf.sub_title("Query (same scope as list)")
    pdf.table_row(["Param", "Type", "Default"], [50, 40, 100], bold=True)
    pdf.table_row(["allocated_only", "bool", "false"], [50, 40, 100])
    pdf.table_row(["assignment_date", "date", "today IST if allocated"], [50, 40, 100])
    pdf.table_row(["shift_name", "string", "current shift if allocated"], [50, 40, 100])

    pdf.sub_title("Success response (200)  note id vs list report_id")
    pdf.body(
        "List uses report_id. Detail uses id for the same row. "
        "Map both: reportDbId = row.report_id ?? row.id"
    )
    pdf.code_block(
        """{
  "id": 41,
  "lab_test_order_id": 88,
  "uploaded_by": 22,
  "uploaded_by_name": "Lab Tech One",
  "sample_collected_at": "2026-08-24T09:00:00+05:30",
  "test_performed_at": "2026-08-24T10:00:00+05:30",
  "report_file": "uploads/lab_reports/....pdf",
  "remarks": "Within normal limits",
  "created_at": "2026-08-24T10:15:00+05:30",
  "file_name": "cbc-p1037.pdf",
  "file_type": "application/pdf",
  "file_size": 184320,
  "file_size_display": "180.0 KB",
  "source": "BOTH",
  "order": {
    "id": 88,
    "patient_id": 1037,
    "patient_name": "Sumit Sharma",
    "patient_uid": "P-1037",
    "registration_source": "IPD",
    "encounter_type": "IPD",
    "admission_id": 12,
    "ward_name": "General",
    "bed_number": "G-12",
    "doctor_id": 9,
    "doctor_name": "Dr. Arora",
    "department_id": 11,
    "test_name": "CBC",
    "category": "Hematology",
    "priority": "Normal",
    "status": "completed"
  },
  "parameters": [
    {
      "id": 1,
      "parameter_name": "Hemoglobin",
      "value": "13.2",
      "unit": "g/dL",
      "normal_range": "12-16",
      "flag": "normal"
    }
  ]
}"""
    )
    pdf.body(
        "parameter.flag is normal | low | high | null. Render a tone badge. "
        "If parameters is [] and report_file is set, show Download only."
    )

    pdf.section_title("8. GET /nurse/lab-reports/{report_id}/file  Download")
    pdf.body(
        "This is NOT JSON. Response is a file stream (FileResponse). "
        "Copy the lab technician blob pattern, but change the URL."
    )
    pdf.code_block(
        """const response = await fetch(
  `${API_BASE_URL}${API_PREFIX}/nurse/lab-reports/${reportId}/file?allocated_only=true`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const blob = await response.blob();
const fileName = parseContentDisposition(response) || `lab-report-${reportId}`;
// then URL.createObjectURL(blob) + <a download>"""
    )
    pdf.bullet("Pass the same allocated_only query string as the list")
    pdf.bullet("404 if no file uploaded, file missing on disk, or patient out of scope")
    pdf.bullet("Content-Type comes from the server (application/pdf or image/*)")
    pdf.bullet("Do not use apiClient JSON helper for this call")

    pdf.add_page()
    pdf.section_title("9. Errors")
    pdf.table_row(["Status", "When", "UI action"], [18, 85, 87], bold=True)
    for row in [
        ("401", "Missing/expired JWT", "Redirect to login"),
        ("403", "Missing nurse_lab_reports:view", "Hide nav and page"),
        ("404", "Unknown report_id OR patient not on an allowed occupied bed", "Show not found; do not leak why"),
        ("404", "File endpoint: no report_file or file gone from disk", "Hide Download / toast 'No file'"),
        ("200 + empty items", "No occupied beds, or no allocated beds this shift", "Empty state, not an error"),
    ]:
        pdf.table_row(list(row), [18, 85, 87])
    pdf.ln(1)
    pdf.body(
        "If allocated_only=true and the nurse has no bed allocations, total=0 and items=[]. "
        "Reuse the vitals empty copy: 'No beds assigned for this shift.'"
    )

    pdf.section_title("10. Suggested screens (mirror Vitals / Notes)")
    pdf.table_row(["Screen", "Route", "APIs"], [48, 62, 80], bold=True)
    for row in [
        ("Lab Reports registry", "/nurse/lab-reports", "GET /nurse/lab-reports"),
        ("Report detail", "/nurse/lab-reports/:reportId", "GET /{id} + optional file"),
        ("Patient overview tab", "/nurse/patients/:patientId", "GET list?patient_id="),
    ]:
        pdf.table_row(list(row), [48, 62, 80])
    pdf.ln(1)
    pdf.sub_title("Registry table columns (same pattern as NurseVitalsRegistryPage)")
    pdf.bullet("Patient ID (UHID) | Patient Name | Ward | Bed | Doctor | Test | Type | Reported at | Actions")
    pdf.bullet("Actions: View (always) + Download (only if report_file is set)")
    pdf.bullet("Row click can open detail. No Edit / Upload buttons.")
    pdf.bullet("Search box: send as search= (backend matches name, UHID, test name)")
    pdf.bullet("Pagination: page + page_size; use total from the payload")
    pdf.bullet("Wire NursePatientScopeBar: ...scopeFilters on the query")

    pdf.sub_title("Patient overview tab")
    pdf.body(
        "On NursePatientOverviewPage add a Lab Reports tab next to Vitals / Notes / Meds. "
        "Call GET /nurse/lab-reports?patient_id={id}&page_size=20 plus scopeFilters. "
        "If the patient is not currently on an occupied bed, the list is empty."
    )

    pdf.sub_title("Nav")
    pdf.body(
        "Add 'Lab Reports' to NurseLayout after Nursing Notes (or after Medications). "
        "Show only when canViewLabReports is true. Suggested icon: FlaskConical or FileSearch "
        "from lucide-react."
    )

    pdf.section_title("11. Frontend files to add or change")
    pdf.body("Do not modify lab technician feature files. Touch nurse + shared nurse API only.")
    pdf.code_block(
        """ADD
src/features/nurse/pages/NurseLabReportsRegistryPage.jsx
src/features/nurse/pages/NurseLabReportDetailPage.jsx   (or a modal)

CHANGE
src/features/nurse/api/nurse.js
  getLabReports(params, token)
  getLabReportById(reportId, params, token)
  fetchNurseLabReportFileBlob(reportId, params, token)  // raw fetch, not JSON

src/shared/hooks/queries/useNurseQuery.js
  useNurseLabReportsQuery(filters)
  useNurseLabReportQuery(reportId, filters)

src/shared/api/queryKeys.js
  nurse.labReports(filters)
  nurse.labReport(id, filters)

src/shared/api/mappers/nurseMapper.js
  mapLabReportItem(row)  // report_id, patient_uid, ward, bed, doctor_name
  // You MAY reuse mapApiVisitLocationFields from labMapper.js
  // Do NOT import lab services / lab query hooks

src/features/nurse/hooks/useNursePermission.js
  labReportsView: 'nurse_lab_reports:view'

src/features/nurse/components/NurseLayout.jsx
  nav link Lab Reports

src/routes/nurseRoutes.jsx
src/shared/constants/index.js
  NURSE_LAB_REPORTS, NURSE_LAB_REPORT_DETAIL

src/features/admin/nurse/constants/nurseManagementConfig.js
src/features/admin/constants/adminEditLocks.js
src/features/super-admin/constants/seedPermissions.js
  nurse_lab_reports:view  (view only)

OPTIONAL
src/features/nurse/pages/NursePatientOverviewPage.jsx
  Lab Reports tab"""
    )

    pdf.add_page()
    pdf.section_title("12. Suggested service wrappers")
    pdf.code_block(
        """// nurse.js
export function getNurseLabReports(params, token) {
  return apiClient(appendQuery('/nurse/lab-reports', params), { token });
}

export function getNurseLabReportById(reportId, params, token) {
  return apiClient(
    appendQuery(`/nurse/lab-reports/${reportId}`, params),
    { token }
  );
}

// file download: copy fetchLabReportFileBlob but URL =
// /nurse/lab-reports/${reportId}/file  + same query params"""
    )
    pdf.body(
        "Always forward allocated_only from scopeFilters. Example list call:"
    )
    pdf.code_block(
        """useNurseLabReportsQuery({
  search: debouncedSearch || undefined,
  page,
  page_size: 20,
  ...scopeFilters,   // { allocated_only: true } when Allocated mode
})"""
    )

    pdf.section_title("13. Display rules")
    pdf.bullet("Patient ID column = patient_uid (P-1037). Never show numeric patient_id.")
    pdf.bullet("Doctor column = doctor_name (already includes Dr. prefix). Fallback em dash.")
    pdf.bullet("Ward / Bed = ward_name / bed_number. Same cells as dashboard / vitals.")
    pdf.bullet("Empty ward/bed: show em dash. Do not invent values on the client.")
    pdf.bullet("Read-only: no forms, no file input, no status change buttons.")
    pdf.bullet("Print is optional; if you print, use detail JSON, do not call /lab print helpers that hit /lab/reports.")

    pdf.section_title("14. What backend already does (do not reimplement)")
    pdf.bullet("Occupied-bed filter (All) and allocated-bed filter (Allocated)")
    pdf.bullet("404 for out-of-scope report ids (treat as not found)")
    pdf.bullet("Doctor name snapshot with Dr. prefix")
    pdf.bullet("Ward/bed from the occupied bed row")
    pdf.bullet("Audit log on detail view and file download (Super Admin audit page)")
    pdf.bullet("Pagination total / page / page_size / items")

    pdf.section_title("15. Backend setup (local / devops)")
    pdf.code_block(
        """cd HM-System-Backend
python seed.py
# Adds nurse_lab_reports:view to the nurse role.
# No alembic migration for this feature."""
    )
    pdf.body(
        "Until seed.py is run, nurse calls return 403.\n"
        "Aligned with Routers/nurse_lab_report_router.py and "
        "Services/nurse_lab_report_service.py (24 August 2026)."
    )

    pdf.section_title("16. QA checklist for frontend")
    pdf.bullet("Nurse without permission: nav hidden, direct URL blocked")
    pdf.bullet("All mode: sees reports for any currently occupied bed")
    pdf.bullet("Allocated mode: only allocated occupied beds; empty if none assigned")
    pdf.bullet("Search by name / UHID / test name updates the list")
    pdf.bullet("View opens detail with parameters table")
    pdf.bullet("Download works for PDF and is hidden when report_file is null")
    pdf.bullet("OPD-only patient (no bed) never appears")
    pdf.bullet("Lab technician pages still use /lab/reports unchanged")
    pdf.bullet("No upload/edit UI anywhere in nurse module")

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
