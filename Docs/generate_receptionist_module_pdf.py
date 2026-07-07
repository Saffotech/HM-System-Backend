"""Generator: Receptionist Module - Payment-Gated Queue Guide (PDF)."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "receptionist-module-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Receptionist & Queue Workflow",
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


def build_pdf() -> None:
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 60, 120)
    pdf.multi_cell(0, 11, "OPD Payment-Gated Queue\nReceptionist View-Only Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6, "Version: 3.0  |  Date: July 2026")
    pdf.ln(6)

    pdf.section_title("1. End-to-end workflow")
    pdf.code_block(
        """Patient arrives
  -> Reception sends to OPD Billing
  -> Registration (if needed)
  -> Appointment created
  -> Payment completed (opd_visits.payment_status = paid)
  -> System auto-creates patient_queue row
  -> Receptionist dashboard shows patient (view only)
  -> Doctor GET /queue/today shows patient"""
    )

    pdf.section_title("2. Role responsibilities")
    pdf.bullet("OPD Billing: register, create appointment, collect payment")
    pdf.bullet("System: enqueue after payment (queue_enqueue_service.py)")
    pdf.bullet("Receptionist: view queue only - no billing, no queue creation")
    pdf.bullet("Doctor: consult, request-next, start/complete")

    pdf.section_title("3. Eligibility (receptionist sees only)")
    pdf.bullet("Appointment exists and status is not cancelled")
    pdf.bullet("Linked opd_visits.payment_status = paid")
    pdf.bullet("patient_queue row exists (auto-created after payment)")
    pdf.bullet("Unpaid (pending/partial) patients are NOT shown")

    pdf.section_title("4. OPD APIs that trigger enqueue")
    pdf.bullet("POST /opd/patient/register - pay now at register")
    pdf.bullet("POST /opd/visit - optional appointment_id for pre-booked")
    pdf.bullet("POST /opd/visit/{visit_id}/pay - pay later then auto-enqueue")

    pdf.section_title("5. Receptionist APIs (view only)")
    pdf.bullet("GET /receptionist/dashboard")
    pdf.bullet("GET /receptionist/today-queue")
    pdf.bullet("GET /receptionist/doctor-queue/{doctor_id}")
    pdf.bullet("GET /receptionist/queue-history")

    pdf.section_title("6. Key code files")
    pdf.bullet("Services/queue_enqueue_service.py")
    pdf.bullet("Services/opd_service.py")
    pdf.bullet("Services/receptionist_service.py")
    pdf.bullet("Models/patient.py - OpdVisit.appointment_id")
    pdf.bullet("alembic f6a7b8c9d0e1 - migration")

    pdf.section_title("7. Deployment")
    pdf.bullet("Run: alembic upgrade head")
    pdf.bullet("Run: python seed.py")
    pdf.bullet("Re-login receptionist and doctor users")

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
