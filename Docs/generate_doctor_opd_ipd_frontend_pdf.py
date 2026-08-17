"""Generator: Doctor module OPD/IPD frontend guide (matches shipped backend)."""
from pathlib import Path

from fpdf import FPDF

OUT = (
    Path(__file__).resolve().parent
    / "frontend-doctor-opd-ipd-dashboard-changes.pdf"
)


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Doctor Module: OPD / IPD Frontend Guide",
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
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, f"  - {text}")

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_text_color(20, 20, 20)
        self.set_fill_color(245, 245, 245)
        usable = self.w - self.l_margin - self.r_margin
        for line in text.strip("\n").splitlines():
            self.set_x(self.l_margin)
            self.multi_cell(usable, 4.5, "  " + line, fill=True)
        self.ln(2)

    def warn(self, text: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 60, 20)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, f"IMPORTANT: {text}")
        self.ln(1)

    def table_row(self, cols: list[str], bold: bool = False):
        col_w = (self.w - self.l_margin - self.r_margin) / len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        x0 = self.get_x()
        y0 = self.get_y()
        heights = []
        for i, col in enumerate(cols):
            self.set_xy(x0 + i * col_w, y0)
            self.multi_cell(col_w, 5, col, border=1)
            heights.append(self.get_y() - y0)
        self.set_xy(x0, y0 + max(heights))


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(
        0,
        9,
        "Doctor Module\nOPD / IPD Tabs + Patient History\nFrontend Implementation Guide",
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Audience: Doctor frontend developers  |  Scope: Doctor UI only  |  "
        "Date: August 2026  |  Backend for this work is already shipped",
    )
    pdf.ln(2)

    # ------------------------------------------------------------------
    pdf.section_title("1. Purpose")
    pdf.body(
        "This document tells frontend what to build after the doctor-module backend "
        "update. Doctors must see OPD and IPD separately, with filters and pagination "
        "on IPD, and discharged IPD patients in patient history."
    )
    pdf.warn(
        "Do not use GET /ipd/admissions for the doctor screen. That IPD-desk API "
        "requires ipd:patients:list, which the doctor role does not have. "
        "Use GET /doctor/ipd-admissions (appointments:view)."
    )
    pdf.warn(
        "Do not drive the IPD tab from GET /appointments/today. That list has no "
        "IPD pagination, no IPD date filter, and no discharged list. Today-list IPD "
        "rows also send status=scheduled, which is wrong for Admit/Discharge UI."
    )

    # ------------------------------------------------------------------
    pdf.section_title("2. What Product UI Must Look Like")
    pdf.sub_title("Doctor Dashboard")
    pdf.bullet("Add two buttons / tabs: OPD | IPD.")
    pdf.bullet(
        "OPD tab: today's OPD appointments only (existing Consult / Cancel / "
        "Pending-payment behaviour)."
    )
    pdf.bullet(
        "IPD tab: this doctor's admissions. Columns: Patient name, Patient ID (UHID), "
        "Date (admit date), Status (Admit / Discharge)."
    )
    pdf.bullet(
        "IPD filters: search (name / UHID / phone / admission no), date range, "
        "status Admit or Discharge. Pagination: page + page_size."
    )
    pdf.bullet("IPD sort is done by backend (newest admission first). Do not re-sort oldest first.")
    pdf.bullet(
        "Admit list stays until discharge. After discharge the row leaves Admit "
        "and appears under Discharge and in Patients history."
    )

    pdf.sub_title("Patients / EMR history")
    pdf.bullet(
        "Same search, date (filter_date / month / year), and page / page_size as today."
    )
    pdf.bullet(
        "List now mixes completed OPD visits + discharged IPD stays (default)."
    )
    pdf.bullet("Show an OPD / IPD badge per row using encounter_type.")
    pdf.bullet("Do not open Consult using an IPD row id.")

    # ------------------------------------------------------------------
    pdf.section_title("3. Which API For Which Screen")
    pdf.table_row(["Screen", "Call this API", "Do not use"], bold=True)
    pdf.table_row(
        [
            "Dashboard OPD tab",
            "GET /appointments/today (existing)",
            "IPD desk /ipd/*",
        ]
    )
    pdf.table_row(
        [
            "Dashboard IPD tab",
            "GET /doctor/ipd-admissions",
            "GET /appointments/today",
        ]
    )
    pdf.table_row(
        [
            "Patients list / EMR",
            "GET /patients (+ encounter_type)",
            "GET /ipd/admissions",
        ]
    )
    pdf.table_row(
        [
            "One patient history",
            "GET /patients/{patient_uid}",
            "Appointment id APIs for IPD",
        ]
    )
    pdf.ln(3)
    pdf.body(
        "Auth: same doctor JWT. IPD list permission = appointments:view. "
        "History permission = patients:view. Do not send doctor_id; backend uses the token."
    )

    # ------------------------------------------------------------------
    pdf.section_title("4. NEW API  -  GET /doctor/ipd-admissions")
    pdf.body(
        "This is the IPD tab API. Logged-in doctor only. Newest admitted_at first. "
        "Default status is admitted (Admit list)."
    )
    pdf.sub_title("4.1 Query params")
    pdf.table_row(["Param", "Default", "Notes"], bold=True)
    pdf.table_row(["status", "admitted", "admitted | discharged | cancelled | all"])
    pdf.table_row(["", "", "Aliases: admit, discharge"])
    pdf.table_row(["from_date", "none", "YYYY-MM-DD, filters admitted_at"])
    pdf.table_row(["to_date", "none", "YYYY-MM-DD, filters admitted_at"])
    pdf.table_row(["search", "none", "name, UHID, phone, admission_no"])
    pdf.table_row(["page", "1", "1-based"])
    pdf.table_row(["page_size", "20", "max 100"])
    pdf.ln(2)
    pdf.body("Examples:")
    pdf.code_block(
        """GET /doctor/ipd-admissions?status=admitted&page=1&page_size=20
GET /doctor/ipd-admissions?status=admit&page=1
GET /doctor/ipd-admissions?status=discharged&from_date=2026-08-01&to_date=2026-08-17
GET /doctor/ipd-admissions?search=amresh&status=admitted&page=2&page_size=20"""
    )

    pdf.sub_title("4.2 Response")
    pdf.code_block(
        """{
  "success": true,
  "total": 41,
  "page": 1,
  "page_size": 20,
  "items": [ { ...IPD row... } ]
}"""
    )

    pdf.sub_title("4.3 IPD row fields (map these)")
    pdf.code_block(
        """{
  "id": "IPD-1005",
  "appointment_uid": "IPD-1005",
  "patient_id": 205,
  "patient_uid": "P-1205",
  "patient_name": "Amresh",
  "patient_phone": "98xxxxxxxx",
  "patient_age": "32y",
  "patient_gender": "Male",
  "registration_source": "IPD",
  "encounter_type": "IPD",
  "appointment_type": "ipd",
  "admission_id": 5,
  "bed_number": "B-12",
  "ward_name": "General",
  "status": "admitted",
  "scheduled_at": "<admitted_at ISO>",
  "appointment_date": "2026-08-17",
  "appointment_time": "10:15:00",
  "admitted_at": "2026-08-17T10:15:00+05:30",
  "discharged_at": null,
  "diagnosis": "...",
  "notes": "...",
  "doctor_id": 12,
  "department_id": 3
}"""
    )
    pdf.bullet("id and appointment_uid are STRINGS (admission_no). Not a numeric appointment PK.")
    pdf.bullet("admission_id is the numeric IPD admission PK if you need it later.")
    pdf.bullet("status is real: admitted | discharged | cancelled. Display Admit / Discharge.")
    pdf.bullet("Date column: admitted_at (or appointment_date). After discharge, discharged_at is set.")
    pdf.bullet(
        "If IPD admit left Doctor empty, doctor_id is null and the row never appears here."
    )

    pdf.sub_title("4.4 Status mapping for UI")
    pdf.table_row(["API status", "IPD tab label", "Query to send"], bold=True)
    pdf.table_row(["admitted", "Admit", "status=admitted (or admit)"])
    pdf.table_row(["discharged", "Discharge", "status=discharged (or discharge)"])
    pdf.table_row(["cancelled", "Cancelled", "status=cancelled (optional)"])
    pdf.ln(3)
    pdf.body(
        "Extend apiStatusToUiStatus: admitted -> Admit, discharged -> Discharge. "
        "Do not map admitted to Scheduled on the IPD tab."
    )

    # ------------------------------------------------------------------
    pdf.section_title("5. Dashboard OPD Tab  -  GET /appointments/today")
    pdf.body(
        "Keep using this for the OPD tab only. Permission: appointments:view. "
        "Top-level shape is unchanged."
    )
    pdf.code_block(
        """{
  "success": true,
  "message": "Today's appointments fetched successfully",
  "appointment": <count>,
  "appointments": [ ... ]
}"""
    )
    pdf.bullet("OPD rows: encounter_type=OPD, numeric id, normal appointment status.")
    pdf.bullet(
        "Backend may still append admitted IPD rows on this list (bonus / badge). "
        "Those IPD rows use status=scheduled on purpose so old Scheduled filter "
        "does not drop them. That is NOT the IPD tab contract."
    )
    pdf.bullet(
        "OPD tab should show only encounter_type === 'OPD' (or appointment_type !== 'ipd')."
    )
    pdf.bullet(
        "Keep the existing unpaid-OPD Pending filter on the OPD tab. "
        "Never run that filter on IPD tab rows."
    )
    pdf.bullet(
        "If the same patient has OPD today + IPD admit, today-list skips the IPD duplicate. "
        "The IPD tab still shows them via /doctor/ipd-admissions."
    )

    pdf.sub_title("5.1 OPD row vs leftover today-list IPD row")
    pdf.code_block(
        """OPD (use on OPD tab):
  id: 42                    // numeric appointment PK
  encounter_type: "OPD"
  status: "scheduled" | "completed" | "cancelled"
  admission_id: null

Today-list IPD leftover (ignore on IPD tab):
  id: "IPD-1005"            // STRING
  encounter_type: "IPD"
  status: "scheduled"       // dashboard-only, not Admit
  admission_id: 5"""
    )

    # ------------------------------------------------------------------
    pdf.section_title("6. Patients History  -  GET /patients")
    pdf.body(
        "Same filters and pagination as before, plus encounter_type. "
        "Default encounter_type=all mixes completed OPD + discharged IPD."
    )
    pdf.sub_title("6.1 Query params (unchanged + one new)")
    pdf.table_row(["Param", "Used for", "Notes"], bold=True)
    pdf.table_row(["search", "name / UHID / phone", "same as OPD history"])
    pdf.table_row(["filter_date", "one day", "OPD: scheduled_at; IPD: admitted_at"])
    pdf.table_row(["month + year", "calendar filter", "month is 1-12"])
    pdf.table_row(["year", "year only", "same as today"])
    pdf.table_row(["page / page_size", "pagination", "default 20, max 100"])
    pdf.table_row(["encounter_type", "NEW", "opd | ipd | all (default all)"])
    pdf.ln(2)
    pdf.code_block(
        """GET /patients?page=1&page_size=20
GET /patients?encounter_type=all&search=amresh&page=1
GET /patients?encounter_type=opd&filter_date=2026-08-17
GET /patients?encounter_type=ipd&month=8&year=2026
GET /patients/P-1205?encounter_type=all&page=1&page_size=20"""
    )
    pdf.body(
        "If a screen must stay OPD-only (old behaviour), send encounter_type=opd. "
        "Patients EMR should send all (or omit it) so discharged IPD appears."
    )

    pdf.sub_title("6.2 History row")
    pdf.bullet("OPD: id is numeric appointment PK, status=completed, encounter_type=OPD.")
    pdf.bullet(
        "IPD: id is STRING admission_no, status=discharged, encounter_type=IPD, "
        "admission_id set, admitted_at / discharged_at set."
    )
    pdf.bullet("department_id may be null on IPD. Treat it as optional.")
    pdf.bullet(
        "appointmentDbId / Consult must use numeric appointment id only. "
        "If encounter_type is IPD, appointmentDbId must be null."
    )

    pdf.sub_title("6.3 Current frontend gap")
    pdf.bullet(
        "features/doctor/api/patients.js does not send encounter_type yet. Add it."
    )
    pdf.bullet(
        "getPatientHistory() currently has no query string. Pass page, page_size, "
        "encounter_type when opening one patient."
    )
    pdf.bullet(
        "doctorPatientMapper.apiToUiPatientVisitRow uses api.id as appointmentDbId. "
        "That will treat IPD-1005 as an appointment id. Guard it."
    )

    # ------------------------------------------------------------------
    pdf.section_title("7. registration_source vs encounter_type")
    pdf.bullet(
        "registration_source (OPD | IPD): which desk first created the UHID. Permanent."
    )
    pdf.bullet(
        "encounter_type (OPD | IPD): this row's visit type. Use this for badges."
    )
    pdf.body(
        "Example: UHID created in OPD, later admitted to this doctor. "
        "registration_source stays OPD. IPD tab / history IPD row has encounter_type IPD."
    )

    # ------------------------------------------------------------------
    pdf.section_title("8. Frontend Work  -  What To Change")
    pdf.warn(
        "IPD tab will stay empty until you call GET /doctor/ipd-admissions and skip "
        "the OPD Pending payment filter on those rows."
    )

    pdf.sub_title("8.1 MUST  -  New IPD API client + query")
    pdf.bullet("NEW file: src/features/doctor/api/ipd.js")
    pdf.code_block(
        """// GET /doctor/ipd-admissions
export async function getDoctorIpdAdmissions(token, params = {}) {
  const qs = new URLSearchParams();
  if (params.page != null) qs.set('page', String(params.page));
  if (params.page_size != null) qs.set('page_size', String(params.page_size));
  if (params.status) qs.set('status', params.status);
  if (params.from_date) qs.set('from_date', params.from_date);
  if (params.to_date) qs.set('to_date', params.to_date);
  if (params.search?.trim()) qs.set('search', params.search.trim());
  const q = qs.toString();
  return apiClient(q ? `/doctor/ipd-admissions?${q}` : '/doctor/ipd-admissions', { token });
}"""
    )
    pdf.bullet("NEW hook: src/features/doctor/hooks/useDoctorIpdQuery.js")
    pdf.bullet(
        "queryKeys.js: add doctor.ipd.admissions(filters) e.g. "
        "['doctor', 'ipd', 'admissions', filters]"
    )
    pdf.bullet("Do not reuse queryKeys.ipd.* (those are the IPD desk module).")
    pdf.bullet("Invalidate doctor IPD keys after discharge if the doctor UI can refresh it.")

    pdf.sub_title("8.2 MUST  -  Dashboard OPD | IPD tabs")
    pdf.body("Files: DashboardSection.jsx, DashboardAppointmentsTable.jsx, DashboardFilterBar.jsx")
    pdf.bullet("Add OPD | IPD toggle. Default OPD so current OPD flow stays.")
    pdf.bullet("OPD: keep useDoctorDashboardTodayAppointmentsQuery. Filter out IPD rows.")
    pdf.bullet(
        "IPD: new query. Table columns Patient ID, Patient Name, Date, Status. "
        "No Consult / Cancel columns (or disable them)."
    )
    pdf.bullet(
        "IPD status filter: Admit (status=admitted) vs Discharge (status=discharged). "
        "Do not reuse Scheduled / Completed / Cancelled OPD chips for IPD."
    )
    pdf.bullet("IPD search + date: send search / from_date / to_date to the API (not client-only).")
    pdf.bullet("IPD pagination: use response.total, page, page_size. Do not slice locally.")
    pdf.bullet("Optional: show ward_name / bed_number under the name.")

    pdf.sub_title("8.3 MUST  -  Do not treat IPD as unpaid OPD")
    pdf.body(
        "Files: features/doctor/utils/doctorAppointmentPayment.js "
        "(enrichDoctorAppointmentsWithOpdPayment) and appointmentMapper.js"
    )
    pdf.body(
        "Today OPD tab still drops unpaid scheduled OPD (displayStatus Pending). "
        "If an IPD row is ever mapped through that helper, it has no OPD bill and is dropped."
    )
    pdf.code_block(
        """const isIpd =
  appt.encounterType === 'IPD' ||
  appt.encounter_type === 'IPD' ||
  appt.type === 'ipd';

if (isIpd) {
  // keep the row; do not set Pending; do not filter out
}"""
    )
    pdf.bullet("IPD tab must never call enrichDoctorAppointmentsWithOpdPayment.")

    pdf.sub_title("8.4 MUST  -  Map new fields")
    pdf.body("File: shared/api/mappers/appointmentMapper.js (apiToUiAppointment)")
    pdf.bullet("encounterType from encounter_type (default OPD).")
    pdf.bullet("registrationSource from registration_source.")
    pdf.bullet("admissionId, bedNumber, wardName, admittedAt, dischargedAt.")
    pdf.bullet("Keep string id => dbId null for IPD (resolveAppointmentIds).")
    pdf.bullet("Status map: admitted -> Admit, discharged -> Discharge.")

    pdf.body("File: shared/api/mappers/doctorPatientMapper.js")
    pdf.bullet("Map encounterType, registrationSource, admissionId, admittedAt, dischargedAt.")
    pdf.bullet(
        "appointmentDbId: only if encounter_type is OPD and id is numeric. "
        "Never Number('IPD-1005')."
    )
    pdf.bullet("Status: keep discharged as Discharge, not Completed.")

    pdf.sub_title("8.5 MUST  -  Guard Consult / Cancel / GET appointment by id")
    pdf.body(
        "Files: AppointmentRowActions.jsx, DashboardSection.jsx, "
        "features/doctor/api/appointments.js"
    )
    pdf.bullet("If encounterType === IPD or dbId == null: hide/disable Consult and Cancel.")
    pdf.bullet("Never call GET /appointments/{id} or PUT /appointments/{id}/status with IPD-1005.")
    pdf.bullet("Patient profile by patientUid / patientDbId still works without appointment id.")

    pdf.sub_title("8.6 MUST  -  Patients EMR / history")
    pdf.body(
        "Files: features/doctor/api/patients.js, hooks/useDoctorPatientQuery.js, "
        "PatientsEMRSection.jsx, PatientHistoryProfile.jsx, patientDateFilters.js"
    )
    pdf.bullet("Pass encounter_type=all on the EMR list (or omit; backend default is all).")
    pdf.bullet("Keep sending search, filter_date, month, year, page, page_size as today.")
    pdf.bullet("Optional OPD/IPD filter in EMR: pass encounter_type=opd|ipd|all.")
    pdf.bullet("Show Type badge from encounterType. Date from scheduled_at / admitted_at.")
    pdf.bullet("Opening a history IPD row must not start an OPD consultation.")

    # ------------------------------------------------------------------
    pdf.section_title("9. Frontend Files Checklist")
    pdf.sub_title("Create")
    pdf.bullet("src/features/doctor/api/ipd.js")
    pdf.bullet("src/features/doctor/hooks/useDoctorIpdQuery.js")
    pdf.bullet("Optional: src/features/doctor/components/DoctorIpdPatientsTable.jsx")

    pdf.sub_title("Must change")
    pdf.bullet("src/shared/api/queryKeys.js")
    pdf.bullet("src/shared/api/mappers/appointmentMapper.js")
    pdf.bullet("src/shared/api/mappers/doctorPatientMapper.js")
    pdf.bullet("src/features/doctor/utils/doctorAppointmentPayment.js")
    pdf.bullet("src/features/doctor/components/DashboardSection.jsx")
    pdf.bullet("src/features/doctor/components/DashboardAppointmentsTable.jsx")
    pdf.bullet("src/features/doctor/components/DashboardFilterBar.jsx")
    pdf.bullet("src/features/doctor/components/AppointmentRowActions.jsx")
    pdf.bullet("src/features/doctor/api/patients.js")
    pdf.bullet("src/features/doctor/hooks/useDoctorPatientQuery.js")
    pdf.bullet("src/features/doctor/components/PatientsEMRSection.jsx")
    pdf.bullet("src/features/doctor/components/PatientHistoryProfile.jsx")

    pdf.sub_title("Should change")
    pdf.bullet("src/features/doctor/utils/doctorDashboardSelectors.js")
    pdf.bullet("src/features/doctor/utils/patientDateFilters.js")
    pdf.bullet("src/features/doctor/utils/patientListFilters.js")
    pdf.bullet("src/features/doctor/components/StatusPill.jsx (Admit / Discharge colours)")
    pdf.bullet("src/shared/api/services/doctorAppointments.js (skip IPD in OPD today map if mixed)")
    pdf.bullet("src/shared/api/services/doctorPatients.js")

    pdf.sub_title("Do not change for this")
    pdf.bullet("IPD desk frontend (features/ipd/*) and GET /ipd/admissions.")
    pdf.bullet("Nurse, lab, pharmacy, receptionist.")
    pdf.bullet("OPD consult / queue / prescribe flows for real OPD appointments.")

    # ------------------------------------------------------------------
    pdf.section_title("10. Suggested Frontend Data Flow")
    pdf.code_block(
        """Dashboard
  [OPD] -> GET /appointments/today
         -> map appointments
         -> drop encounter_type IPD
         -> existing OPD payment Pending filter
         -> Consult / Cancel allowed if dbId is number

  [IPD] -> GET /doctor/ipd-admissions?status=&from_date=&to_date=&search=&page=
         -> map items (do NOT run OPD payment filter)
         -> table: name | UHID | date | Admit/Discharge
         -> paginate from total / page / page_size
         -> no Consult / Cancel

Patients EMR
  GET /patients?search=&filter_date=&month=&year=&page=&encounter_type=all
  GET /patients/{uid}?encounter_type=all&page=
         -> badge OPD / IPD from encounter_type
         -> IPD rows are discharged stays only"""
    )

    # ------------------------------------------------------------------
    pdf.section_title("11. Doctor notification on IPD admit (backend live)")
    pdf.body(
        "When IPD desk admits a patient with Doctor selected, that doctor gets an "
        "in-app inbox row on the existing GET /doctor/notifications API. "
        "Unread count includes it. No new notification endpoint."
    )
    pdf.bullet("Type: IPD_ADMITTED  |  source_module: IPD  |  priority: HIGH")
    pdf.bullet("reference_type: ADMISSION  |  reference_id: numeric admission_id")
    pdf.bullet("Title: IPD Patient Admitted")
    pdf.bullet("Also sent if an already-admitted stay is later assigned/reassigned to this doctor.")
    pdf.bullet("Not sent if Doctor is empty on admit. Not sent on discharge.")
    pdf.body("Existing doctor inbox already renders unknown types with the Bell fallback, so the row appears without a frontend code change. Optional later: add an IPD_ADMITTED filter chip and deep-link the click to the IPD tab.")
    pdf.code_block(
        """{
  "notification_type": "IPD_ADMITTED",
  "source_module": "IPD",
  "reference_type": "ADMISSION",
  "reference_id": 5,
  "priority": "HIGH",
  "title": "IPD Patient Admitted",
  "message": "IPD patient admitted under you.\\nPatient: Amresh (P-1205)\\nAdmission: IPD-1005\\nWard: General  Bed: B-12"
}"""
    )

    # ------------------------------------------------------------------
    pdf.section_title("12. How An IPD Patient Reaches The Doctor")
    pdf.code_block(
        """IPD Register (UHID)     -> registration_source = IPD
        |
IPD Admit (bed + doctor) -> ipd_admissions.doctor_id = that doctor
        |                    status = admitted
        v
GET /doctor/ipd-admissions?status=admitted
GET /doctor/notifications (IPD_ADMITTED)
        |                    -> IPD tab Admit list (until discharge)
        |                    -> doctor inbox bell / unread count
        v
IPD Discharge            -> status = discharged
        |
GET /doctor/ipd-admissions?status=discharged
GET /patients (encounter_type=all or ipd)
        |                    -> Discharge list + Patients history"""
    )
    pdf.bullet("Doctor on IPD admit is optional. Empty doctor => row never appears for anyone, and no notification.")
    pdf.bullet("User must open the dashboard of the SAME doctor selected at admit.")

    # ------------------------------------------------------------------
    pdf.section_title("13. QA Checklist")
    pdf.bullet("OPD tab: paid today patients still show; unpaid OPD still hidden.")
    pdf.bullet("OPD tab: Consult / Cancel still work on numeric appointment ids.")
    pdf.bullet("IPD tab Admit: Amresh admitted to Dr X appears on Dr X, newest first.")
    pdf.bullet("IPD tab still shows Amresh the next day if still admitted (not today-only).")
    pdf.bullet("IPD search by name / UHID hits the API and paginates (total matches pages).")
    pdf.bullet("IPD date from/to filters by admit date.")
    pdf.bullet("After discharge: leaves Admit, appears under Discharge + Patients history.")
    pdf.bullet("History search / month / year / page still work; IPD rows have Type IPD.")
    pdf.bullet("IPD row never calls /appointments/{id} (422/404 would mean a frontend bug).")
    pdf.bullet("IPD admit with no doctor: does not appear (expected).")
    pdf.bullet("Doctor JWT only; 403 if a non-doctor calls the IPD doctor API.")
    pdf.bullet(
        "IPD admit with Doctor = Dr X: Dr X GET /doctor/notifications shows IPD Patient Admitted; unread-count +1."
    )
    pdf.bullet("IPD admit with no doctor: no notification for any doctor.")
    pdf.bullet("Later assign Doctor on the admission: that doctor then gets IPD_ADMITTED.")

    # ------------------------------------------------------------------
    pdf.section_title("14. Out of Scope")
    pdf.bullet("Lab technician module.")
    pdf.bullet("Nurse module.")
    pdf.bullet("IPD consult / prescribe / lab order from an IPD encounter (no API yet).")
    pdf.bullet("Changing IPD desk admit/discharge screens.")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        5,
        "End of document. Build IPD tab on GET /doctor/ipd-admissions first, "
        "then map history encounter_type so discharged IPD shows in Patients EMR.",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
