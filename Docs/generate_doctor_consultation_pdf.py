"""One-off generator: Doctor Consultation & Queue module changes PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "doctor-consultation-workflow-changes.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "SaffoCare HMS - Doctor Consultation Module Changes", align="C", new_x="LMARGIN", new_y="NEXT")
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
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        for line in text.strip().splitlines():
            self.cell(0, 5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(0, 10, "Doctor Consultation Workflow\nBackend Changes Documentation")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6, "Version: 1.0  |  Date: June 2026  |  Scope: HM-System backend only")
    pdf.ln(4)

    pdf.section_title("1. Purpose")
    pdf.body(
        "This document describes backend changes for the Doctor Consultation workflow. "
        "The goal is to let doctors open a consultation without mutating queue status, "
        "save clinical data in one atomic step, and keep appointments and patient_queue "
        "consistent across doctor, reception, nurse, OPD, and pharmacy modules."
    )

    pdf.section_title("2. Problem Solved (Before vs After)")
    pdf.sub_title("Before")
    pdf.bullet("Opening consult required queue/add and queue/start (status mutations).")
    pdf.bullet("Saving required queue_id and a 3-step chain: add, start, complete.")
    pdf.bullet("PUT /queue/complete accepted clinical JSON but did not persist it.")
    pdf.bullet("PUT /appointments/{id}/status could not go scheduled to completed.")
    pdf.ln(2)
    pdf.sub_title("After")
    pdf.bullet("GET /consultations/appointment/{id} loads context read-only.")
    pdf.bullet("POST /consultations/save and PUT /queue/complete complete in one request.")
    pdf.bullet("PATCH /consultations/appointment/{id} completes with queue optional.")
    pdf.bullet("Clinical fields persist on appointments (symptoms, diagnosis, notes, follow_up_date).")
    pdf.bullet("PUT /appointments/{appointment_id}/status supports scheduled/waiting to completed with queue sync.")

    pdf.section_title("3. New API Endpoints")
    pdf.sub_title("Doctor Consultations (/consultations)")
    pdf.body("Tag: Doctor Consultations | Router: Routers/doctor_consultation_router.py")
    pdf.bullet("GET /consultations/appointment/{appointment_id} - Read-only context (appointments:view)")
    pdf.bullet("POST /consultations/save - Atomic save with queue ensured (appointments:update)")
    pdf.bullet("PATCH /consultations/appointment/{appointment_id} - Queue-optional save (appointments:update)")

    pdf.sub_title("Doctor Patient Queue - Extended (/queue)")
    pdf.body("Tag: Doctor Patient Queue | Router: Routers/doctor_patient_queue_router.py")
    pdf.bullet("PUT /queue/complete - NEW: Atomic save by appointment_id (same logic as POST /consultations/save)")
    pdf.bullet("PUT /queue/complete/{queue_id} - ENHANCED: Persists clinical body; returns appointment in response")

    pdf.sub_title("Doctor Appointments - Updated (/appointments)")
    pdf.bullet("PUT /appointments/{appointment_id}/status - scheduled/waiting -> completed allowed; syncs queue if row exists")

    pdf.section_title("4. API Request / Response Examples")
    pdf.sub_title("POST /consultations/save  |  PUT /queue/complete")
    pdf.code_block(
        """Request:
{
  "appointment_id": 17,
  "clinical": {
    "symptoms": "Fever, cough",
    "diagnosis": "Viral URI",
    "notes": "Rest and fluids",
    "follow_up_date": "2026-07-15"
  }
}

Response 200:
{
  "success": true,
  "message": "Consultation saved",
  "appointment": { "id": 17, "status": "completed", ... },
  "queue": { "id": 42, "status": "completed", "appointment_id": 17 }
}"""
    )

    pdf.sub_title("GET /consultations/appointment/{appointment_id}")
    pdf.code_block(
        """Response 200:
{
  "success": true,
  "appointment": { ... patient + visit fields ... },
  "queue": { "id": 42, "status": "waiting", ... } | null,
  "prescriptions": [ ... recent for patient ... ],
  "lab_orders": [ ... for this appointment ... ]
}"""
    )

    pdf.sub_title("PATCH /consultations/appointment/{appointment_id} (queue optional)")
    pdf.code_block(
        """Request body (clinical only):
{
  "symptoms": "Fever",
  "diagnosis": "Viral URI",
  "notes": "Rest",
  "follow_up_date": "2026-07-15"
}

Behavior:
- Does NOT create patient_queue row.
- If queue row exists today -> marks queue completed + saves clinical.
- If no queue row -> only appointment completed + clinical saved."""
    )

    pdf.add_page()
    pdf.section_title("5. Which Endpoint to Use")
    pdf.body(
        "Use POST /consultations/save or PUT /queue/complete when the doctor should finish "
        "the visit in one step and reception/nurse must see patient_queue completed "
        "(queue row created internally if missing)."
    )
    pdf.body(
        "Use PATCH /consultations/appointment/{id} when queue is optional for the doctor "
        "(no new queue row; only updates existing queue if checked in)."
    )
    pdf.body(
        "Use PUT /queue/complete/{queue_id} when you already have queue_id from reception check-in."
    )
    pdf.body(
        "Use PUT /appointments/{id}/status with status=completed for status-only completion "
        "(no clinical body); syncs queue if row exists."
    )

    pdf.section_title("6. Internal Service Flow")
    pdf.sub_title("Atomic save (POST /consultations/save, PUT /queue/complete)")
    pdf.bullet("save_consultation_service() in Services/doctor_consultation_service.py")
    pdf.bullet("1. Load and lock appointment; reject completed/cancelled.")
    pdf.bullet("2. ensure_queue_for_appointment() - get or create today's queue row.")
    pdf.bullet("3. finalize_consultation() - clinical fields + queue completed + appointment completed.")
    pdf.bullet("4. Single database commit.")

    pdf.sub_title("Queue-optional save (PATCH /consultations/appointment/{id})")
    pdf.bullet("complete_appointment_consultation_service() in Services/doctor_appointment_service.py")
    pdf.bullet("complete_queue_for_appointment_if_exists() - only if row exists today.")
    pdf.bullet("Otherwise appointment-only completion with clinical fields.")

    pdf.sub_title("Queue helpers (Services/doctor_patient_queue_service.py)")
    pdf.bullet("find_queue_for_appointment_today()")
    pdf.bullet("ensure_queue_for_appointment()")
    pdf.bullet("complete_queue_for_appointment_if_exists()")
    pdf.bullet("finalize_consultation()")
    pdf.bullet("_apply_clinical_to_appointment()")

    pdf.section_title("7. Files Added")
    pdf.bullet("Routers/doctor_consultation_router.py")
    pdf.bullet("Services/doctor_consultation_service.py")
    pdf.bullet("Schemas/doctor_consultation_schema.py")
    pdf.bullet("alembic/versions/a9b0c1d2e3f4_appointment_symptoms.py")

    pdf.section_title("8. Files Modified")
    pdf.bullet("main.py - registered consultation_router")
    pdf.bullet("Models/opd_billing.py - added appointments.symptoms column")
    pdf.bullet("Services/doctor_helpers.py - appointment_to_dict includes symptoms")
    pdf.bullet("Services/doctor_appointment_service.py - VALID_TRANSITIONS, PATCH service logic, status queue sync")
    pdf.bullet("Services/doctor_patient_queue_service.py - clinical persist, helpers, complete_consultation fix")
    pdf.bullet("Routers/doctor_patient_queue_router.py - PUT /queue/complete, enhanced complete response")
    pdf.bullet("Schemas/doctor_appointment_schema.py - AppointmentConsultationUpdate")

    pdf.section_title("9. Database Changes")
    pdf.bullet("Table: appointments")
    pdf.bullet("New column: symptoms (TEXT, nullable)")
    pdf.bullet("Existing columns used: diagnosis, notes, follow_up_date")
    pdf.bullet("No new tables. No new status enum values.")
    pdf.bullet("Migration: alembic upgrade head (revision a9b0c1d2e3f4)")

    pdf.section_title("10. Appointment Status Transitions (VALID_TRANSITIONS)")
    pdf.code_block(
        """scheduled  -> waiting | completed | cancelled
waiting    -> in_progress | completed | cancelled
in_progress -> completed | cancelled
completed  -> (none)
cancelled  -> (none)"""
    )

    pdf.section_title("11. Cross-Module Consistency")
    pdf.bullet("Doctor dashboard reads appointments.status")
    pdf.bullet("Reception and nurse read patient_queue")
    pdf.bullet("Pharmacy POST /prescriptions requires appointment.status == completed")
    pdf.bullet("Atomic save updates both appointment and queue in one transaction")
    pdf.bullet("PATCH queue-optional path may leave no queue row (nurse/reception queue empty for that visit)")

    pdf.section_title("12. Legacy Queue APIs (Unchanged)")
    pdf.bullet("GET /queue/today")
    pdf.bullet("PUT /queue/start/{queue_id}")
    pdf.bullet("GET /queue/current")
    pdf.bullet("POST /queue/request-next")
    pdf.bullet("POST /queue/add - removed (was legacy check-in alias)")

    pdf.section_title("13. Error Codes (Common)")
    pdf.bullet("404 - Appointment or queue not found / not doctor's patient")
    pdf.bullet("400 - Already completed, cancelled, or invalid status transition")
    pdf.bullet("409 - Patient already has another queue entry with same doctor today (atomic save)")

    pdf.section_title("14. Deployment Checklist")
    pdf.bullet("1. Run: alembic upgrade head")
    pdf.bullet("2. Restart FastAPI server")
    pdf.bullet("3. Verify Swagger tags: Doctor Consultations, Doctor Patient Queue")
    pdf.bullet("4. Test POST /consultations/save from scheduled appointment")
    pdf.bullet("5. Test PATCH /consultations/appointment/{id} without prior check-in")
    pdf.bullet("6. Test PUT /queue/complete with same body as POST /consultations/save")

    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
