"""Generator: Doctor Patient Vitals + Nursing Notes - Frontend Developer Guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "doctor-vitals-notes-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Doctor Vitals & Nursing Notes Frontend Guide",
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
    pdf.multi_cell(0, 11, "Doctor Patient Vitals &\nNursing Notes\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: 24 August 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System-Backend (FastAPI)  |  Auth: JWT Bearer token\n"
        "Doctor prefix: /doctor/patients/{patient_id}  |  Read-only (view only)",
    )
    pdf.ln(3)

    pdf.callout(
        "BACKEND IS DONE - FRONTEND IS NOT WIRED",
        "Doctors can already view nurse-recorded vitals and nursing notes for "
        "their assigned patients. Wire this into the doctor EMR (PatientHistoryProfile), "
        "the same way Doctor Visits was added. Do NOT call nurse APIs. "
        "Do NOT add create / edit / delete actions for the doctor.",
    )

    pdf.section_title("1. Purpose")
    pdf.body(
        "A doctor must be able to read the vitals and nursing notes that nurses "
        "recorded for a patient assigned to that doctor (OPD appointment or IPD "
        "admission). This is a clinical read of nurse data, not the doctor's own "
        "consultation notes / prescriptions."
    )
    pdf.bullet("VIEW vitals timeline for one assigned patient: YES")
    pdf.bullet("VIEW nursing notes timeline for one assigned patient: YES")
    pdf.bullet("CREATE / UPDATE / DELETE vitals or notes: NO")
    pdf.bullet("Hospital-wide vitals registry (like nurse /nurse/vitals): NO")
    pdf.bullet("No new database tables. Reuses patient_vitals + nursing_notes")
    pdf.bullet("No Alembic migration. Permissions already in seed.py")

    pdf.section_title("2. Critical: do not reuse Nurse APIs")
    pdf.table_row(["Wrong (nurse / other)", "Correct (doctor)"], [95, 95], bold=True)
    pdf.table_row(
        ["GET /nurse/vitals", "GET /doctor/patients/{patient_id}/vitals"],
        [95, 95],
    )
    pdf.table_row(
        ["GET /nurse/vitals/search?patient_id=", "GET /doctor/patients/{patient_id}/vitals"],
        [95, 95],
    )
    pdf.table_row(
        ["GET /nurse/notes", "GET /doctor/patients/{patient_id}/notes"],
        [95, 95],
    )
    pdf.table_row(
        ["POST /nurse/vitals  (record)", "Not allowed for doctor"],
        [95, 95],
    )
    pdf.ln(1)
    pdf.body(
        "Nurse endpoints require nurse_vitals:view / nurse_notes:view and filter by "
        "occupied / allocated beds. A doctor JWT will 403. Do not import nurse.js, "
        "useNurseQuery, or nurse mapper hooks."
    )

    pdf.section_title("3. Two different 'notes' - do not mix them")
    pdf.table_row(["Source", "What it is", "Where it lives today"], [38, 72, 80], bold=True)
    pdf.table_row(
        [
            "Doctor clinical notes",
            "Symptoms / diagnosis / follow-up the doctor writes in consultation",
            "ConsultationModal + appointment PATCH + prescriptions",
        ],
        [38, 72, 80],
    )
    pdf.table_row(
        [
            "Nursing notes (THIS API)",
            "Nurse observations: symptoms, treatment_response, additional_notes",
            "GET /doctor/patients/{id}/notes  -- not wired yet",
        ],
        [38, 72, 80],
    )
    pdf.ln(1)
    pdf.body(
        "Do not dump nursing notes into ConsultationModal. Add a separate "
        "'Nursing Notes' panel on the patient profile, next to Prescriptions / "
        "Labs / Doctor Visits."
    )

    pdf.section_title("4. Permissions (two view keys)")
    pdf.table_row(["Permission", "Role", "Used for"], [50, 28, 112], bold=True)
    pdf.table_row(
        ["doctor_vitals:view", "doctor", "GET /doctor/patients/{id}/vitals"],
        [50, 28, 112],
    )
    pdf.table_row(
        ["doctor_notes:view", "doctor", "GET /doctor/patients/{id}/notes"],
        [50, 28, 112],
    )
    pdf.ln(1)
    pdf.body(
        "All requests require: Authorization: Bearer <access_token>\n"
        "401 = token missing/expired. 403 = permission missing OR patient not assigned.\n"
        "There is NO doctor_vitals:create / doctor_notes:update."
    )
    pdf.bullet("Add keys to useDoctorPermission.js (vitalsView, notesView)")
    pdf.bullet("Add keys to seedPermissions.js")
    pdf.bullet("Add a view-only group in doctorManagementConfig.js (Nurse clinical read)")
    pdf.bullet("Add keys to adminEditLocks.js doctor_clinical")
    pdf.bullet("Hide each panel when the matching permission is false")

    pdf.section_title("5. API endpoints (2 total)")
    pdf.table_row(["#", "Method", "URL", "Purpose"], [8, 18, 95, 69], bold=True)
    for row in [
        ("1", "GET", "/doctor/patients/{patient_id}/vitals", "Paginated vitals for one patient"),
        ("2", "GET", "/doctor/patients/{patient_id}/notes", "Paginated nursing notes for one patient"),
    ]:
        pdf.table_row(list(row), [8, 18, 95, 69])
    pdf.ln(1)
    pdf.body("No POST / PUT / PATCH / DELETE under these paths. No list-all-patients endpoint.")

    pdf.add_page()
    pdf.section_title("6. patient_id is the NUMERIC id, not UHID")
    pdf.callout(
        "EASIEST BUG TO SHIP",
        "Path param patient_id is the internal integer (e.g. 1037), NOT the "
        "display UHID (P-1037). GET /patients/{uhid} uses UHID. These two APIs "
        "do not. If you pass P-1037 you get 422.",
    )
    pdf.table_row(["Value", "Example", "Use here?"], [50, 50, 90], bold=True)
    pdf.table_row(["Internal patient_id", "1037", "YES - path param"], [50, 50, 90])
    pdf.table_row(["UHID / patient_uid", "P-1037", "NO - display only"], [50, 50, 90])
    pdf.table_row(["appointment_id", "88", "NO - not in this URL"], [50, 50, 90])
    pdf.ln(1)
    pdf.body(
        "On PatientHistoryProfile the numeric id is already resolved:\n"
        "  const patientId = resolvedPatientId ?? historyData?.patientId ?? null;\n"
        "That is the same patientId used for prescriptions and Doctor Visits. "
        "Enable the vitals/notes queries only when Number.isFinite(patientId)."
    )
    pdf.bullet("From EMR list row: row.patientId (mapped from patient_id)")
    pdf.bullet("From today's appointment: appt.patientDbId")
    pdf.bullet("From visitRowToPatientSummary: patient.patientId")
    pdf.bullet("If patientId is null, show empty copy. Do not call the API with UHID.")

    pdf.section_title("7. Assigned-patient scope (backend enforces)")
    pdf.body(
        "The logged-in doctor is 'assigned' to a patient if ANY of these is true:"
    )
    pdf.bullet("An OPD appointment exists with Appointment.doctor_id = current user id")
    pdf.bullet("An IPD admission exists with IpdAdmission.doctor_id = current user id")
    pdf.body(
        "Status is not filtered (past / cancelled / discharged still count). "
        "There is no allocated_only / shift / ward filter. The doctor sees the "
        "full vitals and notes history for that patient, newest first."
    )
    pdf.callout(
        "403 IS NOT ALWAYS A MISSING PERMISSION",
        "If the JWT has doctor_vitals:view but the patient was never this doctor's "
        "OPD or IPD patient, the API returns 403 detail: "
        "'Patient is not assigned to this doctor'. Hide the panel for missing "
        "permission. For assignment 403, show: 'This patient is not assigned to you.' "
        "Do not treat it as an empty list.",
    )

    pdf.section_title("8. Shared query parameters (both endpoints)")
    pdf.table_row(["Param", "Type", "Default", "Description"], [32, 22, 28, 108], bold=True)
    for row in [
        ("patient_id", "int path", "required", "Internal id, ge=1"),
        ("page", "int", "1", "Page number, ge=1"),
        ("page_size", "int", "20", "Max 100"),
        ("from_date", "date", "-", "YYYY-MM-DD inclusive start"),
        ("to_date", "date", "-", "YYYY-MM-DD inclusive end"),
    ]:
        pdf.table_row(list(row), [32, 22, 28, 108])
    pdf.ln(1)
    pdf.body(
        "Date filter field: vitals use recorded_at. Notes use created_at. "
        "to_date is inclusive (backend uses < to_date + 1 day). "
        "No search, allocated_only, shift_name, or patient_uid query params."
    )
    pdf.sub_title("Example requests")
    pdf.code_block(
        "GET /doctor/patients/1037/vitals?page=1&page_size=20\n"
        "Authorization: Bearer <doctor_token>\n"
        "\n"
        "GET /doctor/patients/1037/notes?from_date=2026-08-01&to_date=2026-08-24\n"
        "Authorization: Bearer <doctor_token>"
    )

    pdf.add_page()
    pdf.section_title("9. GET /doctor/patients/{patient_id}/vitals")
    pdf.sub_title("Success response (200)")
    pdf.code_block(
        """{
  "success": true,
  "total": 2,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 51,
      "appointment_id": 88,
      "patient_id": 1037,
      "patient_uid": "P-1037",
      "patient_name": "Sumit Sharma",
      "bed_number": "G-12",
      "ward_name": "General",
      "doctor_id": 9,
      "doctor_name": "Dr. Arora",
      "recorded_by": 22,
      "recorded_by_name": "Nurse Priya",
      "temperature": 37.4,
      "blood_pressure": "120/80",
      "heart_rate": 78,
      "respiratory_rate": 18,
      "oxygen_saturation": 98,
      "blood_sugar": 110.0,
      "weight": 68.5,
      "pain_level": 2,
      "observation_notes": "Stable, afebrile",
      "status": "recorded",
      "recorded_at": "2026-08-24T08:15:00+05:30",
      "updated_at": "2026-08-24T08:15:00+05:30",
      "history": [
        {
          "history_id": 51,
          "recorded_at": "2026-08-24T08:15:00+05:30",
          "recorded_by": "Nurse Priya",
          "status": "recorded",
          "temperature": 37.4,
          "blood_pressure": "120/80",
          "heart_rate": 78,
          "respiratory_rate": 18,
          "oxygen_saturation": 98,
          "blood_sugar": 110.0,
          "weight": 68.5,
          "pain_level": 2,
          "observation_notes": "Stable, afebrile"
        }
      ]
    }
  ]
}"""
    )

    pdf.sub_title("Vitals fields to display")
    pdf.table_row(["API field", "UI label", "Notes"], [48, 42, 100], bold=True)
    for row in [
        ("recorded_at", "Recorded at", "ISO datetime IST. Sort is newest first"),
        ("recorded_by_name", "Recorded by", "Nurse display name"),
        ("temperature", "Temp", "Number; show unit C in the label"),
        ("blood_pressure", "BP", "String e.g. 120/80"),
        ("heart_rate", "HR", "bpm"),
        ("respiratory_rate", "RR", "breaths/min"),
        ("oxygen_saturation", "SpO2", "percent"),
        ("blood_sugar", "Blood sugar", "Number; may be null"),
        ("weight", "Weight", "kg; may be null"),
        ("pain_level", "Pain", "0-10; may be null"),
        ("observation_notes", "Observation", "Free text; may be null"),
        ("status", "Status", "recorded | reviewed"),
        ("ward_name / bed_number", "Ward / Bed", "From occupied bed; may be null for OPD"),
        ("patient_uid", "Patient ID", "Display UHID, never numeric patient_id"),
    ]:
        pdf.table_row(list(row), [48, 42, 100])
    pdf.ln(1)
    pdf.body(
        "Any vital field may be null. Show an em dash. Do not invent 0. "
        "appointment_id may be null for IPD-only recordings."
    )

    pdf.sub_title("history[] on each item")
    pdf.body(
        "Because the serializer reuses the nurse helper, EVERY item includes "
        "history: the full newest-first list of all recordings for that patient "
        "(not paginated). Do NOT render history inside every table row."
    )
    pdf.bullet("Table / timeline = items[] (respects page, page_size, from_date, to_date)")
    pdf.bullet("Optional date picker of all timestamps = items[0].history only")
    pdf.bullet("If total is large, prefer pagination on items[] and ignore history")

    pdf.add_page()
    pdf.section_title("10. GET /doctor/patients/{patient_id}/notes")
    pdf.sub_title("Success response (200)")
    pdf.code_block(
        """{
  "success": true,
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 19,
      "appointment_id": 88,
      "patient_id": 1037,
      "patient_uid": "P-1037",
      "patient_name": "Sumit Sharma",
      "bed_number": "G-12",
      "ward_name": "General",
      "doctor_id": 9,
      "doctor_name": "Dr. Arora",
      "nurse_id": 22,
      "nurse_name": "Nurse Priya",
      "created_by_name": "Nurse Priya",
      "symptoms": "Mild headache, afebrile",
      "treatment_response": "Paracetamol given, pain reduced",
      "additional_notes": "Encourage fluids",
      "status": "active",
      "created_at": "2026-08-24T08:40:00+05:30",
      "updated_at": "2026-08-24T08:40:00+05:30",
      "history": [
        {
          "history_id": 19,
          "created_at": "2026-08-24T08:40:00+05:30",
          "created_by": "Nurse Priya",
          "status": "active",
          "symptoms": "Mild headache, afebrile",
          "treatment_response": "Paracetamol given, pain reduced",
          "additional_notes": "Encourage fluids"
        }
      ]
    }
  ]
}"""
    )

    pdf.sub_title("Nursing note fields to display")
    pdf.table_row(["API field", "UI label", "Notes"], [48, 42, 100], bold=True)
    for row in [
        ("created_at", "Created at", "ISO datetime IST. Newest first"),
        ("nurse_name", "Nurse", "Fallback created_by_name"),
        ("symptoms", "Symptoms", "Nurse observation, not doctor diagnosis"),
        ("treatment_response", "Treatment response", "May be null"),
        ("additional_notes", "Additional notes", "May be null"),
        ("status", "Status", "active | archived"),
        ("ward_name / bed_number", "Ward / Bed", "May be null for OPD"),
        ("patient_uid", "Patient ID", "Display UHID"),
    ]:
        pdf.table_row(list(row), [48, 42, 100])
    pdf.ln(1)
    pdf.body(
        "Same history[] rule as vitals: use items[] for the list. "
        "Do not show Edit / Archive buttons. Doctor is read-only."
    )

    pdf.section_title("11. Errors")
    pdf.table_row(["Status", "When", "UI action"], [18, 92, 80], bold=True)
    for row in [
        ("401", "Missing/expired JWT", "Redirect to login"),
        ("403", "Missing doctor_vitals:view or doctor_notes:view", "Hide that panel / nav"),
        ("403", "Patient not assigned to this doctor", "Message: not assigned. Do not leak why"),
        ("422", "patient_id not an integer >= 1 (e.g. passed UHID)", "Do not call; fix the id source"),
        ("200 + empty items", "Assigned patient, nurse has recorded nothing yet", "Empty state, not an error"),
    ]:
        pdf.table_row(list(row), [18, 92, 80])

    pdf.section_title("12. Suggested UI (mirror Doctor Visits)")
    pdf.body(
        "Do not add a new top-level sidebar item unless product asks. "
        "Doctor workflow is: open a patient from Patients EMR / queue / IPD, "
        "then read vitals and notes on that profile."
    )
    pdf.table_row(["Screen", "Where", "APIs"], [48, 62, 80], bold=True)
    for row in [
        ("Vitals panel", "PatientHistoryProfile", "GET .../{id}/vitals"),
        ("Nursing notes panel", "PatientHistoryProfile", "GET .../{id}/notes"),
        ("Optional latest vitals", "IPD patient table row", "Same vitals API page_size=1"),
    ]:
        pdf.table_row(list(row), [48, 62, 80])
    pdf.ln(1)
    pdf.sub_title("Copy DoctorPatientVisitsPanel.jsx")
    pdf.bullet("New components: DoctorPatientVitalsPanel.jsx + DoctorPatientNotesPanel.jsx")
    pdf.bullet("Pass patientId (numeric). Hide if permission is false (return null)")
    pdf.bullet("Show on OPD AND IPD profile (visits panel is IPD-only; these are both)")
    pdf.bullet("Place after Prescriptions / Labs, before or after Doctor Visits")
    pdf.bullet("Date range optional: from_date + to_date as YYYY-MM-DD")
    pdf.bullet("Pagination: page + page_size; use total from the payload")
    pdf.bullet("Empty copy: 'No vitals recorded for this patient.' / 'No nursing notes...'")
    pdf.bullet("Loading / error copy: same tone as Doctor Visits panel")
    pdf.bullet("No Record / Edit / Delete buttons")

    pdf.sub_title("Suggested vitals table columns")
    pdf.bullet("Recorded at | Temp | BP | HR | RR | SpO2 | Pain | Recorded by")
    pdf.bullet("Expand row or modal for observation_notes, weight, blood sugar, ward/bed")

    pdf.sub_title("Suggested notes table columns")
    pdf.bullet("Created at | Symptoms | Treatment response | Nurse")
    pdf.bullet("Expand row for additional_notes")

    pdf.add_page()
    pdf.section_title("13. Frontend files to add or change")
    pdf.body("Touch doctor + shared doctor API only. Do not modify nurse feature files.")
    pdf.code_block(
        """ADD
src/features/doctor/api/patientClinical.js
  getDoctorPatientVitals(patientId, params, token)
  getDoctorPatientNotes(patientId, params, token)

src/features/doctor/components/DoctorPatientVitalsPanel.jsx
src/features/doctor/components/DoctorPatientNotesPanel.jsx

CHANGE
src/shared/api/services/doctorPatients.js
  fetchDoctorPatientVitals(patientId, token, params)
  fetchDoctorPatientNotes(patientId, token, params)

src/features/doctor/hooks/useDoctorPatientQuery.js
  useDoctorPatientVitalsQuery(patientId, filters)
  useDoctorPatientNotesQuery(patientId, filters)
  enabled: canView && Number.isFinite(Number(patientId))

src/shared/api/queryKeys.js
  doctor.patients.vitals(patientId, filters)
  doctor.patients.notes(patientId, filters)

src/shared/api/mappers/doctorPatientMapper.js
  mapDoctorVitalItem(row)   // keep snake_case or camelCase consistently
  mapDoctorNoteItem(row)
  // Do NOT import nurseMapper.js

src/features/doctor/hooks/useDoctorPermission.js
  vitalsView: 'doctor_vitals:view'
  notesView: 'doctor_notes:view'

src/features/doctor/components/PatientHistoryProfile.jsx
  Render both panels with patientId={patientId}
  Show for OPD and IPD (not IPD-only)

src/features/admin/doctor/constants/doctorManagementConfig.js
src/features/admin/constants/adminEditLocks.js  (doctor_clinical)
src/features/super-admin/constants/seedPermissions.js
  doctor_vitals:view
  doctor_notes:view

DO NOT CHANGE
src/features/nurse/**  (nurse record/edit vitals and notes stay nurse-only)
src/features/doctor/api/clinical.js  (that file is doctor consultation records)
src/features/doctor/components/ConsultationModal.jsx"""
    )

    pdf.section_title("14. Suggested service wrappers")
    pdf.code_block(
        """// src/features/doctor/api/patientClinical.js
import { apiClient } from '@/shared/api/client';

function appendQuery(path, params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

export function getDoctorPatientVitals(patientId, params, token) {
  return apiClient(
    appendQuery(`/doctor/patients/${patientId}/vitals`, params),
    { token }
  );
}

export function getDoctorPatientNotes(patientId, params, token) {
  return apiClient(
    appendQuery(`/doctor/patients/${patientId}/notes`, params),
    { token }
  );
}"""
    )
    pdf.body("Hook example (same pattern as useDoctorPatientPrescriptionsQuery):")
    pdf.code_block(
        """useDoctorPatientVitalsQuery(patientId, {
  page: 1,
  page_size: 20,
  from_date,   // optional 'YYYY-MM-DD'
  to_date,     // optional 'YYYY-MM-DD'
})
// enabled only when doctor_vitals:view AND numeric patientId"""
    )

    pdf.section_title("15. Display rules")
    pdf.bullet("Patient ID column / header chip = patient_uid (P-1037).")
    pdf.bullet("Numeric patient_id is for the URL only. Never show it in the table.")
    pdf.bullet("Null numbers and empty strings: em dash. Do not coerce to 0.")
    pdf.bullet("Ward / Bed empty for OPD is normal.")
    pdf.bullet("Read-only: no forms, no status change, no nurse-style Edit.")
    pdf.bullet("Format recorded_at / created_at with the same datetime helper as Doctor Visits.")
    pdf.bullet("Do not map nursing symptoms onto visit.diagnosis.")

    pdf.section_title("16. What backend already does (do not reimplement)")
    pdf.bullet("Assignment check (OPD appointment OR IPD admission for this doctor)")
    pdf.bullet("403 when the patient is not assigned")
    pdf.bullet("Pagination total / page / page_size / items")
    pdf.bullet("Inclusive from_date / to_date")
    pdf.bullet("Newest-first order")
    pdf.bullet("Nurse display name, UHID, ward/bed snapshot when occupied")
    pdf.bullet("Audit: doctor.patient_vitals.view and doctor.patient_notes.view")

    pdf.section_title("17. Backend setup (local / devops)")
    pdf.code_block(
        """cd HM-System-Backend
python seed.py
# Ensures doctor_vitals:view and doctor_notes:view exist on the doctor role.
# No alembic migration for this feature."""
    )
    pdf.body(
        "Until seed.py is run on an old database, doctor calls return 403.\n"
        "Aligned with Routers/doctor_patient_clinical_router.py and "
        "Services/doctor_patient_clinical_service.py (24 August 2026)."
    )

    pdf.section_title("18. QA checklist for frontend")
    pdf.bullet("Doctor without doctor_vitals:view: vitals panel hidden")
    pdf.bullet("Doctor without doctor_notes:view: notes panel hidden")
    pdf.bullet("Assigned OPD patient: both lists load (ward/bed may be empty)")
    pdf.bullet("Assigned IPD patient: both lists load; ward/bed shown if occupied")
    pdf.bullet("Patient assigned to another doctor: 403 handled, not an empty table")
    pdf.bullet("UHID is never sent as the path param")
    pdf.bullet("Date range filters the list")
    pdf.bullet("Pagination uses total from the payload")
    pdf.bullet("Empty assigned patient shows empty copy, not an error toast")
    pdf.bullet("No Record / Edit / Delete UI on doctor screens")
    pdf.bullet("Nurse module still uses /nurse/vitals and /nurse/notes unchanged")
    pdf.bullet("ConsultationModal still saves doctor clinical notes, not nursing notes")

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
