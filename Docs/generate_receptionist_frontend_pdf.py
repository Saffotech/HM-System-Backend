"""Generator: Receptionist Module - Frontend Developer Documentation PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "receptionist-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Receptionist Module Frontend Guide",
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
        for line in text.strip().splitlines():
            self.cell(0, 4.5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table_row(self, cols: list[str], bold: bool = False):
        col_w = (self.w - self.l_margin - self.r_margin) / len(cols)
        self.set_font("Helvetica", "B" if bold else "", 9)
        for col in cols:
            self.cell(col_w, 6, col[:40], border=1)
        self.ln()


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cover
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(0, 11, "Receptionist Module\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: July 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System (FastAPI)  |  Base URL: /receptionist  |  Auth: JWT Bearer",
    )
    pdf.ln(6)

    pdf.section_title("1. Purpose & Scope")
    pdf.body(
        "The Receptionist module manages the live OPD waiting line after OPD Billing has booked "
        "an appointment. Reception checks in arriving patients, monitors doctor queues, answers "
        "doctor 'next patient' requests, and handles no-show / rejoin actions."
    )
    pdf.body(
        "This document is written for frontend developers building the receptionist UI in "
        "HM-frontend-Side. All 11 backend REST endpoints are complete; frontend screens are "
        "not yet implemented."
    )

    pdf.sub_title("What reception DOES")
    pdf.bullet("Show today's scheduled arrivals (not yet checked in)")
    pdf.bullet("Check-in patients into the doctor queue (assigns token number)")
    pdf.bullet("View today's queue across all doctors or per-doctor boards")
    pdf.bullet("Answer doctor 'next patient' requests (call patient to room)")
    pdf.bullet("Mark no-show and rejoin patients")
    pdf.bullet("Queue history reporting and CSV export")

    pdf.sub_title("What reception does NOT do")
    pdf.bullet("Register patients or collect payment (OPD Billing module)")
    pdf.bullet("Create appointments (OPD Billing module)")
    pdf.bullet("Start or complete consultations (Doctor module)")
    pdf.bullet("Record vitals (Nurse module - optional pre-consult step)")

    pdf.section_title("2. End-to-End Workflow")
    pdf.code_block(
        """OPD Billing  ->  POST /opd/appointments  ->  appointment (scheduled)
Patient arrives at hospital
Reception    ->  POST /receptionist/check-in/{appointment_id}
              ->  patient_queue row (status=waiting) + token number
[Optional] Nurse -> POST /nurse/vitals -> queue status vitals_completed
Doctor       ->  PUT /queue/complete/{queue_id}  (finish current patient)
Doctor       ->  POST /queue/request-next  ->  pending call request
Reception    ->  GET /receptionist/pending-calls  (poll every 5-10s)
Reception    ->  POST /receptionist/call-patient/{queue_id}
              ->  status=called, called_at, called_by set
Doctor       ->  PUT /queue/start/{queue_id}  ->  in_progress
Doctor       ->  PUT /queue/complete/{queue_id}  ->  completed
Repeat..."""
    )

    pdf.sub_title("Appointment status flow")
    pdf.code_block(
        """scheduled -> waiting -> in_progress -> completed
              |           |
          check-in    doctor start
waiting -> cancelled  (no-show path)"""
    )

    pdf.sub_title("Queue status flow")
    pdf.code_block(
        """(none) -> waiting -> [vitals_completed] -> called -> in_progress -> completed

waiting | vitals_completed | called  ->  no_show  ->  rejoin  ->  waiting (new token at end)"""
    )

    pdf.sub_title("Key business rules")
    pdf.bullet("Booking an appointment does NOT put the patient in the queue - check-in is separate.")
    pdf.bullet("Reception cannot call a patient unless the doctor first POST /queue/request-next.")
    pdf.bullet("FIFO by token number; urgent/emergency priority sorts first.")
    pdf.bullet("Only one in_progress patient per doctor at a time.")
    pdf.bullet("Duplicate check-in returns HTTP 409.")
    pdf.bullet("All dates/times use IST (Asia/Kolkata). API returns ISO 8601 with timezone.")
    pdf.bullet("No WebSocket - pending calls use HTTP polling (5-10 second interval).")

    pdf.add_page()
    pdf.section_title("3. Authentication & Permissions")

    pdf.sub_title("Auth mechanism")
    pdf.bullet("Header: Authorization: Bearer <JWT>")
    pdf.bullet("401 - invalid or missing token -> redirect to /login")
    pdf.bullet("403 - Permission denied: {permission} required")

    pdf.sub_title("Receptionist role permissions (from seed.py)")
    pdf.bullet("patients:view")
    pdf.bullet("opd:view")
    pdf.bullet("appointments:view")
    pdf.bullet("appointments:update")

    pdf.sub_title("Permission mapping per endpoint")
    pdf.table_row(["Permission", "Endpoints"], bold=True)
    pdf.table_row(["opd:view", "dashboard, today-queue, doctor-queue,"])
    pdf.table_row(["", "pending-calls, queue-history, export"])
    pdf.table_row(["appointments:view", "arrivals"])
    pdf.table_row(["appointments:update", "check-in, call-patient, no-show, rejoin"])

    pdf.body(
        "Frontend role constant: RECEPTIONIST = 'receptionist' (src/shared/constants/index.js). "
        "Route label: 'Reception'. Folder: src/pages/receptionist/ (to be created)."
    )

    pdf.section_title("4. API Endpoints Summary")
    pdf.table_row(["#", "Method", "Path", "Permission"], bold=True)
    endpoints = [
        ("1", "GET", "/receptionist/dashboard", "opd:view"),
        ("2", "GET", "/receptionist/today-queue", "opd:view"),
        ("3", "GET", "/receptionist/arrivals", "appointments:view"),
        ("4", "POST", "/receptionist/check-in/{appointment_id}", "appointments:update"),
        ("5", "GET", "/receptionist/doctor-queue/{doctor_id}", "opd:view"),
        ("6", "GET", "/receptionist/pending-calls", "opd:view"),
        ("7", "POST", "/receptionist/call-patient/{queue_id}", "appointments:update"),
        ("8", "PATCH", "/receptionist/queue/{queue_id}/no-show", "appointments:update"),
        ("9", "PATCH", "/receptionist/queue/{queue_id}/rejoin", "appointments:update"),
        ("10", "GET", "/receptionist/queue-history", "opd:view"),
        ("11", "GET", "/receptionist/queue-history/export", "opd:view"),
    ]
    for num, method, path, perm in endpoints:
        pdf.table_row([num, method, path, perm])

    pdf.ln(2)
    pdf.body("Swagger docs available at /docs under tag 'Receptionist'.")

    pdf.section_title("5. API Details - Read Endpoints")

    pdf.sub_title("GET /receptionist/dashboard")
    pdf.bullet("Query: doctor_id (optional int) - filter stats to one doctor")
    pdf.code_block(
        """Response 200:
{
  "success": true,
  "data": {
    "total_patients": 45,
    "waiting": 10, "called": 2, "in_progress": 3,
    "completed": 30, "no_show": 2,
    "pending_doctor_requests": 2,
    "todays_arrivals": 52, "todays_checked_in": 45,
    "todays_cancelled": 3,
    "average_waiting_time_minutes": 18.5
  }
}
average_waiting_time_minutes is null if no consultations started today."""
    )

    pdf.sub_title("GET /receptionist/today-queue")
    pdf.bullet("All patients checked in today across all doctors.")
    pdf.bullet("Query: doctor_id, doctor_name (partial), patient_id, status, search, page (def 1), limit (def 20, max 100)")
    pdf.bullet("Search matches: patient name, UHID, phone, token, appointment UID, doctor name")
    pdf.bullet("Sort: priority DESC -> called/waiting/vitals_completed first -> token ASC")
    pdf.code_block(
        """Response 200:
{
  "success": true, "queue_date": "2026-06-23",
  "total": 45, "page": 1, "limit": 20,
  "queue": [ { QueueItemOut + doctor_name } ]
}"""
    )

    pdf.sub_title("GET /receptionist/arrivals")
    pdf.bullet("Today's appointments with status=scheduled and NO queue row yet.")
    pdf.bullet("Query: doctor_id, search, page (def 1), limit (def 20, max 100)")
    pdf.bullet("Search matches: patient name, UHID, phone, appointment UID")
    pdf.code_block(
        """Response 200:
{
  "success": true, "total": 45, "page": 1, "limit": 20,
  "arrivals": [{
    "appointment_id": 42, "appointment_uid": "AP-0042",
    "patient_id": 10, "patient_name": "Nilesh Patil",
    "patient_uid": "P-1001", "patient_phone": "9876543210",
    "doctor_id": 5, "doctor_name": "Dr. Sharma",
    "scheduled_at": "2026-06-23T10:30:00+05:30"
  }]
}"""
    )

    pdf.add_page()
    pdf.sub_title("GET /receptionist/doctor-queue/{doctor_id}")
    pdf.bullet("Query: status, search, date (default today IST), page, limit")
    pdf.bullet("If page and limit omitted, returns all rows for that doctor/date")
    pdf.code_block(
        """Response 200:
{
  "success": true, "doctor_id": 5,
  "total": 3, "page": 1, "limit": 3,
  "queue": [ { QueueItemOut } ]
}"""
    )

    pdf.sub_title("GET /receptionist/pending-calls")
    pdf.bullet("Query: doctor_id (optional)")
    pdf.bullet("Poll every 5-10 seconds while screen is open and tab is focused")
    pdf.code_block(
        """Response 200:
{
  "success": true, "total": 1,
  "pending_calls": [{
    "request_id": 3, "doctor_id": 5, "doctor_name": "Dr. Sharma",
    "queue_id": 16, "queue_number": 7,
    "appointment_id": 42, "patient_id": 10,
    "patient_name": "Nilesh Patil", "patient_uid": "P-1001",
    "appointment_time": "10:30:00", "status": "pending",
    "requested_at": "2026-06-23T10:30:00+05:30"
  }]
}"""
    )

    pdf.sub_title("GET /receptionist/queue-history")
    pdf.bullet("Query: date OR date_from/date_to, doctor_id, status, search, page, limit")
    pdf.bullet("Default date range: today only")
    pdf.code_block(
        """Response 200:
{
  "success": true,
  "date_from": "2026-06-01", "date_to": "2026-06-23",
  "total": 120, "page": 1, "limit": 20,
  "history": [ { QueueHistoryItem = QueueItemOut + doctor_name } ]
}"""
    )

    pdf.sub_title("GET /receptionist/queue-history/export")
    pdf.bullet("Same query params as history + format=csv (only csv supported)")
    pdf.bullet("Returns raw CSV file download (Content-Disposition: attachment)")
    pdf.bullet("Columns: Queue Date, Token, Appointment UID, Patient, UHID, Phone,")
    pdf.bullet("  Doctor, Status, Checked In, Called At, Called By (ID/Name),")
    pdf.bullet("  Consultation Started, Consultation Completed")

    pdf.section_title("6. API Details - Write Endpoints")

    pdf.sub_title("POST /receptionist/check-in/{appointment_id}")
    pdf.bullet("Request body: none")
    pdf.bullet("Creates patient_queue row (status=waiting, assigns token_number)")
    pdf.bullet("Sets appointments.status = waiting")
    pdf.bullet("201 on success; 404 if not found; 409 if already checked in today")
    pdf.code_block(
        """Response 201:
{
  "success": true,
  "message": "Patient checked in successfully",
  "queue": { QueueItemOut }
}"""
    )

    pdf.sub_title("POST /receptionist/call-patient/{queue_id}")
    pdf.bullet("Request body: none")
    pdf.bullet("Requires pending doctor request (doctor must POST /queue/request-next first)")
    pdf.bullet("Sets status=called, called_at, called_by; fulfills matching next-request")
    pdf.bullet("400 if no pending request, wrong status, or doctor already has in_progress patient")
    pdf.code_block(
        """Response 200:
{
  "success": true,
  "message": "Patient called to doctor room",
  "queue": {
    "queue_id": 16, "queue_number": 7, "status": "called",
    "called_at": "2026-06-23T10:32:00+05:30",
    "called_by": 12, "called_by_name": "Priya Reception"
  }
}"""
    )

    pdf.sub_title("PATCH /receptionist/queue/{queue_id}/no-show")
    pdf.bullet("Allowed when status is waiting, vitals_completed, or called")
    pdf.bullet("Sets status=no_show; cancels appointment; cancels pending next-request")

    pdf.sub_title("PATCH /receptionist/queue/{queue_id}/rejoin")
    pdf.bullet("Allowed only when status is no_show")
    pdf.bullet("Sets status=waiting; assigns new token at end of line; appointment -> waiting")

    pdf.add_page()
    pdf.section_title("7. Shared Data Types")

    pdf.sub_title("QueueItemOut (used in most queue responses)")
    pdf.code_block(
        """{
  queue_id: number           // DB patient_queue.id
  appointment_id: number
  appointment_uid?: string
  queue_number: number       // token_number in DB
  patient_id: number
  patient_name: string
  patient_uid: string        // UHID
  patient_phone?: string
  doctor_id: number
  status: QueueStatus        // lowercase string
  checked_in_at?: datetime   // queue_entered_at in DB
  called_at?: datetime
  called_by?: number         // receptionist user id
  called_by_name?: string
  consultation_started_at?: datetime
  consultation_completed_at?: datetime
  queue_date?: date
  doctor_name?: string       // today-queue & history only
}"""
    )

    pdf.sub_title("QueueStatus enum values")
    pdf.table_row(["Value", "Meaning", "Badge color suggestion"], bold=True)
    statuses = [
        ("waiting", "Checked in, in waiting area", "Blue"),
        ("vitals_completed", "Nurse recorded vitals", "Teal"),
        ("called", "Reception called to doctor room", "Orange"),
        ("in_progress", "Doctor started consultation", "Purple"),
        ("completed", "Consultation finished", "Green"),
        ("cancelled", "Cancelled", "Gray"),
        ("no_show", "Patient absent", "Red"),
    ]
    for val, meaning, color in statuses:
        pdf.table_row([val, meaning, color])

    pdf.sub_title("AppointmentStatus (appointments table)")
    pdf.body("scheduled | waiting | in_progress | completed | cancelled")

    pdf.sub_title("NextRequestStatus (doctor_queue_next_requests)")
    pdf.body("pending | fulfilled | cancelled")

    pdf.sub_title("QueuePriority")
    pdf.body("normal | urgent | emergency (sorts higher priority first)")

    pdf.section_title("8. Frontend Screens to Build")

    pdf.table_row(["#", "Screen", "Route", "Primary API"], bold=True)
    screens = [
        ("1", "Dashboard", "/receptionist/dashboard", "GET /dashboard"),
        ("2", "Arrivals", "/receptionist/arrivals", "GET /arrivals + POST check-in"),
        ("2b", "Today's Queue", "/receptionist/today", "GET /today-queue"),
        ("3", "Doctor Queues", "/receptionist/queues", "GET /doctor-queue/{id}"),
        ("4", "Pending Calls", "/receptionist/pending-calls", "GET pending + POST call"),
        ("5", "Queue History", "/receptionist/history", "GET history + export"),
    ]
    for row in screens:
        pdf.table_row(list(row))

    pdf.sub_title("Sidebar menu")
    pdf.bullet("Dashboard")
    pdf.bullet("Arrivals")
    pdf.bullet("Today's Queue")
    pdf.bullet("Doctor Queues")
    pdf.bullet("Pending Calls  (badge when pending_doctor_requests > 0)")
    pdf.bullet("Queue History")
    pdf.bullet("Sign out")

    pdf.section_title("9. Screen Specifications")

    pdf.sub_title("Screen 1 - Dashboard (/receptionist/dashboard)")
    pdf.bullet("Stat cards: waiting, called, in_progress, completed, no_show, pending_doctor_requests")
    pdf.bullet("Manager metrics: todays_arrivals, todays_checked_in, todays_cancelled, avg waiting time")
    pdf.bullet("Optional doctor filter (?doctor_id=5)")
    pdf.bullet("Quick action links to Arrivals, Today's Queue, Doctor Queues, Pending Calls")
    pdf.bullet("Optional auto-refresh every 30-60 seconds")

    pdf.sub_title("Screen 2 - Arrivals (/receptionist/arrivals)")
    pdf.bullet("Table: Time, Appointment UID, Patient, UHID, Phone, Doctor, Check-in button")
    pdf.bullet("Filters: search (debounce 400ms), doctor dropdown, pagination (page/limit)")
    pdf.bullet("Doctor dropdown data: GET /opd/departments + GET /opd/doctors/department/{id}")
    pdf.bullet("On check-in: POST /check-in/{appointment_id} -> toast 'Token #N checked in' -> remove row")
    pdf.bullet("Handle 409: 'Patient already checked in today'")
    pdf.bullet("Empty state: 'No arrivals waiting for check-in today'")

    pdf.sub_title("Screen 2b - Today's Queue (/receptionist/today)")
    pdf.bullet("All checked-in patients across all doctors today")
    pdf.bullet("Filters: doctor_id, doctor_name, patient_id, status tabs, search, pagination")
    pdf.bullet("Columns: Token, Appointment UID, Patient, UHID, Doctor, Status, Checked in, Called, Called by")

    pdf.sub_title("Screen 3 - Doctor Queues (/receptionist/queues)")
    pdf.bullet("Requires doctor selection before loading")
    pdf.bullet("Filters: status tabs, search, date picker (default today)")
    pdf.bullet("Row actions: No-show (waiting/called/vitals_completed), Rejoin (no_show only)")
    pdf.bullet("Do NOT add 'Call patient' here - use Pending Calls screen")
    pdf.bullet("Empty: 'Select a doctor' or 'No patients in queue for Dr. {name} today'")

    pdf.sub_title("Screen 4 - Pending Calls (/receptionist/pending-calls)")
    pdf.bullet("Poll GET /pending-calls every 5-10 seconds (tab focused)")
    pdf.bullet("Card per request: doctor, patient, UHID, token, requested_at, Call patient button")
    pdf.bullet("On call: POST /call-patient/{queue_id} -> status becomes 'called'")
    pdf.bullet("Sidebar badge when total > 0; optional sound on new request_id")
    pdf.bullet("Empty: 'No doctors waiting for patient call'")

    pdf.sub_title("Screen 5 - Queue History (/receptionist/history)")
    pdf.bullet("Date range filters, doctor, status, search, pagination")
    pdf.bullet("Export button: GET /queue-history/export?format=csv with same filters")
    pdf.bullet("For today live data, use Today's Queue or Doctor Queues instead")

    pdf.add_page()
    pdf.section_title("10. Global UI Conventions")

    pdf.table_row(["Pattern", "Rule"], bold=True)
    conventions = [
        ("Auth", "Redirect to /login on 401"),
        ("Permissions", "Hide module if role != receptionist"),
        ("Search debounce", "400ms"),
        ("Default page size", "20 (max 100)"),
        ("Pending calls poll", "5-10s while tab focused"),
        ("Dashboard refresh", "Optional 30-60s"),
        ("Date/time display", "IST; API returns ISO 8601 with timezone"),
        ("Error toasts", "Show API detail message"),
        ("Status badges", "Consistent colors across all screens"),
    ]
    for pattern, rule in conventions:
        pdf.table_row([pattern, rule])

    pdf.sub_title("Filters, search & pagination summary")
    pdf.table_row(["Screen", "Search", "Filters", "Pagination", "Polling"], bold=True)
    filter_summary = [
        ("Dashboard", "No", "Doctor", "No", "Optional"),
        ("Arrivals", "Yes", "Doctor", "Yes", "No"),
        ("Today's Queue", "Yes", "Doctor, status", "Yes", "Manual"),
        ("Doctor Queues", "Optional", "Doctor, status, date", "Optional", "Manual"),
        ("Pending Calls", "No", "Doctor", "No", "Yes 5-10s"),
        ("Queue History", "Yes", "Date, doctor, status", "Yes", "Export CSV"),
    ]
    for row in filter_summary:
        pdf.table_row(list(row))

    pdf.section_title("11. TypeScript Types (src/types/receptionist.ts)")

    pdf.code_block(
        """export type PaginatedMeta = { total: number; page: number; limit: number }

export type ReceptionistDashboard = {
  total_patients: number; waiting: number; called: number
  in_progress: number; completed: number; no_show: number
  pending_doctor_requests: number; todays_arrivals: number
  todays_checked_in: number; todays_cancelled: number
  average_waiting_time_minutes: number | null
}

export type Arrival = {
  appointment_id: number; appointment_uid: string
  patient_id: number; patient_name: string; patient_uid: string
  patient_phone?: string; doctor_id: number; doctor_name: string
  scheduled_at: string
}

export type QueueItem = {
  queue_id: number; appointment_id: number; appointment_uid?: string
  queue_number: number; patient_id: number; patient_name: string
  patient_uid: string; patient_phone?: string; doctor_id: number
  status: string; checked_in_at?: string; called_at?: string | null
  called_by?: number | null; called_by_name?: string | null
  consultation_started_at?: string | null
  consultation_completed_at?: string | null; doctor_name?: string
}

export type PendingCall = {
  request_id: number; doctor_id: number; doctor_name: string
  queue_id: number; queue_number: number; patient_name: string
  patient_uid: string; requested_at: string
}"""
    )

    pdf.section_title("12. API Client (src/api/receptionist.ts)")

    pdf.code_block(
        """getDashboard(params?: { doctor_id?: number })
getTodayQueue(params?: {
  doctor_id?: number; doctor_name?: string; patient_id?: number
  status?: string; search?: string; page?: number; limit?: number
})
getArrivals(params: { doctor_id?: number; search?: string; page?: number; limit?: number })
checkIn(appointmentId: number)
getDoctorQueue(doctorId: number, params?: { status?: string; search?: string; date?: string })
getPendingCalls(params?: { doctor_id?: number })
callPatient(queueId: number)
markNoShow(queueId: number)
rejoinQueue(queueId: number)
getQueueHistory(params: {
  date?: string; date_from?: string; date_to?: string
  doctor_id?: number; status?: string; search?: string
  page?: number; limit?: number
})
exportQueueHistory(params: { ...same filters...; format?: 'csv' })"""
    )

    pdf.section_title("13. Suggested File Structure")

    pdf.code_block(
        """pages/receptionist/
  ReceptionistRoutes.tsx
  Dashboard.tsx
  Arrivals.tsx
  TodayQueue.tsx
  DoctorQueues.tsx
  PendingCalls.tsx
  QueueHistory.tsx
  hooks/
    useReceptionistArrivals.ts
    useDoctorQueue.ts
    usePendingCallsPoll.ts
  components/
    QueueTable.tsx
    ArrivalTable.tsx
    ArrivalFilters.tsx
    DoctorQueueFilters.tsx
    PendingCallCard.tsx
    QueueStatusBadge.tsx
    PaginationBar.tsx"""
    )

    pdf.add_page()
    pdf.section_title("14. Error Handling")

    pdf.table_row(["HTTP", "When", "Frontend action"], bold=True)
    errors = [
        ("400", "Invalid queue state, no pending request", "Toast with detail"),
        ("401", "Invalid/missing token", "Redirect to /login"),
        ("403", "Missing permission", "Toast: contact admin"),
        ("404", "Appointment/queue not found", "Toast with detail"),
        ("409", "Duplicate check-in", "Toast: already checked in"),
    ]
    for http, when, action in errors:
        pdf.table_row([http, when, action])

    pdf.sub_title("Common API detail messages")
    pdf.bullet("Patient already checked in for this appointment today")
    pdf.bullet("Patient already has a queue entry with this doctor today")
    pdf.bullet("No pending doctor request for this patient...")
    pdf.bullet("No-show is only allowed for patients waiting or called...")
    pdf.bullet("Only no-show patients can rejoin the queue")

    pdf.section_title("15. Integration with Other Modules")

    pdf.sub_title("OPD Billing (/opd) - upstream")
    pdf.bullet("POST /opd/appointments - creates scheduled appointments (before check-in)")
    pdf.bullet("POST /opd/patient/register - patient registration (not reception)")
    pdf.bullet("GET /opd/departments - department dropdown")
    pdf.bullet("GET /opd/doctors/department/{department_id} - doctor dropdown")
    pdf.bullet("DO NOT USE: GET /opd/visits/today or GET /opd/queue/today (billing visits, not clinical queue)")

    pdf.sub_title("Doctor module (/queue) - downstream partner")
    pdf.bullet("POST /queue/request-next - doctor signals ready; creates pending call")
    pdf.bullet("PUT /queue/start/{queue_id} - called -> in_progress")
    pdf.bullet("PUT /queue/complete/{queue_id} - finishes consultation")
    pdf.bullet("GET /queue/current - doctor's active patient")

    pdf.sub_title("Nurse module - optional")
    pdf.bullet("POST /nurse/vitals - updates queue waiting -> vitals_completed")

    pdf.sub_title("Deprecated endpoints - do NOT use in new frontend")
    pdf.table_row(["Old endpoint", "Use instead"], bold=True)
    deprecated = [
        ("POST /queue/add", "POST /receptionist/check-in/{appointment_id}"),
        ("GET /opd/queue/next-requests", "GET /receptionist/pending-calls"),
        ("POST /opd/queue/send-in", "POST /receptionist/call-patient/{queue_id}"),
    ]
    for old, new in deprecated:
        pdf.table_row([old, new])

    pdf.section_title("16. Call Patient vs Start Consultation")

    pdf.table_row(["Action", "Actor", "Sets", "Meaning"], bold=True)
    call_flow = [
        ("Call patient", "Reception", "called, called_at, called_by", "Patient sent to room"),
        ("Start consultation", "Doctor", "in_progress, consultation_started_at", "Clinical encounter begins"),
        ("Complete", "Doctor", "completed, consultation_completed_at", "Visit finished"),
    ]
    for row in call_flow:
        pdf.table_row(list(row))

    pdf.section_title("17. Recommended Build Order")

    pdf.table_row(["Phase", "Screens", "Why"], bold=True)
    build_order = [
        ("P1", "Arrivals + Check-in", "Core workflow entry point"),
        ("P2", "Doctor Queues + Pending Calls", "Live queue + polling"),
        ("P3", "Dashboard", "Summary after core flows work"),
        ("P4", "Queue History", "Reporting"),
        ("P5", "Polish", "Badges, sounds, empty states"),
    ]
    for phase, screens, why in build_order:
        pdf.table_row([phase, screens, why])

    pdf.section_title("18. Backend Source Files (Reference)")

    pdf.bullet("Routers/receptionist_router.py - 11 HTTP endpoints")
    pdf.bullet("Services/receptionist_service.py - business logic orchestration")
    pdf.bullet("Schemas/receptionist_schema.py - Pydantic request/response models")
    pdf.bullet("Models/doctor_patient_queue.py - PatientQueue, QueueStatus, QueuePriority")
    pdf.bullet("Models/doctor_queue_next_request.py - DoctorQueueNextRequest")
    pdf.bullet("Models/opd_billing.py - Appointment, AppointmentStatus")
    pdf.bullet("main.py - app.include_router(receptionist_router)")

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        5,
        "Related markdown docs: HM-System/Docs/frontend/roles/receptionist.md, "
        "HM-System/Docs/flows/receptionist-module.md, "
        "HM-System/Docs/frontend/API-REFERENCE.md (Section 4).",
    )

    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
