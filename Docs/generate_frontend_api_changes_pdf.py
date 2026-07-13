"""Generator: Frontend guide for REC / NURSE / DOC bugfix API changes."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "frontend-api-changes-rec-nurse-doc.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Frontend API Changes (Receptionist / Nurse / Doctor)",
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
            self.cell(self.epw, 4.5, "  " + safe[:105], new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table_row(self, cols: list[str], bold: bool = False, widths: list[float] | None = None):
        if widths is None:
            widths = [self.epw / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        for i, col in enumerate(cols):
            self.cell(widths[i], 6, col[:48], border=1)
        self.ln()


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cover
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 11, "Frontend API Change Guide")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Receptionist / Nurse / Doctor Bug Fixes")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body(
        "Date: 13 July 2026  |  Audience: Frontend developers  |  "
        "Purpose: Exact UI/API changes after backend fixes REC-1, REC-2, REC-3, NURSE-1, DOC-1."
    )
    pdf.body(
        "This document tells you WHAT changed, WHICH endpoints to call, request/response shapes, "
        "and WHAT to stop doing in the UI."
    )

    # Overview
    pdf.section_title("1. Change Overview")
    w = [pdf.epw * 0.16, pdf.epw * 0.22, pdf.epw * 0.62]
    pdf.table_row(["Ticket", "Module", "Frontend impact"], bold=True, widths=w)
    pdf.table_row(["REC-1", "Receptionist", "Dashboard counts are now accurate"], widths=w)
    pdf.table_row(
        ["REC-2", "Receptionist", "Queue has no duplicate patients; pagination fixed"],
        widths=w,
    )
    pdf.table_row(
        ["REC-3", "Receptionist", "Queue returns scheduled_at - show time, not dash"],
        widths=w,
    )
    pdf.table_row(
        ["NURSE-1", "Nurse", "IPD vitals/notes via patient_id (no OPD appointment)"],
        widths=w,
    )
    pdf.table_row(
        ["DOC-1", "Doctor", "One Save API completes consult + optional Rx atomically"],
        widths=w,
    )
    pdf.ln(2)
    pdf.callout(
        "Auth note",
        "All endpoints still require Bearer JWT. Permissions unchanged unless noted.",
    )

    # REC
    pdf.section_title("2. Receptionist Module")
    pdf.sub_title("2.1 REC-1 - Dashboard counts")
    pdf.body("Endpoint (unchanged): GET /receptionist/dashboard")
    pdf.body("Optional query: doctor_id")
    pdf.body(
        "Backend now counts DISTINCT appointments. Do not invent client-side totals from "
        "joined/queue lists. Trust data.total_patients, data.completed, "
        "data.todays_paid_appointments, data.todays_unpaid_appointments, data.todays_cancelled."
    )
    pdf.code_block(
        """
{
  "success": true,
  "data": {
    "total_patients": 47,
    "completed": 12,
    "todays_paid_appointments": 30,
    "todays_unpaid_appointments": 17,
    "todays_cancelled": 2
  }
}
"""
    )
    pdf.bullet("UI: bind dashboard cards directly to these fields.")
    pdf.bullet("UI: expected Scheduled/Total card uses total_patients (now correct).")

    pdf.sub_title("2.2 REC-2 - Queue duplicates and pagination")
    pdf.body("Endpoints (unchanged paths):")
    pdf.bullet("GET /receptionist/today-queue")
    pdf.bullet("GET /receptionist/doctor-queue/{doctor_id}")
    pdf.bullet("GET /receptionist/queue-history")
    pdf.body(
        "Backend guarantees one queue row per selected appointment. On same-day boards "
        "(today-queue / doctor-queue), if the same patient has multiple appointments, "
        "backend keeps ONE canonical appointment using this priority:"
    )
    pdf.bullet("1. Paid appointment")
    pdf.bullet("2. Linked visit exists")
    pdf.bullet("3. Latest scheduled_at")
    pdf.bullet("4. Highest appointment id")
    pdf.body(
        "total / page / limit now match unique rows after dedupe. Use server pagination; "
        "do not re-count duplicates on the client."
    )
    pdf.callout(
        "Frontend action",
        "Remove any client-side unique-by-patient hacks. Rely on API total for pager labels "
        "(e.g. Showing 1-20 of {total}).",
    )

    pdf.sub_title("2.3 REC-3 - scheduled_at on queue items")
    pdf.body(
        "Every queue item now includes scheduled_at (ISO datetime with timezone). "
        "Previously UI showed '-' because the field was missing."
    )
    pdf.code_block(
        """
{
  "appointment_id": 42,
  "appointment_uid": "AP-0042",
  "patient_id": 10,
  "patient_name": "Nilesh Patil",
  "patient_uid": "P-1001",
  "patient_phone": "98XXXXXXXX",
  "doctor_id": 5,
  "doctor_name": "Dr. Sharma",
  "status": "scheduled",
  "payment_status": "paid",
  "scheduled_at": "2026-07-13T13:00:00+05:30",
  "checked_in_at": null,
  "called_at": null,
  "consultation_started_at": null,
  "consultation_completed_at": null,
  "queue_date": "2026-07-13"
}
"""
    )
    pdf.bullet("Display: format scheduled_at in Asia/Kolkata, e.g. 1:00 PM.")
    pdf.bullet("Fallback only if scheduled_at is null (should be rare).")
    pdf.bullet("Applies to today-queue, doctor-queue, and queue-history rows.")

    pdf.sub_title("2.4 Receptionist TypeScript types (suggested)")
    pdf.code_block(
        """
type ReceptionistQueueItem = {
  appointment_id: number;
  appointment_uid?: string | null;
  patient_id: number;
  patient_name: string;
  patient_uid: string;
  patient_phone?: string | null;
  doctor_id: number;
  doctor_name?: string | null;
  status: "scheduled" | "completed";
  payment_status?: string | null;
  scheduled_at?: string | null; // NEW - ISO string
  checked_in_at?: string | null;
  called_at?: string | null;
  consultation_started_at?: string | null;
  consultation_completed_at?: string | null;
  queue_date?: string | null;
};
"""
    )

    # Nurse
    pdf.add_page()
    pdf.section_title("3. Nurse Module (NURSE-1)")
    pdf.sub_title("3.1 Problem solved")
    pdf.body(
        "IPD patients on occupied beds often have no OPD appointment. Vitals and nursing notes "
        "no longer require appointment_id only."
    )

    pdf.sub_title("3.2 Create vitals")
    pdf.body("Endpoint: POST /nurse/vitals")
    pdf.body("Send EITHER appointment_id (OPD) OR patient_id (IPD occupied bed).")
    pdf.code_block(
        """
// OPD (existing)
POST /nurse/vitals
{ "appointment_id": 42, "temperature": 98.6, "heart_rate": 78 }

// IPD (NEW)
POST /nurse/vitals
{ "patient_id": 10, "temperature": 98.6, "heart_rate": 78, "mark_critical": false }
"""
    )
    pdf.body("Rules:")
    pdf.bullet("At least one of appointment_id or patient_id is required.")
    pdf.bullet("patient_id alone is allowed only if patient currently occupies a bed.")
    pdf.bullet("If both are sent, patient_id must match the appointment patient.")
    pdf.bullet("Response appointment_id may be null for pure IPD records.")

    pdf.sub_title("3.3 Create nursing notes")
    pdf.body("Endpoint: POST /nurse/notes")
    pdf.code_block(
        """
// OPD
{ "appointment_id": 42, "symptoms": "...", "additional_notes": "..." }

// IPD (NEW)
{ "patient_id": 10, "symptoms": "...", "treatment_response": "...", "additional_notes": "..." }
"""
    )

    pdf.sub_title("3.4 Response shape changes")
    pdf.code_block(
        """
{
  "id": 101,
  "appointment_id": null,   // can be null for IPD
  "patient_id": 10,
  "patient_uid": "P-1001",
  "patient_name": "Nilesh Patil",
  "bed_number": "B-12",
  "recorded_by": 8,
  "temperature": 98.6,
  "heart_rate": 78,
  "status": "recorded",
  "recorded_at": "2026-07-13T14:10:00+05:30"
}
"""
    )
    pdf.callout(
        "Frontend action - IPD screens",
        "On bed/IPD patient detail, call create vitals/notes with patient_id from the bed "
        "record. Do not block the form waiting for an OPD appointment_id.",
    )
    pdf.callout(
        "Frontend action - OPD screens",
        "Keep using appointment_id as before. No breaking change if you already send it.",
    )
    pdf.body("Errors to handle in UI:")
    pdf.bullet("400: Provide appointment_id or patient_id")
    pdf.bullet("400: patient_id only allowed for occupied-bed patients")
    pdf.bullet("400: Vitals already recorded for this appointment / today for IPD")
    pdf.bullet("404: Appointment not found / Patient not found")

    pdf.sub_title("3.5 Suggested TypeScript")
    pdf.code_block(
        """
type VitalCreatePayload = {
  appointment_id?: number;
  patient_id?: number;
  temperature?: number;
  blood_pressure?: string;
  heart_rate?: number;
  respiratory_rate?: number;
  oxygen_saturation?: number;
  blood_sugar?: number;
  weight?: number;
  pain_level?: number;
  observation_notes?: string;
  mark_critical?: boolean;
};

type VitalResponse = {
  id: number;
  appointment_id?: number | null;
  patient_id: number;
  patient_uid?: string | null;
  patient_name?: string | null;
  bed_number?: string | null;
  recorded_by: number;
  // ...vital fields
  status?: string | null;
  recorded_at: string;
};
"""
    )

    # Doctor
    pdf.add_page()
    pdf.section_title("4. Doctor Module (DOC-1)")
    pdf.sub_title("4.1 Problem solved")
    pdf.body(
        "Doctors no longer need a multi-step UI flow Scheduled -> Waiting -> In Progress -> "
        "Completed with separate prescription create. Partial failures left inconsistent data. "
        "Use ONE atomic save."
    )

    pdf.sub_title("4.2 Preferred endpoint")
    pdf.body("POST /consultations/save")
    pdf.body("Also available: PUT /queue/complete (same SaveConsultationRequest body).")
    pdf.body(
        "In one DB transaction the backend: ensures queue row, saves clinical fields "
        "(symptoms/diagnosis/notes/follow_up_date), optionally creates prescription + items, "
        "marks appointment completed, marks queue completed."
    )

    pdf.sub_title("4.3 Request body")
    pdf.code_block(
        """
POST /consultations/save
{
  "appointment_id": 42,
  "clinical": {
    "symptoms": "Fever, cough",
    "diagnosis": "Viral fever",
    "notes": "Advise rest and fluids",
    "follow_up_date": "2026-07-20"
  },
  "prescription": {
    "diagnosis": "Viral fever",
    "notes": "After food",
    "items": [
      {
        "medicine_name": "Paracetamol",
        "dosage": "500mg",
        "frequency": "TDS",
        "duration": 3,
        "instructions": "After food"
      }
    ]
  }
}
"""
    )
    pdf.bullet("prescription is OPTIONAL. Omit it if only clinical completion is needed.")
    pdf.bullet("If prescription is sent, diagnosis and non-empty items are required.")
    pdf.bullet("clinical fields are all optional individually, but send what the form collected.")

    pdf.sub_title("4.4 Success response")
    pdf.code_block(
        """
{
  "success": true,
  "message": "Consultation saved",
  "appointment": { "id": 42, "status": "completed", "...": "..." },
  "queue": { "id": 16, "status": "completed", "appointment_id": 42, "token_number": 7 },
  "prescription": {
    "id": 55,
    "appointment_id": 42,
    "patient_id": 10,
    "diagnosis": "Viral fever",
    "status": "pending",
    "items": [ { "medicine_name": "Paracetamol", "...": "..." } ]
  }
}
"""
    )
    pdf.body("prescription in response is null when not provided in the request.")

    pdf.sub_title("4.5 What frontend should STOP doing")
    pdf.bullet("Do NOT manually patch appointment status scheduled -> waiting -> in_progress -> completed.")
    pdf.bullet("Do NOT call create-prescription only after a separate complete call (race/partial failure).")
    pdf.bullet("Do NOT keep local multi-step wizards that require intermediate status success.")
    pdf.body(
        "Recommended UX: one Save / Complete Consultation button that posts clinical + Rx together."
    )

    pdf.sub_title("4.6 Optional still-valid endpoints")
    pdf.bullet("GET /consultations/appointment/{id} - read-only context (appointment, queue, past Rx, labs).")
    pdf.bullet("PATCH /consultations/appointment/{id} - clinical complete without creating prescription.")
    pdf.bullet("Legacy queue start/complete-by-queue-id may exist; prefer POST /consultations/save for finish.")

    pdf.sub_title("4.7 Errors to handle")
    pdf.bullet("404 Appointment not found")
    pdf.bullet("400 Consultation already completed")
    pdf.bullet("400 Cannot save consultation for cancelled appointment")
    pdf.bullet("400 prescription.diagnosis required / items must not be empty")
    pdf.bullet("400 Prescription already exists for this appointment")
    pdf.bullet("409 Patient already has a queue entry with this doctor today (rare edge)")

    pdf.sub_title("4.8 Suggested TypeScript")
    pdf.code_block(
        """
type SaveConsultationRequest = {
  appointment_id: number;
  clinical?: {
    symptoms?: string;
    diagnosis?: string;
    notes?: string;
    follow_up_date?: string; // YYYY-MM-DD
  };
  prescription?: {
    diagnosis: string;
    notes?: string;
    items: Array<{
      medicine_name: string;
      dosage: string;
      frequency: string;
      duration: number;
      instructions?: string;
    }>;
  };
};

type SaveConsultationResponse = {
  success: boolean;
  message: string;
  appointment: Record<string, unknown>;
  queue: { id: number; status: string; appointment_id: number; token_number?: number };
  prescription?: Record<string, unknown> | null;
};
"""
    )

    # Checklist
    pdf.add_page()
    pdf.section_title("5. Frontend Implementation Checklist")
    pdf.sub_title("Receptionist")
    pdf.bullet("[ ] Dashboard cards use GET /receptionist/dashboard fields only")
    pdf.bullet("[ ] Queue time column binds to scheduled_at (format local IST)")
    pdf.bullet("[ ] Pager uses response.total after dedupe (no client unique hacks)")
    pdf.bullet("[ ] Update QueueItem TypeScript to include scheduled_at")

    pdf.sub_title("Nurse")
    pdf.bullet("[ ] IPD bed patient vitals form sends patient_id")
    pdf.bullet("[ ] IPD nursing notes form sends patient_id")
    pdf.bullet("[ ] OPD forms continue sending appointment_id")
    pdf.bullet("[ ] Handle nullable appointment_id in list/detail UI")
    pdf.bullet("[ ] Show friendly error if patient is not on an occupied bed")

    pdf.sub_title("Doctor")
    pdf.bullet("[ ] Replace multi-step complete flow with POST /consultations/save")
    pdf.bullet("[ ] Include prescription payload in same save when Rx is written")
    pdf.bullet("[ ] On success, refresh appointment + queue from response (status=completed)")
    pdf.bullet("[ ] Remove dependency on intermediate waiting/in_progress UI steps for finish")

    pdf.section_title("6. Quick Endpoint Map")
    ew = [pdf.epw * 0.12, pdf.epw * 0.48, pdf.epw * 0.40]
    pdf.table_row(["Method", "Path", "Change"], bold=True, widths=ew)
    pdf.table_row(["GET", "/receptionist/dashboard", "Accurate distinct counts"], widths=ew)
    pdf.table_row(["GET", "/receptionist/today-queue", "Dedupe + scheduled_at"], widths=ew)
    pdf.table_row(["GET", "/receptionist/doctor-queue/{id}", "Dedupe + scheduled_at"], widths=ew)
    pdf.table_row(["GET", "/receptionist/queue-history", "Dedupe + scheduled_at"], widths=ew)
    pdf.table_row(["POST", "/nurse/vitals", "patient_id OR appointment_id"], widths=ew)
    pdf.table_row(["POST", "/nurse/notes", "patient_id OR appointment_id"], widths=ew)
    pdf.table_row(["POST", "/consultations/save", "Atomic clinical + Rx + complete"], widths=ew)
    pdf.table_row(["PUT", "/queue/complete", "Same save body as above"], widths=ew)

    pdf.section_title("7. Notes for QA")
    pdf.bullet("Receptionist: create multi-visit/queue join cases; dashboard must not inflate.")
    pdf.bullet("Receptionist: same patient two appointments same day -> one canonical row on today-queue.")
    pdf.bullet("Receptionist: time column shows 1:00 PM style from scheduled_at.")
    pdf.bullet("Nurse IPD: occupied bed patient can save vitals with only patient_id.")
    pdf.bullet("Nurse OPD: appointment_id path unchanged.")
    pdf.bullet("Doctor: one Save completes consult; if Rx included, prescription row exists immediately.")
    pdf.bullet("Doctor: second save on completed appointment returns 400.")

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        5,
        "Generated for SaffoCare HMS frontend team. Backend source of truth: "
        "Services/receptionist_service.py, Schemas/receptionist_schema.py, "
        "Schemas/nurse_schema.py, nurse vitals/notes services, "
        "Schemas/doctor_consultation_schema.py, Services/doctor_consultation_service.py.",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
