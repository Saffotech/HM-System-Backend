"""Generator: Nurse Profile & Notifications - Frontend Developer Documentation PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "nurse-profile-notifications-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Nurse Profile & Notifications Frontend Guide",
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
    pdf.multi_cell(0, 11, "Nurse Profile & Notifications\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: July 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System (FastAPI)  |  Auth: JWT Bearer token\n"
        "Modules: /nurse/profile  +  /nurse/notifications",
    )
    pdf.ln(4)

    # =========================================================
    pdf.section_title("1. Purpose & Scope")
    pdf.body(
        "This document describes the Nurse Profile and Nurse Notifications APIs so frontend "
        "developers can build the nurse UI correctly. Both modules are fully implemented. "
        "Use this guide as the source of truth for endpoints, payloads, validation, "
        "permissions, and UI behaviour."
    )

    pdf.sub_title("What this covers")
    pdf.bullet("Nurse self-service profile: view, update, upload/delete profile image")
    pdf.bullet("Which fields nurses can edit vs admin-owned (read-only in UI)")
    pdf.bullet("Profile completion rules and image upload constraints")
    pdf.bullet("In-app nurse notifications: list, unread badge, mark one/all as read")
    pdf.bullet("Nurse-relevant notification types, priorities, filters, deep-link hints")
    pdf.bullet("Suggested TypeScript types and frontend checklist")

    pdf.sub_title("What this does NOT cover")
    pdf.bullet("Clinical nurse APIs (vitals, notes, medications, handovers, alerts) except as notification triggers")
    pdf.bullet("Admin staff APIs (/users) except where they own nurse fields / shift")
    pdf.bullet("Push notifications, WebSocket, or SSE (not implemented - poll unread-count)")
    pdf.bullet("Delete notification or notification preferences (not implemented)")

    pdf.sub_title("Auth header (all endpoints)")
    pdf.code_block("Authorization: Bearer <access_token>")
    pdf.body(
        "Login via POST /auth/login. JWT must include the required permission. "
        "Only role name \"nurse\" can use profile endpoints. Inactive accounts: 403. "
        "Soft-deleted / missing users: 404."
    )

    pdf.sub_title("Required JWT permissions (nurse seed)")
    w = [70, 100]
    pdf.table_row(["Permission", "Used for"], w, bold=True)
    pdf.table_row(["nurse_profile:view", "GET /nurse/profile"], w)
    pdf.table_row(["nurse_profile:update", "PUT /nurse/profile"], w)
    pdf.table_row(["nurse_profile:upload_image", "POST /nurse/profile/image"], w)
    pdf.table_row(["nurse_profile:delete_image", "DELETE /nurse/profile/image"], w)
    pdf.table_row(["notifications:view", "List + unread-count"], w)
    pdf.table_row(["notifications:update", "Mark one / mark all read"], w)
    pdf.body(
        "After seed/permission changes, nurses must re-login so the JWT includes new permissions."
    )

    # =========================================================
    pdf.section_title("2. Module A - Nurse Profile")
    pdf.body(
        "Prefix: /nurse  |  Router: Routers/nurse_profile_router.py  |  Tag: Nurse Profile"
    )
    pdf.body(
        "Only users with role \"nurse\" can call these endpoints. Admins manage "
        "license_number, employee_id, joining_date, department, and shift via admin staff APIs - "
        "not via /nurse/profile."
    )

    pdf.sub_title("2.1 Endpoint summary")
    w = [48, 18, 55, 49]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], w, bold=True)
    pdf.table_row(["GET /nurse/profile", "200", "nurse_profile:view", "Load full profile"], w)
    pdf.table_row(["PUT /nurse/profile", "200", "nurse_profile:update", "Update editable fields"], w)
    pdf.table_row(["POST /nurse/profile/image", "200", "nurse_profile:upload_image", "Upload avatar"], w)
    pdf.table_row(["DELETE /nurse/profile/image", "200", "nurse_profile:delete_image", "Remove avatar"], w)

    # ---------------------------------------------------------
    pdf.sub_title("2.2 GET /nurse/profile")
    pdf.body("Request body: none. Returns NurseProfileResponse (nested address, emergency_contact, department, role, shift).")
    pdf.code_block(
        """{
  "user_id": 21,
  "first_name": "Priya",
  "last_name": "Sharma",
  "email": "priya.nurse@hospital.com",
  "phone": "9876543210",
  "phone_code": "+91",
  "address": {
    "line": "12 Ward Road",
    "city": "Pune",
    "state": "Maharashtra"
  },
  "date_of_birth": "1992-06-15",
  "gender": 2,
  "emergency_contact": {
    "name": "Rahul Sharma",
    "phone": "9123456780"
  },
  "department": { "id": 3, "name": "General Ward" },
  "role": { "id": 4, "name": "nurse" },
  "qualification": "BSc Nursing",
  "license_number": "NRC-44521",
  "employee_id": "NUR-102",
  "experience_years": 6,
  "joining_date": "2020-03-01",
  "bio": "Ward nurse with focus on postop care.",
  "languages": ["English", "Hindi", "Marathi"],
  "shift": {
    "name": "Morning",
    "start_time": "08:00",
    "end_time": "16:00"
  },
  "profile_image_url": "/uploads/nurse_image/a1b2c3d4.jpg",
  "is_profile_completed": true,
  "profile_completion_percentage": 93,
  "is_active": true,
  "last_login": "2026-07-14T08:01:00+05:30",
  "created_at": "2026-01-10T10:00:00+05:30",
  "updated_at": "2026-07-13T18:20:00+05:30"
}"""
    )

    pdf.body("Response field reference:")
    wf = [48, 40, 82]
    pdf.table_row(["Field", "Type", "Notes"], wf, bold=True)
    pdf.table_row(["user_id", "number", "Nurse user id"], wf)
    pdf.table_row(["first_name", "string", "Read-only"], wf)
    pdf.table_row(["last_name", "string | null", "Read-only"], wf)
    pdf.table_row(["email", "string (email)", "Read-only"], wf)
    pdf.table_row(["phone", "string | null", "Editable"], wf)
    pdf.table_row(["phone_code", "string | null", "Editable (e.g. +91)"], wf)
    pdf.table_row(["address", "object", "{ line, city, state } - editable"], wf)
    pdf.table_row(["date_of_birth", "string | null", "YYYY-MM-DD, editable"], wf)
    pdf.table_row(["gender", "number | null", "1-4, see Gender codes"], wf)
    pdf.table_row(["emergency_contact", "object", "{ name, phone } - editable"], wf)
    pdf.table_row(["department", "object | null", "{ id, name } - admin-owned, read-only"], wf)
    pdf.table_row(["role", "object | null", "{ id, name } - read-only"], wf)
    pdf.table_row(["qualification", "string | null", "Editable"], wf)
    pdf.table_row(["license_number", "string | null", "Admin-owned, read-only"], wf)
    pdf.table_row(["employee_id", "string | null", "Admin-owned, read-only"], wf)
    pdf.table_row(["experience_years", "number | null", "Editable, 0-60"], wf)
    pdf.table_row(["joining_date", "string | null", "Admin-owned, read-only"], wf)
    pdf.table_row(["bio", "string | null", "Editable"], wf)
    pdf.table_row(["languages", "string[]", "Editable, default []"], wf)
    pdf.table_row(["shift", "object | null", "{ name, start_time, end_time } - admin-owned"], wf)
    pdf.table_row(["profile_image_url", "string | null", "Relative path under /uploads"], wf)
    pdf.table_row(["is_profile_completed", "boolean", "Server-computed (see rules below)"], wf)
    pdf.table_row(["profile_completion_percentage", "number", "0-100, 14 field checks"], wf)
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
    pdf.bullet("403 - Missing permission, inactive account, or role is not nurse")
    pdf.bullet("404 - User/profile not found (\"Nurse profile not found. Contact admin.\")")

    # ---------------------------------------------------------
    pdf.sub_title("2.3 PUT /nurse/profile")
    pdf.body(
        "Content-Type: application/json. Schema: NurseProfileUpdate with extra=\"forbid\". "
        "Partial updates are allowed. Empty body / no fields => 400 \"No fields to update\". "
        "Unknown or admin-only fields => 422."
    )
    pdf.code_block(
        """{
  "qualification": "BSc Nursing, Critical Care Cert",
  "experience_years": 6,
  "bio": "Ward nurse with focus on postop care.",
  "languages": ["English", "Hindi"],
  "phone": "9876543210",
  "phone_code": "+91",
  "address": {
    "line": "12 Ward Road",
    "city": "Pune",
    "state": "Maharashtra"
  },
  "date_of_birth": "1992-06-15",
  "gender": 2,
  "emergency_contact": {
    "name": "Rahul Sharma",
    "phone": "9123456780"
  }
}"""
    )

    pdf.sub_title("Editable vs read-only")
    we = [55, 40, 75]
    pdf.table_row(["Field", "Nurse can edit?", "UI tip"], we, bold=True)
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
    pdf.table_row(["license_number", "No", "Admin-owned"], we)
    pdf.table_row(["employee_id", "No", "Admin-owned"], we)
    pdf.table_row(["joining_date", "No", "Admin-owned"], we)
    pdf.table_row(["department / role", "No", "Display only"], we)
    pdf.table_row(["shift", "No", "Admin updates; nurse gets SHIFT_UPDATED notification"], we)
    pdf.table_row(["profile_image_url", "No in PUT", "Use image upload/delete endpoints"], we)

    pdf.body(
        "Do NOT send name, email, license_number, employee_id, joining_date, "
        "department, role, shift, profile_image_url, is_profile_completed, or "
        "profile_completion_percentage in PUT."
    )
    pdf.body("Success response: full NurseProfileResponse (same shape as GET).")

    # ---------------------------------------------------------
    pdf.sub_title("2.4 POST /nurse/profile/image")
    pdf.body("multipart/form-data. Field name: file (required).")
    pdf.bullet("Allowed: .jpg .jpeg .png .webp")
    pdf.bullet("Max size: 5 MB")
    pdf.bullet("Empty file rejected")
    pdf.bullet("Stores under uploads/nurse_image/ (or NURSE_PROFILE_UPLOAD_DIR)")
    pdf.bullet("Replaces previous image file on success")
    pdf.code_block(
        """{
  "message": "Profile image uploaded successfully",
  "profile_image_url": "/uploads/nurse_image/<uuid>.jpg"
}"""
    )
    pdf.body(
        "Display image as: API_BASE + profile_image_url "
        "(e.g. http://localhost:8000/uploads/nurse_image/...)."
    )

    pdf.sub_title("2.5 DELETE /nurse/profile/image")
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
    pdf.section_title("3. Module B - Nurse Notifications")
    pdf.body(
        "Prefix: /nurse/notifications  |  Router: Routers/nurse_notification_router.py  |  "
        "Tag: Nurse Notifications"
    )
    pdf.body(
        "Uses the shared notifications table, filtered by the logged-in nurse user_id. "
        "Same schema as doctor notifications, different URL prefix and trigger set."
    )

    pdf.sub_title("3.1 Endpoint summary")
    w = [58, 18, 48, 46]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], w, bold=True)
    pdf.table_row(
        ["GET /nurse/notifications/unread-count", "200", "notifications:view", "Badge count"],
        w,
    )
    pdf.table_row(
        ["GET /nurse/notifications", "200", "notifications:view", "Paginated list"],
        w,
    )
    pdf.table_row(
        ["PATCH /nurse/notifications/{id}/read", "200", "notifications:update", "Mark one read"],
        w,
    )
    pdf.table_row(
        ["PATCH /nurse/notifications/read-all", "200", "notifications:update", "Mark all read"],
        w,
    )

    # ---------------------------------------------------------
    pdf.sub_title("3.2 GET /nurse/notifications/unread-count")
    pdf.code_block('{ "count": 3 }')
    pdf.body(
        "Poll every 15-30 seconds for the header badge. No WebSocket/SSE in backend yet."
    )

    # ---------------------------------------------------------
    pdf.sub_title("3.3 GET /nurse/notifications")
    pdf.body("Query parameters:")
    wq = [40, 35, 95]
    pdf.table_row(["Param", "Type / rules", "Purpose"], wq, bold=True)
    pdf.table_row(["page", "int >= 1, default 1", "Page number"], wq)
    pdf.table_row(["limit", "int 1-100, default 20", "Page size"], wq)
    pdf.table_row(["search", "string min 1", "ILIKE title, message, created_by_name"], wq)
    pdf.table_row(["is_read", "bool optional", "Filter unread/read"], wq)
    pdf.table_row(["source_module", "enum optional", "e.g. NURSE, ADMIN"], wq)
    pdf.table_row(["notification_type", "enum optional", "e.g. EMERGENCY_ALERT"], wq)
    pdf.table_row(["start_date / end_date", "date optional", "Inclusive Asia/Kolkata"], wq)

    pdf.body(
        "Sort order: priority CRITICAL then HIGH then NORMAL, then created_at DESC "
        "(newest first within priority)."
    )
    pdf.code_block(
        """GET /nurse/notifications?page=1&limit=20&is_read=false

{
  "total": 3,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": 501,
      "user_id": 21,
      "title": "Handover taken over",
      "message": "Anita Patel took over your handover HO-2026-0012.",
      "notification_type": "HANDOVER_TAKEN_OVER",
      "priority": "HIGH",
      "source_module": "NURSE",
      "reference_type": "HANDOVER",
      "reference_id": 88,
      "created_by": 22,
      "created_by_name": "Anita Patel",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-07-14T09:15:00+05:30"
    }
  ]
}"""
    )

    pdf.body("NotificationResponse fields:")
    wn = [42, 42, 86]
    pdf.table_row(["Field", "Type", "Notes"], wn, bold=True)
    pdf.table_row(["id", "number", "Notification id"], wn)
    pdf.table_row(["user_id", "number", "Recipient nurse"], wn)
    pdf.table_row(["title", "string", "Short headline"], wn)
    pdf.table_row(["message", "string | null", "Body text"], wn)
    pdf.table_row(["notification_type", "enum string", "See type table"], wn)
    pdf.table_row(["priority", "NORMAL|HIGH|CRITICAL", "UI badge styling"], wn)
    pdf.table_row(["source_module", "enum string", "Which module created it"], wn)
    pdf.table_row(["reference_type", "enum string", "Deep-link entity type"], wn)
    pdf.table_row(["reference_id", "number", "Deep-link entity id"], wn)
    pdf.table_row(["created_by", "number | null", "Actor user id"], wn)
    pdf.table_row(["created_by_name", "string | null", "Actor display name"], wn)
    pdf.table_row(["is_read", "boolean", "Read flag"], wn)
    pdf.table_row(["read_at", "datetime | null", "Set when marked read"], wn)
    pdf.table_row(["created_at", "datetime", "ISO with timezone"], wn)

    # ---------------------------------------------------------
    pdf.sub_title("3.4 PATCH /nurse/notifications/{notification_id}/read")
    pdf.body(
        "Marks one notification as read for the current nurse. Idempotent "
        "(already-read returns success). Sets is_read=true and read_at=now(IST). "
        "404 if notification does not belong to this nurse."
    )
    pdf.body("Response: full NotificationResponse.")

    pdf.sub_title("3.5 PATCH /nurse/notifications/read-all")
    pdf.code_block('{ "message": "All notifications marked as read" }')
    pdf.body("Marks every unread notification for this nurse as read.")

    # =========================================================
    pdf.section_title("4. Nurse notification types (what you will actually receive)")
    pdf.body(
        "The shared NotificationType enum has many values (including doctor appointment/lab types). "
        "Nurses typically only receive the types below. Filter UI and deep-links around these."
    )

    wt = [42, 22, 28, 28, 50]
    pdf.table_row(
        ["notification_type", "priority", "source", "reference", "When created"],
        wt,
        bold=True,
    )
    pdf.table_row(
        [
            "EMERGENCY_ALERT",
            "by severity",
            "NURSE",
            "ALERT",
            "Alert assigned to nurse, or auto HIGH/CRITICAL alert notifies triggering nurse",
        ],
        wt,
    )
    pdf.table_row(
        [
            "HANDOVER_TAKEN_OVER",
            "HIGH",
            "NURSE",
            "HANDOVER",
            "Another nurse takes over your submitted handover",
        ],
        wt,
    )
    pdf.table_row(
        [
            "SHIFT_UPDATED",
            "HIGH",
            "ADMIN",
            "SCHEDULE",
            "Admin changes shift name / start / end on nurse profile",
        ],
        wt,
    )
    pdf.table_row(
        [
            "ADMIN_UPDATE",
            "HIGH",
            "ADMIN",
            "USER",
            "Admin changes department, deactivates, or deletes nurse account",
        ],
        wt,
    )

    pdf.sub_title("Deep-link suggestions")
    pdf.bullet("reference_type = ALERT + reference_id -> emergency alert detail screen")
    pdf.bullet("reference_type = HANDOVER + reference_id -> handover detail / take-over screen")
    pdf.bullet("reference_type = SCHEDULE -> open profile shift section (read-only)")
    pdf.bullet("reference_type = USER (ADMIN_UPDATE) -> show notice; may force logout if deactivated")

    pdf.sub_title("Enums (full, for filter dropdowns)")
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

interface NurseProfile {
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
  qualification?: string | null;
  license_number?: string | null;
  employee_id?: string | null;
  experience_years?: number | null;
  joining_date?: string | null;
  bio?: string | null;
  languages: string[];
  shift?: {
    name?: string | null;
    start_time?: string | null;
    end_time?: string | null;
  } | null;
  profile_image_url?: string | null;
  is_profile_completed: boolean;
  profile_completion_percentage: number;
  is_active: boolean;
  last_login?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface NurseProfileUpdate {
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

interface NurseNotification {
  id: number;
  user_id: number;
  title: string;
  message?: string | null;
  notification_type: string;
  priority: "NORMAL" | "HIGH" | "CRITICAL";
  source_module: string;
  reference_type: string;
  reference_id: number;
  created_by?: number | null;
  created_by_name?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}"""
    )

    # =========================================================
    pdf.section_title("6. Frontend implementation checklist")
    pdf.sub_title("Profile")
    pdf.bullet("[ ] Load GET /nurse/profile on Profile page mount")
    pdf.bullet("[ ] Render nested address / emergency_contact / department / shift")
    pdf.bullet("[ ] Disable admin-owned fields (registration, employee_id, joining, dept, shift)")
    pdf.bullet("[ ] PUT only editable fields; reject extra keys (extra=forbid)")
    pdf.bullet("[ ] Show completion % progress + is_profile_completed banner")
    pdf.bullet("[ ] Map gender int 1-4 to UI labels")
    pdf.bullet("[ ] Image upload via multipart field `file`; preview with API_BASE + url")
    pdf.bullet("[ ] Delete image updates UI to null avatar")

    pdf.sub_title("Notifications")
    pdf.bullet("[ ] Poll GET /nurse/notifications/unread-count for header badge")
    pdf.bullet("[ ] Inbox: list with page/limit; tabs or filter for is_read")
    pdf.bullet("[ ] Style CRITICAL / HIGH / NORMAL differently")
    pdf.bullet("[ ] Click item -> PATCH .../read then deep-link by reference_type")
    pdf.bullet("[ ] Mark all read button -> PATCH .../read-all then refresh count")
    pdf.bullet("[ ] Handle EMERGENCY_ALERT, HANDOVER_TAKEN_OVER, SHIFT_UPDATED, ADMIN_UPDATE")
    pdf.bullet("[ ] After admin deactivate/delete notice, force re-auth if 401/403")

    pdf.sub_title("Common")
    pdf.bullet("[ ] Always send Authorization: Bearer <token>")
    pdf.bullet("[ ] Handle 401 (login), 403 (permission/role), 404, 422 validation")
    pdf.bullet("[ ] Re-login after seed if nurse_profile:* or notifications:* missing in JWT")

    # =========================================================
    pdf.section_title("7. Quick reference - base URLs")
    pdf.code_block(
        """Profile:
  GET    /nurse/profile
  PUT    /nurse/profile
  POST   /nurse/profile/image     (multipart file)
  DELETE /nurse/profile/image

Notifications:
  GET    /nurse/notifications/unread-count
  GET    /nurse/notifications
  PATCH  /nurse/notifications/{notification_id}/read
  PATCH  /nurse/notifications/read-all

Static files:
  GET    /uploads/nurse_image/<filename>
"""
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        5,
        "Generated from HM-System-Backend Docs/generate_nurse_profile_notification_pdf.py. "
        "Aligned with Routers/nurse_profile_router.py and Routers/nurse_notification_router.py "
        "(July 2026).",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
