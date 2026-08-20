"""Generator: Nurse Doctor Visits + Doctor Read-Only - Frontend Developer Guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "nurse-doctor-visits-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Nurse Doctor Visits Frontend Guide",
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

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        usable = self.w - self.l_margin - self.r_margin
        for line in text.strip().splitlines():
            while len(line) > 95:
                self.cell(
                    usable,
                    4.5,
                    "  " + line[:95],
                    new_x="LMARGIN",
                    new_y="NEXT",
                    fill=True,
                )
                line = line[95:]
            self.cell(usable, 4.5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table_row(self, cols: list[str], widths: list[float] | None = None, bold: bool = False):
        usable = self.w - self.l_margin - self.r_margin
        if widths is None:
            widths = [usable / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        if self.get_y() > self.h - 25:
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

    # Cover
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(0, 11, "Nurse Doctor Visits\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: August 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System-Backend (FastAPI)  |  Auth: JWT Bearer token\n"
        "Nurse prefix: /nurse/doctor-visits  |  Doctor prefix: /doctor/patient-visits",
    )
    pdf.ln(4)

    # 1. Purpose
    pdf.section_title("1. Purpose & Scope")
    pdf.body(
        "This document describes the new Nurse Doctor Visit Tracking APIs and the Doctor "
        "read-only Patient Visits API. Nurses log how many times a doctor checked a patient. "
        "Doctors can view visit counts and history for their patients (read-only).\n\n"
        "Backend is fully implemented. Frontend is NOT yet wired - use this guide to build "
        "the Nurse 'Doctor Visits' screen and the Doctor patient visit panel."
    )
    pdf.bullet("Single database table: nurse_doctor_visits")
    pdf.bullet("No separate summary API - compute KPIs client-side from GET list + bed patients")
    pdf.bullet("Visit numbers (Visit #1, #2) are computed by backend per patient per day")
    pdf.bullet("Void = soft delete; voided rows never appear in normal list/count")

    # 2. Permissions
    pdf.section_title("2. Permissions")
    pdf.table_row(["Permission", "Role", "Used for"], [55, 35, 100], bold=True)
    rows = [
        ("nurse_doctor_visits:view", "nurse", "GET list, GET doctors"),
        ("nurse_doctor_visits:create", "nurse", "POST log visit"),
        ("nurse_doctor_visits:update", "nurse", "PUT edit, PUT void"),
        ("doctor_patient_visits:view", "doctor", "GET patient visits (read-only)"),
    ]
    for row in rows:
        pdf.table_row(list(row), [55, 35, 100])
    pdf.ln(2)
    pdf.body(
        "All requests require: Authorization: Bearer <access_token>\n"
        "403 if permission missing. 401 if token expired."
    )

    # 3. Nurse APIs overview
    pdf.section_title("3. Nurse API Endpoints (5 total)")
    pdf.table_row(["#", "Method", "URL", "Purpose"], [8, 18, 72, 92], bold=True)
    nurse_apis = [
        ("1", "POST", "/nurse/doctor-visits", "Log a doctor visit"),
        ("2", "GET", "/nurse/doctor-visits", "List/filter visits"),
        ("3", "PUT", "/nurse/doctor-visits/{id}", "Correct doctor/time/notes"),
        ("4", "PUT", "/nurse/doctor-visits/{id}/void", "Void wrong/duplicate log"),
        ("5", "GET", "/nurse/doctor-visits/doctors", "Active doctors dropdown"),
    ]
    for api in nurse_apis:
        pdf.table_row(list(api), [8, 18, 72, 92])

    # 4. Doctor API
    pdf.section_title("4. Doctor API Endpoint (1 total - read-only)")
    pdf.table_row(["#", "Method", "URL", "Purpose"], [8, 18, 72, 92], bold=True)
    pdf.table_row(
        ["1", "GET", "/doctor/patient-visits", "Visit history + count for one patient"],
        [8, 18, 72, 92],
    )
    pdf.body("Doctor cannot call nurse POST/PUT/void endpoints.")

    # 5. Patient rules
    pdf.section_title("5. Patient Selection Rules (same as Vitals/Notes)")
    pdf.body("When logging a visit (POST), patient must be valid under existing nurse rules:")
    pdf.bullet("IPD: patient_id if patient currently occupies a bed")
    pdf.bullet("OPD: appointment_id from today's queue or patient appointments")
    pdf.bullet("Reject if: no appointment AND not on occupied bed")
    pdf.ln(1)
    pdf.body(
        "IMPORTANT: POST has NO allocated_only restriction. Nurse can log for ANY valid "
        "patient in the hospital.\n\n"
        "allocated_only applies ONLY to GET list (view filter), matching vitals/notes/beds "
        "scope bar behaviour:\n"
        "  allocated_only=false (default) = all visits\n"
        "  allocated_only=true = only visits for patients on nurse's allocated beds"
    )
    pdf.body("Reuse existing APIs for patient picker - do NOT build a new patient API:")
    pdf.bullet("GET /nurse/beds/patients - primary patient list")
    pdf.bullet("GET /nurse/beds/allocation-summary - Allocated / All toggle default")

    # 6. POST create
    pdf.add_page()
    pdf.section_title("6. POST /nurse/doctor-visits - Log Visit")
    pdf.sub_title("Request body")
    pdf.code_block(
        """{
  "patient_id": 1037,
  "doctor_id": 12,
  "visited_at": "2026-08-14T09:00:00+05:30",
  "notes": "Routine check, stable"
}"""
    )
    pdf.table_row(["Field", "Type", "Required", "Notes"], [35, 25, 20, 110], bold=True)
    create_fields = [
        ("patient_id", "number", "One of*", "For IPD / bed patients"),
        ("appointment_id", "number", "One of*", "For OPD queue patients"),
        ("doctor_id", "number", "Yes", "From GET /doctors - never free text"),
        ("visited_at", "datetime", "No", "Defaults to server now (IST)"),
        ("notes", "string", "No", "Free text observation"),
    ]
    for f in create_fields:
        pdf.table_row(list(f), [35, 25, 20, 110])
    pdf.ln(1)
    pdf.body(
        "*Provide patient_id OR appointment_id (same rule as vitals/notes).\n"
        "Server auto-sets (never send from frontend): recorded_by, recorded_by_name, created_at, "
        "doctor_name (snapshot from doctor_id)."
    )
    pdf.sub_title("Success response (201)")
    pdf.code_block(
        """{
  "id": 1,
  "patient_id": 1037,
  "patient_uid": "P-1037",
  "patient_name": "Sumit",
  "doctor_id": 12,
  "doctor_name": "Dr. Arora",
  "visited_at": "2026-08-14T09:00:00+05:30",
  "notes": "Routine check, stable",
  "visit_number": 1,
  "recorded_by": 45,
  "recorded_by_name": "Anita Sharma",
  "created_at": "2026-08-14T09:05:00+05:30",
  "updated_by": null,
  "updated_by_name": null,
  "updated_at": null,
  "is_voided": false
}"""
    )
    pdf.sub_title("Common errors")
    pdf.table_row(["Status", "detail", "UI action"], [18, 82, 90], bold=True)
    errors = [
        ("400", "patient_id is only allowed for patients...", "Show invalid patient message"),
        ("400", "Provide appointment_id or patient_id", "Require patient selection"),
        ("404", "Doctor not found", "Refresh doctors list"),
        ("404", "Patient not found", "Invalid patient"),
        ("403", "Missing permission", "Hide action / show hint"),
    ]
    for e in errors:
        pdf.table_row(list(e), [18, 82, 90])

    # 7. GET list
    pdf.section_title("7. GET /nurse/doctor-visits - List Visits")
    pdf.sub_title("Query parameters")
    pdf.table_row(["Param", "Type", "Default", "Description"], [35, 20, 20, 115], bold=True)
    list_params = [
        ("patient_id", "int", "-", "Filter by patient"),
        ("patient_uid", "string", "-", "Filter by UHID"),
        ("doctor_id", "int", "-", "Filter by visiting doctor"),
        ("visit_date", "date", "-", "IST calendar day e.g. 2026-08-14"),
        ("search", "string", "-", "Patient name/UHID, doctor name, notes"),
        ("allocated_only", "bool", "false", "Scope to nurse allocated beds"),
        ("assignment_date", "date", "-", "With allocated_only"),
        ("shift_name", "string", "-", "With allocated_only"),
        ("page", "int", "1", "Page number"),
        ("page_size", "int", "20", "Max 100"),
    ]
    for p in list_params:
        pdf.table_row(list(p), [35, 20, 20, 115])
    pdf.sub_title("Response")
    pdf.code_block(
        """{
  "total": 6,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 1,
      "patient_id": 1037,
      "patient_uid": "P-1037",
      "patient_name": "Sumit",
      "doctor_id": 12,
      "doctor_name": "Dr. Arora",
      "visited_at": "...",
      "notes": "Routine check, stable",
      "visit_number": 1,
      "recorded_by": 45,
      "recorded_by_name": "Anita Sharma",
      "is_voided": false
    }
  ]
}"""
    )
    pdf.body(
        "Only active (non-voided) visits returned. visit_number is computed per patient "
        "per IST calendar day, ordered by visited_at ASC."
    )

    # 8. KPI computation
    pdf.section_title("8. KPI Cards - Client-Side (no summary API)")
    pdf.body("Build dashboard KPIs by combining two existing calls:")
    pdf.code_block(
        """GET /nurse/beds/patients?page=1&page_size=100&allocated_only=true|false
GET /nurse/doctor-visits?visit_date=2026-08-14&allocated_only=true|false&page_size=100"""
    )
    pdf.table_row(["KPI", "How to compute"], [55, 135], bold=True)
    kpis = [
        ("Total Visits Today", "visits.items.length"),
        ("Patients Visited", "unique patient_id count in visits"),
        ("Not Yet Visited", "bedPatients without any visit today"),
        ("Most Visits", "max visit count grouped by patient_id"),
        ("Per-card badge", "visits filtered by patient_id .length"),
    ]
    for k in kpis:
        pdf.table_row(list(k), [55, 135])

    # 9. GET doctors
    pdf.add_page()
    pdf.section_title("9. GET /nurse/doctor-visits/doctors - Doctor Dropdown")
    pdf.body(
        "Returns ALL active registered doctors (role=doctor, is_active=true). "
        "Do NOT use department-then-doctor two-step picker unless product requires it."
    )
    pdf.sub_title("Query parameters")
    pdf.table_row(["Param", "Type", "Default", "Description"], [35, 20, 20, 115], bold=True)
    pdf.table_row(["search", "string", "-", "Name, specialization, department"], [35, 20, 20, 115])
    pdf.table_row(["page", "int", "1", "Page number"], [35, 20, 20, 115])
    pdf.table_row(["page_size", "int", "50", "Max 100"], [35, 20, 20, 115])
    pdf.sub_title("Response")
    pdf.code_block(
        """{
  "total": 15,
  "page": 1,
  "page_size": 50,
  "doctors": [
    { "id": 12, "name": "Dr. Arora", "specialization": "Cardiology" },
    { "id": 15, "name": "Dr. Mehta", "specialization": "General Medicine" }
  ]
}"""
    )
    pdf.body("UI: searchable dropdown. Send doctor_id in POST - never doctor name as text.")

    # 10. PUT update
    pdf.section_title("10. PUT /nurse/doctor-visits/{id} - Correct Visit")
    pdf.body("Use when nurse picked wrong doctor, time, or notes. Do NOT change patient.")
    pdf.code_block(
        """{
  "doctor_id": 15,
  "visited_at": "2026-08-14T10:30:00+05:30",
  "notes": "Corrected note"
}"""
    )
    pdf.bullet("Allowed: doctor_id, visited_at, notes")
    pdf.bullet("Forbidden: patient_id, recorded_by, recorded_by_name, created_at")
    pdf.bullet("On doctor_id change: doctor_name refreshed; updated_by/updated_by_name/updated_at set")
    pdf.bullet("recorded_by / recorded_by_name / created_at NEVER change")
    pdf.bullet("400 if visit already voided")

    # 11. PUT void
    pdf.section_title("11. PUT /nurse/doctor-visits/{id}/void - Void Visit")
    pdf.body("Use for wrong patient or duplicate log. Soft delete - row kept for audit.")
    pdf.code_block('{ "void_reason": "Logged against wrong patient - meant P-1040" }')
    pdf.bullet("void_reason required (3-500 chars)")
    pdf.bullet("400 if already voided")
    pdf.bullet("After void: row excluded from GET list and visit counts")
    pdf.bullet("Wrong patient flow: void then POST new visit for correct patient")

    # 12. Doctor GET
    pdf.section_title("12. GET /doctor/patient-visits - Doctor Read-Only")
    pdf.body(
        "Doctor views nurse-logged visit history for ONE patient. Read-only - no POST/PUT."
    )
    pdf.sub_title("Query parameters (one patient identifier required)")
    pdf.table_row(["Param", "Type", "Required", "Description"], [35, 20, 20, 115], bold=True)
    pdf.table_row(["patient_id", "int", "One of*", "Internal patient ID"], [35, 20, 20, 115])
    pdf.table_row(["patient_uid", "string", "One of*", "UHID e.g. P-1037"], [35, 20, 20, 115])
    pdf.table_row(["visit_date", "date", "No", "Defaults to today IST"], [35, 20, 20, 115])
    pdf.sub_title("Response")
    pdf.code_block(
        """{
  "patient_id": 1037,
  "patient_uid": "P-1037",
  "patient_name": "Sumit",
  "visit_date": "2026-08-14",
  "visit_count": 2,
  "visits": [
    {
      "id": 1,
      "visit_number": 1,
      "doctor_id": 12,
      "doctor_name": "Dr. Arora",
      "visited_at": "...",
      "notes": "Routine check",
      "recorded_by": 45,
      "recorded_by_name": "Anita Sharma"
    }
  ]
}"""
    )
    pdf.bullet("403 if patient is not doctor's (no IPD admission or OPD appointment link)")
    pdf.bullet("Show visit_count prominently; list visits chronologically")

    # 13. Frontend screens
    pdf.add_page()
    pdf.section_title("13. Suggested Frontend Screens & Routes")
    pdf.table_row(["Screen", "Route", "APIs"], [45, 45, 100], bold=True)
    screens = [
        ("Doctor Visits (nurse)", "/nurse/doctor-visits", "GET list + beds/patients"),
        ("Log Visit modal", "/nurse/doctor-visits (modal)", "POST + GET doctors"),
        ("Edit Visit modal", "same page", "PUT /{id}"),
        ("Void confirm", "same page", "PUT /{id}/void"),
        ("Doctor patient panel", "IPD/patient detail", "GET /doctor/patient-visits"),
    ]
    for s in screens:
        pdf.table_row(list(s), [45, 45, 100])

    pdf.sub_title("Nav suggestion")
    pdf.body(
        "Add 'Doctor Visits' to NurseLayout sidebar (between Medications and Handover). "
        "Wire NursePatientScopeBar allocated_only into GET list queries."
    )

    # 14. Suggested frontend files
    pdf.section_title("14. Suggested Frontend File Structure")
    pdf.code_block(
        """src/features/nurse/
  api/doctorVisits.js          - raw HTTP calls
  pages/NurseDoctorVisitsPage.jsx
  components/NurseLogVisitModal.jsx
  components/NurseEditVisitModal.jsx

src/shared/api/services/nurse.js   - add mapper + service wrappers
src/shared/hooks/queries/useNurseQuery.js  - React Query hooks

src/routes/nurseRoutes.jsx       - add /nurse/doctor-visits route
src/shared/constants/index.js    - ROUTES.NURSE_DOCTOR_VISITS"""
    )

    # 15. Workflows
    pdf.section_title("15. User Workflows")
    pdf.sub_title("WF-01: Log visit")
    pdf.code_block(
        """1. Nurse opens /nurse/doctor-visits
2. GET /nurse/beds/patients + GET /nurse/doctor-visits?visit_date=today
3. Click '+ Log Visit' on patient card
4. GET /nurse/doctor-visits/doctors?search=
5. POST /nurse/doctor-visits { patient_id, doctor_id, notes }
6. Invalidate queries - refresh list + KPIs"""
    )
    pdf.sub_title("WF-02: Fix wrong doctor")
    pdf.code_block("Edit modal - PUT /nurse/doctor-visits/{id} { doctor_id, notes }")
    pdf.sub_title("WF-03: Wrong patient")
    pdf.code_block(
        """Void - PUT /nurse/doctor-visits/{id}/void { void_reason }
Log again - POST for correct patient"""
    )
    pdf.sub_title("WF-04: Doctor views count")
    pdf.code_block(
        """Doctor opens patient detail
GET /doctor/patient-visits?patient_id=1037&visit_date=today
Display visit_count + visit list (read-only)"""
    )

    # 16. TypeScript types
    pdf.section_title("16. TypeScript Interfaces (suggested)")
    pdf.code_block(
        """export interface NurseDoctorVisit {
  id: number;
  patient_id: number;
  patient_uid?: string;
  patient_name?: string;
  doctor_id: number;
  doctor_name: string;
  visited_at: string;
  notes?: string;
  visit_number?: number;
  recorded_by: number;
  recorded_by_name: string;
  created_at: string;
  updated_by?: number;
  updated_by_name?: string;
  updated_at?: string;
  is_voided: boolean;
}

export interface NurseDoctorVisitCreate {
  patient_id?: number;
  appointment_id?: number;
  doctor_id: number;
  visited_at?: string;
  notes?: string;
}

export interface NurseDoctorOption {
  id: number;
  name: string;
  specialization?: string;
}"""
    )

    # 17. Migration note
    pdf.section_title("17. Backend Setup (for devops / local)")
    pdf.code_block(
        """cd HM-System-Backend
alembic upgrade head          # creates nurse_doctor_visits table
python seed.py                # adds permissions to nurse + doctor roles"""
    )
    pdf.body(
        "Migration revision: e6f7a8b9c0d1_create_nurse_doctor_visits.py\n"
        "Aligned with Routers/nurse_doctor_visit_router.py and "
        "Routers/doctor_patient_visit_router.py (August 2026)."
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
