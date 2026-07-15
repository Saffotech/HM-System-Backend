"""Generator: Receptionist Profile & Notifications - Frontend Developer Documentation PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "receptionist-profile-notifications-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Receptionist Profile & Notifications Frontend Guide",
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
    pdf.multi_cell(0, 11, "Receptionist Profile & Notifications\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: July 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System (FastAPI)  |  Auth: JWT Bearer token\n"
        "Modules: /receptionist/profile  +  /receptionist/notifications",
    )
    pdf.ln(4)

    # =========================================================
    pdf.section_title("1. Purpose & Scope")
    pdf.body(
        "This document describes the Receptionist Profile and Receptionist Notifications "
        "APIs so frontend developers can build the front-desk UI correctly. Receptionist "
        "role is view-only for OPD queue boards; this guide covers self-service profile "
        "and a simple HR/admin notification inbox only."
    )

    pdf.sub_title("What this covers")
    pdf.bullet("Receptionist self-service profile: view, update, upload/delete profile image")
    pdf.bullet("Editable vs admin-owned fields (read-only in UI)")
    pdf.bullet("Profile completion rules and image upload constraints")
    pdf.bullet("In-app notifications: list, unread badge, mark one/all as read")
    pdf.bullet("Receptionist-relevant notification types only (shift, department, account)")
    pdf.bullet("Suggested TypeScript types and frontend checklist")

    pdf.sub_title("What this does NOT cover")
    pdf.bullet(
        "Receptionist queue boards (dashboard, today-queue, doctor-queue, history, schedule) "
        "- see receptionist module docs"
    )
    pdf.bullet("Clinical notifications (appointments, lab, prescriptions, emergencies, handovers)")
    pdf.bullet("Admin staff APIs (/users) except as notification triggers for shift/dept/account")
    pdf.bullet("Push notifications, WebSocket, or SSE (not implemented - poll unread-count)")
    pdf.bullet("Delete notification or notification preferences (not implemented)")

    pdf.sub_title("Product rule (important)")
    pdf.body(
        "Receptionist notifications are intentionally simple. Inbox receives only admin/HR "
        "events: SHIFT_UPDATED and ADMIN_UPDATE (department / deactivate / delete). "
        "Do not build UI filters or deep-links for doctor/nurse clinical notification types."
    )

    pdf.sub_title("Auth header (all endpoints)")
    pdf.code_block("Authorization: Bearer <access_token>")
    pdf.body(
        "Login via POST /auth/login. JWT must include the required permission. "
        'Only role name "receptionist" can use profile endpoints. Inactive accounts: 403. '
        "Soft-deleted / missing users: 404."
    )

    pdf.sub_title("Required JWT permissions (receptionist seed)")
    w = [70, 100]
    pdf.table_row(["Permission", "Used for"], w, bold=True)
    pdf.table_row(["receptionist_profile:view", "GET /receptionist/profile"], w)
    pdf.table_row(["receptionist_profile:update", "PUT /receptionist/profile"], w)
    pdf.table_row(
        ["receptionist_profile:upload_image", "POST /receptionist/profile/image"],
        w,
    )
    pdf.table_row(
        ["receptionist_profile:delete_image", "DELETE /receptionist/profile/image"],
        w,
    )
    pdf.table_row(["notifications:view", "List + unread-count"], w)
    pdf.table_row(["notifications:update", "Mark one / mark all read"], w)
    pdf.body(
        "After seed/permission changes, receptionists must re-login so the JWT includes "
        "notifications:view and notifications:update."
    )

    # =========================================================
    pdf.section_title("2. Module A - Receptionist Profile")
    pdf.body(
        "Prefix: /receptionist  |  Router: Routers/receptionist_profile_router.py  |  "
        "Tag: Receptionist Profile"
    )
    pdf.body(
        'Only users with role "receptionist" can call these endpoints. Admins manage '
        "employee_id, joining_date, department, and shift via admin staff APIs - "
        "not via /receptionist/profile."
    )

    pdf.sub_title("2.1 Endpoint summary")
    w = [55, 18, 50, 47]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], w, bold=True)
    pdf.table_row(
        ["GET /receptionist/profile", "200", "receptionist_profile:view", "Load full profile"],
        w,
    )
    pdf.table_row(
        ["PUT /receptionist/profile", "200", "receptionist_profile:update", "Update editable fields"],
        w,
    )
    pdf.table_row(
        [
            "POST /receptionist/profile/image",
            "200",
            "receptionist_profile:upload_image",
            "Upload avatar",
        ],
        w,
    )
    pdf.table_row(
        [
            "DELETE /receptionist/profile/image",
            "200",
            "receptionist_profile:delete_image",
            "Remove avatar",
        ],
        w,
    )

    # ---------------------------------------------------------
    pdf.sub_title("2.2 GET /receptionist/profile")
    pdf.body(
        "Request body: none. Returns ReceptionistProfileResponse "
        "(nested address, emergency_contact, department, role, shift)."
    )
    pdf.code_block(
        """{
  "user_id": 31,
  "first_name": "Riya",
  "last_name": "Patel",
  "email": "riya.reception@hospital.com",
  "phone": "9000000099",
  "phone_code": "+91",
  "address": {
    "line": "5 Main Lobby",
    "city": "Pune",
    "state": "Maharashtra"
  },
  "date_of_birth": "1995-04-12",
  "gender": 2,
  "emergency_contact": {
    "name": "Karan Patel",
    "phone": "9123456789"
  },
  "department": { "id": 1, "name": "Front Desk" },
  "role": { "id": 7, "name": "receptionist" },
  "employee_id": "REC-042",
  "qualification": "Front Desk Diploma",
  "experience_years": 3,
  "joining_date": "2023-01-15",
  "bio": "Patient guidance and OPD queue support.",
  "languages": ["English", "Hindi", "Marathi"],
  "shift": {
    "name": "Morning",
    "start_time": "08:00",
    "end_time": "16:00"
  },
  "profile_image_url": "/uploads/receptionist_image/a1b2c3d4.jpg",
  "is_profile_completed": true,
  "profile_completion_percentage": 100,
  "is_active": true,
  "last_login": "2026-07-15T08:01:00+05:30",
  "created_at": "2026-01-10T10:00:00+05:30",
  "updated_at": "2026-07-14T18:20:00+05:30"
}"""
    )

    pdf.body("Response field reference:")
    wf = [48, 40, 82]
    pdf.table_row(["Field", "Type", "Notes"], wf, bold=True)
    pdf.table_row(["user_id", "number", "Receptionist user id"], wf)
    pdf.table_row(["first_name", "string", "Read-only"], wf)
    pdf.table_row(["last_name", "string | null", "Read-only"], wf)
    pdf.table_row(["email", "string (email)", "Read-only"], wf)
    pdf.table_row(["phone", "string | null", "Editable"], wf)
    pdf.table_row(["phone_code", "string | null", "Editable (e.g. +91)"], wf)
    pdf.table_row(["address", "object", "{ line, city, state } - editable"], wf)
    pdf.table_row(["date_of_birth", "string | null", "YYYY-MM-DD, editable"], wf)
    pdf.table_row(["gender", "number | null", "1-4, see Gender codes"], wf)
    pdf.table_row(["emergency_contact", "object", "{ name, phone } - editable"], wf)
    pdf.table_row(
        ["department", "object | null", "{ id, name } - admin-owned, read-only"],
        wf,
    )
    pdf.table_row(["role", "object | null", "{ id, name } - read-only"], wf)
    pdf.table_row(["employee_id", "string | null", "Admin-owned, read-only"], wf)
    pdf.table_row(["qualification", "string | null", "Editable"], wf)
    pdf.table_row(["experience_years", "number | null", "Editable, 0-60"], wf)
    pdf.table_row(["joining_date", "string | null", "Admin-owned, read-only"], wf)
    pdf.table_row(["bio", "string | null", "Editable"], wf)
    pdf.table_row(["languages", "string[]", "Editable, default []"], wf)
    pdf.table_row(
        ["shift", "object | null", "{ name, start_time, end_time } - admin-owned"],
        wf,
    )
    pdf.table_row(
        ["profile_image_url", "string | null", "Relative path under /uploads"],
        wf,
    )
    pdf.table_row(
        ["is_profile_completed", "boolean", "Server-computed (see rules below)"],
        wf,
    )
    pdf.table_row(
        ["profile_completion_percentage", "number", "0-100, 14 field checks"],
        wf,
    )
    pdf.table_row(["is_active", "boolean", "Account status"], wf)
    pdf.table_row(["last_login", "datetime | null", "ISO with timezone"], wf)
    pdf.table_row(["created_at / updated_at", "datetime | null", "Profile timestamps"], wf)

    pdf.sub_title("Gender codes (integer, not label)")
    pdf.bullet("1 = Male")
    pdf.bullet("2 = Female")
    pdf.bullet("3 = Other")
    pdf.bullet("4 = Prefer not to say")
    pdf.body("API returns the integer. Map to labels in the UI.")

    pdf.sub_title("Profile completion rules")
    pdf.bullet(
        "is_profile_completed = true only when qualification AND experience_years "
        "(not null) AND bio are all set."
    )
    pdf.bullet(
        "profile_completion_percentage: 14 checks - phone, phone_code, address.line, city, "
        "state, DOB, gender, emergency name/phone, qualification, experience_years, bio, "
        "languages (non-empty), profile image."
    )
    pdf.body("Show a completion progress bar using profile_completion_percentage.")

    pdf.sub_title("Errors (GET)")
    pdf.bullet("401 - Missing/invalid JWT")
    pdf.bullet("403 - Missing permission, inactive account, or role is not receptionist")
    pdf.bullet(
        '404 - User/profile not found ("Receptionist profile not found. Contact admin.")'
    )

    # ---------------------------------------------------------
    pdf.sub_title("2.3 PUT /receptionist/profile")
    pdf.body(
        'Content-Type: application/json. Schema: ReceptionistProfileUpdate with '
        'extra="forbid". Partial updates are allowed. Empty body / no fields => 400 '
        '"No fields to update". Unknown or admin-only fields => 422.'
    )
    pdf.code_block(
        """{
  "qualification": "Front Desk Diploma",
  "experience_years": 3,
  "bio": "Patient guidance and OPD queue support.",
  "languages": ["English", "Hindi"],
  "phone": "9000000099",
  "phone_code": "+91",
  "address": {
    "line": "5 Main Lobby",
    "city": "Pune",
    "state": "Maharashtra"
  },
  "date_of_birth": "1995-04-12",
  "gender": 2,
  "emergency_contact": {
    "name": "Karan Patel",
    "phone": "9123456789"
  }
}"""
    )

    pdf.sub_title("Editable vs read-only")
    we = [55, 40, 75]
    pdf.table_row(["Field", "Receptionist edit?", "UI tip"], we, bold=True)
    pdf.table_row(["qualification", "Yes", "Text, max 255"], we)
    pdf.table_row(["experience_years", "Yes", "Number 0-60"], we)
    pdf.table_row(["bio", "Yes", "Textarea"], we)
    pdf.table_row(["languages", "Yes", "Tag input; trimmed, deduped"], we)
    pdf.table_row(["phone / phone_code", "Yes", "max 20 / max 10"], we)
    pdf.table_row(["address.{line,city,state}", "Yes", "city/state max 100"], we)
    pdf.table_row(["date_of_birth", "Yes", "Date picker YYYY-MM-DD"], we)
    pdf.table_row(["gender", "Yes", "Select 1-4"], we)
    pdf.table_row(["emergency_contact", "Yes", "name max 120, phone max 20"], we)
    pdf.table_row(["first_name, last_name, email", "No", "Display only"], we)
    pdf.table_row(["employee_id", "No", "Admin-owned"], we)
    pdf.table_row(["joining_date", "No", "Admin-owned"], we)
    pdf.table_row(["department / role", "No", "Display only"], we)
    pdf.table_row(
        ["shift", "No", "Admin updates; receptionist gets SHIFT_UPDATED"],
        we,
    )
    pdf.table_row(
        ["profile_image_url", "No in PUT", "Use image upload/delete endpoints"],
        we,
    )

    pdf.body(
        "Do NOT send name, email, employee_id, joining_date, department, role, shift, "
        "profile_image_url, is_profile_completed, or profile_completion_percentage in PUT."
    )
    pdf.body("Success response: full ReceptionistProfileResponse (same shape as GET).")

    # ---------------------------------------------------------
    pdf.sub_title("2.4 POST /receptionist/profile/image")
    pdf.body("multipart/form-data. Field name: file (required).")
    pdf.bullet("Allowed: .jpg .jpeg .png .webp")
    pdf.bullet("Max size: 5 MB")
    pdf.bullet("Empty file rejected")
    pdf.bullet("Stores under uploads/receptionist_image/ (or RECEPTIONIST_PROFILE_UPLOAD_DIR)")
    pdf.bullet("Replaces previous image file on success")
    pdf.code_block(
        """{
  "message": "Profile image uploaded successfully",
  "profile_image_url": "/uploads/receptionist_image/<uuid>.jpg"
}"""
    )
    pdf.body(
        "Display image as: API_BASE + profile_image_url "
        "(e.g. http://localhost:8000/uploads/receptionist_image/...)."
    )

    pdf.sub_title("2.5 DELETE /receptionist/profile/image")
    pdf.code_block(
        """{
  "message": "Profile image deleted successfully",
  "profile_image_url": null
}"""
    )
    pdf.bullet("404 if no image set")

    pdf.sub_title("Image / update errors")
    pdf.bullet("400 - Invalid type, empty file, >5 MB, empty PUT body")
    pdf.bullet("401 / 403 / 404 - same auth/role/profile rules as GET")
    pdf.bullet("422 - Forbidden extra fields on PUT")

    # =========================================================
    pdf.add_page()
    pdf.section_title("3. Module B - Receptionist Notifications")
    pdf.body(
        "Prefix: /receptionist/notifications  |  "
        "Router: Routers/receptionist_notification_router.py  |  "
        "Tag: Receptionist Notifications"
    )
    pdf.body(
        "Uses the shared notifications table, filtered by the logged-in receptionist "
        "user_id. Same response schema as doctor/nurse notifications, different URL "
        "prefix and a much smaller trigger set (HR/admin only)."
    )

    pdf.sub_title("3.1 Endpoint summary")
    w = [62, 18, 48, 42]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], w, bold=True)
    pdf.table_row(
        [
            "GET /receptionist/notifications/unread-count",
            "200",
            "notifications:view",
            "Badge count",
        ],
        w,
    )
    pdf.table_row(
        [
            "GET /receptionist/notifications",
            "200",
            "notifications:view",
            "Paginated list",
        ],
        w,
    )
    pdf.table_row(
        [
            "PATCH /receptionist/notifications/{id}/read",
            "200",
            "notifications:update",
            "Mark one read",
        ],
        w,
    )
    pdf.table_row(
        [
            "PATCH /receptionist/notifications/read-all",
            "200",
            "notifications:update",
            "Mark all read",
        ],
        w,
    )

    # ---------------------------------------------------------
    pdf.sub_title("3.2 GET /receptionist/notifications/unread-count")
    pdf.code_block('{ "count": 2 }')
    pdf.body(
        "Poll every 15-30 seconds for the header badge. No WebSocket/SSE in backend yet."
    )

    # ---------------------------------------------------------
    pdf.sub_title("3.3 GET /receptionist/notifications")
    pdf.body("Query parameters:")
    wq = [40, 35, 95]
    pdf.table_row(["Param", "Type / rules", "Purpose"], wq, bold=True)
    pdf.table_row(["page", "int >= 1, default 1", "Page number"], wq)
    pdf.table_row(["limit", "int 1-100, default 20", "Page size"], wq)
    pdf.table_row(["search", "string min 1", "ILIKE title, message, created_by_name"], wq)
    pdf.table_row(["is_read", "bool optional", "Filter unread/read"], wq)
    pdf.table_row(["source_module", "enum optional", "Receptionist usually ADMIN"], wq)
    pdf.table_row(
        ["notification_type", "enum optional", "SHIFT_UPDATED or ADMIN_UPDATE"],
        wq,
    )
    pdf.table_row(["start_date / end_date", "date optional", "Inclusive Asia/Kolkata"], wq)

    pdf.body(
        "Sort order: priority CRITICAL then HIGH then NORMAL, then created_at DESC "
        "(newest first within priority)."
    )
    pdf.code_block(
        """GET /receptionist/notifications?page=1&limit=20&is_read=false

{
  "total": 2,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": 901,
      "user_id": 31,
      "title": "Shift updated by admin",
      "message": "Admin changed your duty shift:\\n- Shift name: Evening\\n- Shift start time: 14:00\\n- Shift end time: 22:00",
      "notification_type": "SHIFT_UPDATED",
      "priority": "HIGH",
      "source_module": "ADMIN",
      "reference_type": "SCHEDULE",
      "reference_id": 31,
      "created_by": 2,
      "created_by_name": "Hospital Admin",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-07-15T09:15:00+05:30"
    }
  ]
}"""
    )

    pdf.body("NotificationResponse fields:")
    wn = [42, 42, 86]
    pdf.table_row(["Field", "Type", "Notes"], wn, bold=True)
    pdf.table_row(["id", "number", "Notification id"], wn)
    pdf.table_row(["user_id", "number", "Recipient receptionist"], wn)
    pdf.table_row(["title", "string", "Short headline"], wn)
    pdf.table_row(["message", "string | null", "Body text (may include newlines)"], wn)
    pdf.table_row(["notification_type", "enum string", "See type table below"], wn)
    pdf.table_row(["priority", "NORMAL|HIGH|CRITICAL", "UI badge styling"], wn)
    pdf.table_row(["source_module", "enum string", "Usually ADMIN"], wn)
    pdf.table_row(["reference_type", "enum string", "Deep-link entity type"], wn)
    pdf.table_row(["reference_id", "number", "Deep-link entity id"], wn)
    pdf.table_row(["created_by", "number | null", "Actor user id"], wn)
    pdf.table_row(["created_by_name", "string | null", "Actor display name"], wn)
    pdf.table_row(["is_read", "boolean", "Read flag"], wn)
    pdf.table_row(["read_at", "datetime | null", "Set when marked read"], wn)
    pdf.table_row(["created_at", "datetime", "ISO with timezone"], wn)

    # ---------------------------------------------------------
    pdf.sub_title("3.4 PATCH /receptionist/notifications/{notification_id}/read")
    pdf.body(
        "Marks one notification as read for the current receptionist. Idempotent "
        "(already-read returns success). Sets is_read=true and read_at=now(IST). "
        "404 if notification does not belong to this receptionist."
    )
    pdf.body("Response: full NotificationResponse.")

    pdf.sub_title("3.5 PATCH /receptionist/notifications/read-all")
    pdf.code_block('{ "message": "All notifications marked as read" }')
    pdf.body("Marks every unread notification for this receptionist as read.")

    # =========================================================
    pdf.section_title("4. Receptionist notification types (what you will actually receive)")
    pdf.body(
        "The shared NotificationType enum has many clinical values. Receptionists only "
        "receive the types below. Build filters, copy, and deep-links around these only."
    )

    wt = [38, 18, 22, 28, 64]
    pdf.table_row(
        ["notification_type", "priority", "source", "reference", "When created"],
        wt,
        bold=True,
    )
    pdf.table_row(
        [
            "SHIFT_UPDATED",
            "HIGH",
            "ADMIN",
            "SCHEDULE",
            "Admin changes shift_name / start / end on receptionist profile",
        ],
        wt,
    )
    pdf.table_row(
        [
            "ADMIN_UPDATE",
            "HIGH",
            "ADMIN",
            "USER",
            "Admin reassigns department, deactivates, or deletes receptionist account",
        ],
        wt,
    )

    pdf.sub_title("Example titles / messages (for UI copy)")
    pdf.bullet('SHIFT_UPDATED title: "Shift updated by admin"')
    pdf.bullet('ADMIN_UPDATE (dept) title: "Department reassigned"')
    pdf.bullet('ADMIN_UPDATE (deactivate) title: "Account disabled by admin"')
    pdf.bullet('ADMIN_UPDATE (delete) title: "Account removed by admin"')

    pdf.sub_title("Deep-link suggestions")
    pdf.bullet(
        "reference_type = SCHEDULE -> open Profile page, focus read-only shift section"
    )
    pdf.bullet(
        "reference_type = USER + ADMIN_UPDATE (department) -> open Profile, show department"
    )
    pdf.bullet(
        "reference_type = USER + account disabled/removed -> show notice; force logout "
        "on next 401/403"
    )

    pdf.sub_title("Do NOT expect these for receptionist")
    pdf.bullet("NEW_APPOINTMENT / APPOINTMENT_CANCELLED / APPOINTMENT_RESCHEDULED")
    pdf.bullet("LAB_REPORT_READY / PRESCRIPTION_* / PATIENT_CHECKED_IN")
    pdf.bullet("EMERGENCY_ALERT / HANDOVER_TAKEN_OVER")
    pdf.body(
        "Those stay on doctor/nurse. Receptionist uses queue board screens for live OPD "
        "patient guidance instead of clinical notification spam."
    )

    pdf.sub_title("Enums (full, for TypeScript union types)")
    pdf.body(
        "NotificationType: NEW_APPOINTMENT | APPOINTMENT_CANCELLED | APPOINTMENT_RESCHEDULED | "
        "PATIENT_CHECKED_IN | LAB_REPORT_READY | LAB_REPORT_UPDATED | PRESCRIPTION_CREATED | "
        "PRESCRIPTION_UPDATED | EMERGENCY_ALERT | ADMIN_UPDATE | HANDOVER_TAKEN_OVER | SHIFT_UPDATED"
    )
    pdf.body("Priority: NORMAL | HIGH | CRITICAL")
    pdf.body(
        "SourceModule: OPD_BILLING | LAB | RECEPTIONIST | NURSE | PHARMACY | ADMIN | SYSTEM"
    )
    pdf.body(
        "ReferenceType: APPOINTMENT | LAB_ORDER | PRESCRIPTION | BILL | PATIENT | USER | "
        "SCHEDULE | LEAVE | HANDOVER | ALERT"
    )

    # =========================================================
    pdf.section_title("5. Suggested TypeScript types")
    pdf.code_block(
        """type GenderCode = 1 | 2 | 3 | 4;

interface AddressInfo {
  line?: string | null;
  city?: string | null;
  state?: string | null;
}

interface EmergencyContactInfo {
  name?: string | null;
  phone?: string | null;
}

interface ReceptionistProfile {
  user_id: number;
  first_name: string;
  last_name?: string | null;
  email: string;
  phone?: string | null;
  phone_code?: string | null;
  address: AddressInfo;
  date_of_birth?: string | null;
  gender?: GenderCode | null;
  emergency_contact: EmergencyContactInfo;
  department?: { id: number; name: string } | null;
  role?: { id: number; name: string } | null;
  employee_id?: string | null;
  qualification?: string | null;
  experience_years?: number | null;
  joining_date?: string | null;
  bio?: string | null;
  languages: string[];
  shift?: {
    name?: string | null;
    start_time?: string | null; // "HH:MM"
    end_time?: string | null;   // "HH:MM"
  } | null;
  profile_image_url?: string | null;
  is_profile_completed: boolean;
  profile_completion_percentage: number;
  is_active: boolean;
  last_login?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface ReceptionistProfileUpdate {
  qualification?: string;
  experience_years?: number;
  bio?: string;
  languages?: string[];
  phone?: string;
  phone_code?: string;
  address?: AddressInfo;
  date_of_birth?: string;
  gender?: GenderCode;
  emergency_contact?: EmergencyContactInfo;
}

/** Types a receptionist actually receives */
type ReceptionistNotificationType = "SHIFT_UPDATED" | "ADMIN_UPDATE";

interface ReceptionistNotification {
  id: number;
  user_id: number;
  title: string;
  message?: string | null;
  notification_type: ReceptionistNotificationType | string;
  priority: "NORMAL" | "HIGH" | "CRITICAL";
  source_module: string;
  reference_type: string;
  reference_id: number;
  created_by?: number | null;
  created_by_name?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

interface NotificationListResponse {
  total: number;
  page: number;
  limit: number;
  items: ReceptionistNotification[];
}"""
    )

    # =========================================================
    pdf.section_title("6. Suggested UI behaviour")
    pdf.sub_title("Profile page")
    pdf.bullet("Sections: Personal info | Professional | Shift (read-only) | Avatar")
    pdf.bullet("Disable employee_id, joining_date, department, role, shift inputs")
    pdf.bullet("Show shift as chips/labels: name + HH:MM - HH:MM")
    pdf.bullet("Progress bar from profile_completion_percentage; banner if incomplete")
    pdf.bullet("Avatar: show API_BASE + profile_image_url; upload/delete buttons")

    pdf.sub_title("Notifications inbox")
    pdf.bullet("Header bell + badge from unread-count (poll 15-30s)")
    pdf.bullet("List cards: title, message (preserve newlines), priority chip, relative time")
    pdf.bullet("Filters: Unread / All, type chips SHIFT_UPDATED | ADMIN_UPDATE, search")
    pdf.bullet("Click row -> PATCH .../read then navigate by reference_type")
    pdf.bullet('"Mark all as read" toolbar action')
    pdf.bullet("Empty state when total === 0")
    pdf.bullet("Visual priority: HIGH amber (receptionist MVP is all HIGH)")
    pdf.bullet("Do not invent delete/archive/preferences UI until backend supports it")

    # =========================================================
    pdf.section_title("7. Frontend implementation checklist")
    pdf.sub_title("Profile")
    pdf.bullet("[ ] Load GET /receptionist/profile on Profile page mount")
    pdf.bullet("[ ] Render nested address / emergency_contact / department / shift")
    pdf.bullet("[ ] Disable admin-owned fields (employee_id, joining_date, dept, shift)")
    pdf.bullet("[ ] PUT only editable fields; reject extra keys (extra=forbid)")
    pdf.bullet("[ ] Show completion % progress + is_profile_completed banner")
    pdf.bullet("[ ] Map gender int 1-4 to UI labels")
    pdf.bullet("[ ] Image upload via multipart field `file`; preview with API_BASE + url")
    pdf.bullet("[ ] Delete image updates UI to null avatar")

    pdf.sub_title("Notifications")
    pdf.bullet("[ ] Poll GET /receptionist/notifications/unread-count for header badge")
    pdf.bullet("[ ] Inbox: list with page/limit; tabs or filter for is_read")
    pdf.bullet("[ ] Style HIGH / NORMAL (CRITICAL rare for receptionist)")
    pdf.bullet("[ ] Click item -> PATCH .../read then deep-link by reference_type")
    pdf.bullet("[ ] Mark all read -> PATCH .../read-all then refresh count")
    pdf.bullet("[ ] Handle SHIFT_UPDATED and ADMIN_UPDATE only")
    pdf.bullet("[ ] After admin deactivate/delete notice, force re-auth if 401/403")

    pdf.sub_title("Common")
    pdf.bullet("[ ] Always send Authorization: Bearer <token>")
    pdf.bullet("[ ] Handle 401 (login), 403 (permission/role), 404, 422 validation")
    pdf.bullet(
        "[ ] Re-login after seed if receptionist_profile:* or notifications:* missing in JWT"
    )

    # =========================================================
    pdf.section_title("8. Quick reference - base URLs")
    pdf.code_block(
        """Profile:
  GET    /receptionist/profile
  PUT    /receptionist/profile
  POST   /receptionist/profile/image     (multipart file)
  DELETE /receptionist/profile/image

Notifications:
  GET    /receptionist/notifications/unread-count
  GET    /receptionist/notifications
  PATCH  /receptionist/notifications/{notification_id}/read
  PATCH  /receptionist/notifications/read-all

Static files:
  GET    /uploads/receptionist_image/<filename>
"""
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        5,
        "Generated from HM-System-Backend Docs/generate_receptionist_profile_notification_pdf.py. "
        "Aligned with Routers/receptionist_profile_router.py and "
        "Routers/receptionist_notification_router.py (July 2026).",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
