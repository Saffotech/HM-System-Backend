"""Generator: Doctor Profile & Notifications - Frontend Developer Documentation PDF."""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "doctor-profile-notifications-frontend-guide.pdf"


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(
            0,
            8,
            "SaffoCare HMS - Doctor Profile & Notifications Frontend Guide",
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
            # Wrap long lines for code blocks
            while len(line) > 95:
                self.cell(usable, 4.5, "  " + line[:95], new_x="LMARGIN", new_y="NEXT", fill=True)
                line = line[95:]
            self.cell(usable, 4.5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table_row(self, cols: list[str], widths: list[float] | None = None, bold: bool = False):
        usable = self.w - self.l_margin - self.r_margin
        if widths is None:
            widths = [usable / len(cols)] * len(cols)
        self.set_font("Helvetica", "B" if bold else "", 8)
        # Check page break for multi-line-ish rows
        if self.get_y() > self.h - 25:
            self.add_page()
        x_start = self.l_margin
        y_start = self.get_y()
        row_h = 6
        max_h = row_h
        # Measure wrapped height
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
    pdf.multi_cell(0, 11, "Doctor Profile & Notifications\nFrontend Developer Guide")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        6,
        "Version: 1.0  |  Date: July 2026  |  Audience: Frontend developers\n"
        "Backend: HM-System (FastAPI)  |  Auth: JWT Bearer token\n"
        "Modules: /doctor/profile  +  /doctor/notifications",
    )
    pdf.ln(4)

    # =========================================================
    pdf.section_title("1. Purpose & Scope")
    pdf.body(
        "This document describes the Doctor Profile and Doctor Notifications APIs so frontend "
        "developers can implement the doctor UI correctly. Both modules are fully implemented "
        "on the backend. Use this guide as the source of truth for endpoints, payloads, "
        "validation, permissions, and UI behaviour."
    )

    pdf.sub_title("What this covers")
    pdf.bullet("Doctor self-service profile: view, update, upload/delete profile image")
    pdf.bullet("Which fields doctors can edit vs which are admin-only (read-only in UI)")
    pdf.bullet("Profile completion rules and image upload constraints")
    pdf.bullet("In-app doctor notifications: list, unread badge, mark one/all as read")
    pdf.bullet("Notification types, priorities, filters, and deep-link hints")
    pdf.bullet("Suggested TypeScript types and frontend implementation checklist")

    pdf.sub_title("What this does NOT cover")
    pdf.bullet("Admin staff APIs (/users) except where they own doctor fields")
    pdf.bullet("Push notifications, WebSocket, or SSE (not implemented - use polling)")
    pdf.bullet("Delete notification or notification preferences (not implemented)")

    pdf.sub_title("Auth header (all endpoints)")
    pdf.code_block("Authorization: Bearer <access_token>")
    pdf.body(
        "Login via POST /auth/login. JWT must include the required permission. "
        "Inactive accounts receive 403. Soft-deleted / missing users receive 404."
    )

    # =========================================================
    pdf.section_title("2. Module A - Doctor Profile")
    pdf.body(
        "Prefix: /doctor  |  Router: Routers/doctor_profile_router.py  |  "
        "Tag: Doctor Profile"
    )
    pdf.body(
        "Only users with role name \"doctor\" can use these endpoints. Admins manage "
        "license, fee, specialization, and department via /users - not via /doctor/profile."
    )

    pdf.sub_title("2.1 Endpoint summary")
    w = [38, 22, 55, 55]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], w, bold=True)
    pdf.table_row(["GET /doctor/profile", "200", "doctor_profile:view", "Load full profile"], w)
    pdf.table_row(["PUT /doctor/profile", "200", "doctor_profile:update", "Update editable fields"], w)
    pdf.table_row(["POST /doctor/profile/image", "200", "doctor_profile:upload_image", "Upload avatar"], w)
    pdf.table_row(["DELETE /doctor/profile/image", "200", "doctor_profile:delete_image", "Remove avatar"], w)

    # ---------------------------------------------------------
    pdf.sub_title("2.2 GET /doctor/profile")
    pdf.body("Request body: none. Returns DoctorProfileResponse.")
    pdf.code_block(
        """{
  "user_id": 12,
  "first_name": "Asha",
  "last_name": "Mehta",
  "email": "asha.mehta@hospital.com",
  "phone": "9876543210",
  "address": "12 MG Road",
  "city": "Pune",
  "state": "Maharashtra",
  "date_of_birth": "1985-04-12",
  "gender": 2,
  "emergency_contact_phone": "9123456780",
  "is_active": true,
  "department": "Cardiology",
  "specialization": "Interventional Cardiology",
  "qualification": "MD, DM Cardiology",
  "medical_license_number": "MH-MED-12345",
  "experience_years": 12,
  "consultation_fee": 800.0,
  "bio": "Consultant cardiologist with 12 years experience.",
  "languages": ["English", "Hindi", "Marathi"],
  "profile_image_url": "/uploads/doctor_image/a1b2c3d4.jpg",
  "is_profile_completed": true
}"""
    )

    pdf.body("Response field reference:")
    wf = [48, 35, 87]
    pdf.table_row(["Field", "Type", "Notes"], wf, bold=True)
    pdf.table_row(["user_id", "number", "Doctor user id"], wf)
    pdf.table_row(["first_name", "string", "Read-only for doctor"], wf)
    pdf.table_row(["last_name", "string | null", "Read-only for doctor"], wf)
    pdf.table_row(["email", "string (email)", "Read-only for doctor"], wf)
    pdf.table_row(["phone", "string | null", "Editable"], wf)
    pdf.table_row(["address", "string | null", "Editable"], wf)
    pdf.table_row(["city", "string | null", "Editable"], wf)
    pdf.table_row(["state", "string | null", "Editable"], wf)
    pdf.table_row(["date_of_birth", "string | null", "YYYY-MM-DD, editable"], wf)
    pdf.table_row(["gender", "number | null", "1-4, see Gender codes"], wf)
    pdf.table_row(["emergency_contact_phone", "string | null", "Editable"], wf)
    pdf.table_row(["is_active", "boolean", "Account status"], wf)
    pdf.table_row(["department", "string | null", "Dept NAME (not id). Read-only"], wf)
    pdf.table_row(["specialization", "string | null", "Admin-owned. Read-only"], wf)
    pdf.table_row(["qualification", "string | null", "Editable"], wf)
    pdf.table_row(["medical_license_number", "string | null", "Admin-owned. Read-only"], wf)
    pdf.table_row(["experience_years", "number | null", "Editable, 0-60"], wf)
    pdf.table_row(["consultation_fee", "number | null", "Admin-owned. Read-only"], wf)
    pdf.table_row(["bio", "string | null", "Editable"], wf)
    pdf.table_row(["languages", "string[]", "Editable, default []"], wf)
    pdf.table_row(["profile_image_url", "string | null", "Relative path under /uploads"], wf)
    pdf.table_row(["is_profile_completed", "boolean", "Computed server-side"], wf)

    pdf.sub_title("Gender codes (integer, not label)")
    pdf.bullet("1 = Male")
    pdf.bullet("2 = Female")
    pdf.bullet("3 = Other")
    pdf.bullet("4 = Prefer not to say")
    pdf.body("API returns the integer. Frontend should map to labels in the UI.")

    pdf.sub_title("Errors")
    pdf.bullet("401 - Missing/invalid JWT")
    pdf.bullet("403 - Missing permission, inactive account, or role is not doctor")
    pdf.bullet("404 - User/profile not found (\"Doctor profile not found. Contact admin.\")")

    # ---------------------------------------------------------
    pdf.sub_title("2.3 PUT /doctor/profile")
    pdf.body(
        "Content-Type: application/json. Schema: DoctorProfileUpdate with extra=\"forbid\". "
        "Unknown/admin-only fields cause 422. At least one field is required; empty body -> 400."
    )
    pdf.body("All fields optional; send only what changed:")
    pdf.code_block(
        """{
  "qualification": "MD, DM Cardiology",
  "experience_years": 12,
  "bio": "Consultant cardiologist...",
  "languages": ["English", "Hindi", "Marathi"],
  "phone": "9876543210",
  "address": "12 MG Road",
  "city": "Pune",
  "state": "Maharashtra",
  "date_of_birth": "1985-04-12",
  "gender": 2,
  "emergency_contact_phone": "9123456780"
}"""
    )

    pdf.body("Validation rules:")
    pdf.bullet("qualification: max 255 chars")
    pdf.bullet("experience_years: integer, >= 0 and <= 60")
    pdf.bullet("phone / emergency_contact_phone: max 20 chars")
    pdf.bullet("city / state: max 100 chars")
    pdf.bullet("gender: integer 1-4")
    pdf.bullet("languages: trimmed; empties dropped; case-insensitive dedupe")
    pdf.bullet(
        "Do NOT send: first_name, last_name, email, department, specialization, "
        "medical_license_number, consultation_fee, profile_image_url, is_profile_completed"
    )

    pdf.body("Response: same DoctorProfileResponse as GET. Side effect: is_profile_completed recomputed.")

    pdf.sub_title("Profile completion rule")
    pdf.body(
        "is_profile_completed is true only when ALL of these are set: "
        "qualification (truthy), experience_years (not null - 0 counts), bio (truthy). "
        "Image, languages, phone, license, and fee are NOT required for completion."
    )

    pdf.sub_title("UI field ownership (important)")
    pdf.bullet("EDITABLE by doctor: qualification, experience_years, bio, languages, phone, address, city, state, date_of_birth, gender, emergency_contact_phone, profile image")
    pdf.bullet("READ-ONLY display: first_name, last_name, email, department, specialization, medical_license_number, consultation_fee, is_active, is_profile_completed")
    pdf.bullet("Show a short note that license / fee / specialization / department are managed by admin")

    # ---------------------------------------------------------
    pdf.sub_title("2.4 POST /doctor/profile/image")
    pdf.body("Content-Type: multipart/form-data. Field name MUST be: file")
    pdf.bullet("Allowed extensions: .jpg, .jpeg, .png, .webp")
    pdf.bullet("Max size: 5 MB")
    pdf.bullet("Empty file rejected")
    pdf.bullet("Replaces previous image (old file deleted on server)")
    pdf.bullet("Image upload does NOT affect is_profile_completed")

    pdf.code_block(
        """// Example (fetch)
const form = new FormData();
form.append("file", selectedFile);
await fetch(`${API_BASE}/doctor/profile/image`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },
  body: form
});

// Success response
{
  "message": "Profile image uploaded successfully",
  "profile_image_url": "/uploads/doctor_image/<uuid>.jpg"
}"""
    )
    pdf.body(
        "Display the image as: {API_BASE}{profile_image_url} "
        "e.g. http://localhost:8000/uploads/doctor_image/....jpg "
        "(static files are mounted at /uploads)."
    )
    pdf.bullet("400 - Missing filename, wrong type, empty, > 5 MB, invalid path")
    pdf.bullet("404 - Profile not found")
    pdf.bullet("500 - Failed to save file")

    # ---------------------------------------------------------
    pdf.sub_title("2.5 DELETE /doctor/profile/image")
    pdf.body("Request body: none.")
    pdf.code_block(
        """{
  "message": "Profile image deleted successfully",
  "profile_image_url": null
}"""
    )
    pdf.bullet("404 - \"No profile image to delete\" or profile missing")

    # ---------------------------------------------------------
    pdf.sub_title("2.6 Suggested Profile UI screens")
    pdf.bullet("Profile Overview: avatar, name, department, specialization, fee (read-only), completion badge")
    pdf.bullet("Edit Professional: qualification, experience_years, bio, languages (tag input)")
    pdf.bullet("Edit Contact: phone, address, city, state, DOB, gender select, emergency phone")
    pdf.bullet("Avatar: crop/preview optional; enforce type + 5 MB client-side before upload")
    pdf.bullet("On load: GET profile once; show spinner; if 404 show \"Contact admin\"")
    pdf.bullet("On save: PUT only dirty fields; refresh form from response")
    pdf.bullet("Show incomplete banner when is_profile_completed === false")

    pdf.sub_title("2.7 TypeScript types (Profile)")
    pdf.code_block(
        """export type GenderCode = 1 | 2 | 3 | 4;

export interface DoctorProfile {
  user_id: number;
  first_name: string;
  last_name: string | null;
  email: string;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  date_of_birth: string | null; // YYYY-MM-DD
  gender: GenderCode | null;
  emergency_contact_phone: string | null;
  is_active: boolean;
  department: string | null;
  specialization: string | null;
  qualification: string | null;
  medical_license_number: string | null;
  experience_years: number | null;
  consultation_fee: number | null;
  bio: string | null;
  languages: string[];
  profile_image_url: string | null;
  is_profile_completed: boolean;
}

export interface DoctorProfileUpdate {
  qualification?: string | null;
  experience_years?: number | null; // 0-60
  bio?: string | null;
  languages?: string[] | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  date_of_birth?: string | null;
  gender?: GenderCode | null;
  emergency_contact_phone?: string | null;
}

export interface DoctorProfileImageResponse {
  message: string;
  profile_image_url: string | null;
}"""
    )

    # =========================================================
    pdf.add_page()
    pdf.section_title("3. Module B - Doctor Notifications")
    pdf.body(
        "Prefix: /doctor/notifications  |  Router: Routers/doctor_notification_router.py  |  "
        "Tag: Doctor Notifications"
    )
    pdf.body(
        "In-app notifications for the logged-in doctor only (scoped by user_id). "
        "There is no WebSocket/SSE/push - poll unread-count for the nav badge. "
        "Doctors cannot create notifications; they are produced by OPD, Lab, Nurse, Admin flows."
    )

    pdf.sub_title("3.1 Endpoint summary")
    wn = [52, 22, 50, 46]
    pdf.table_row(["Method + Path", "Status", "Permission", "Purpose"], wn, bold=True)
    pdf.table_row(["GET /doctor/notifications", "200", "notifications:view", "Paginated list + filters"], wn)
    pdf.table_row(["GET .../unread-count", "200", "notifications:view", "Badge count"], wn)
    pdf.table_row(["PATCH .../{id}/read", "200", "notifications:update", "Mark one as read"], wn)
    pdf.table_row(["PATCH .../read-all", "200", "notifications:update", "Mark all as read"], wn)

    pdf.sub_title("Not implemented (do not build UI for these yet)")
    pdf.bullet("Delete notification")
    pdf.bullet("Preferences / mute / channels")
    pdf.bullet("Push (FCM/APNs) or real-time WebSocket/SSE")
    pdf.bullet("Doctor-facing create API")

    # ---------------------------------------------------------
    pdf.sub_title("3.2 GET /doctor/notifications")
    pdf.body("Query parameters:")
    wq = [40, 35, 95]
    pdf.table_row(["Param", "Type", "Rules"], wq, bold=True)
    pdf.table_row(["page", "int", ">= 1, default 1"], wq)
    pdf.table_row(["limit", "int", "1-100, default 20"], wq)
    pdf.table_row(["search", "string", "min length 1; ILIKE on title, message, created_by_name"], wq)
    pdf.table_row(["is_read", "bool", "Optional filter true/false"], wq)
    pdf.table_row(["source_module", "enum", "See SourceModule"], wq)
    pdf.table_row(["notification_type", "enum", "See NotificationType"], wq)
    pdf.table_row(["start_date", "date", "YYYY-MM-DD, inclusive (Asia/Kolkata)"], wq)
    pdf.table_row(["end_date", "date", "YYYY-MM-DD, inclusive (Asia/Kolkata)"], wq)

    pdf.body("Sort order: priority CRITICAL > HIGH > NORMAL, then created_at descending.")
    pdf.code_block(
        """GET /doctor/notifications?page=1&limit=20&is_read=false

{
  "total": 42,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": 101,
      "user_id": 12,
      "title": "Lab Report Ready",
      "message": "CBC - Ramesh Patil",
      "notification_type": "LAB_REPORT_READY",
      "priority": "HIGH",
      "source_module": "LAB",
      "reference_type": "LAB_ORDER",
      "reference_id": 55,
      "created_by": 8,
      "created_by_name": "Lab Tech One",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-07-13T09:15:00+05:30"
    }
  ]
}"""
    )

    pdf.body("NotificationResponse fields:")
    wr = [45, 40, 85]
    pdf.table_row(["Field", "Type", "Notes"], wr, bold=True)
    pdf.table_row(["id", "number", "Primary key"], wr)
    pdf.table_row(["user_id", "number", "Recipient doctor user id"], wr)
    pdf.table_row(["title", "string", "Max 255"], wr)
    pdf.table_row(["message", "string | null", "May contain \\n - render multiline"], wr)
    pdf.table_row(["notification_type", "enum string", "See types table"], wr)
    pdf.table_row(["priority", "enum string", "NORMAL | HIGH | CRITICAL"], wr)
    pdf.table_row(["source_module", "enum string", "Producer module"], wr)
    pdf.table_row(["reference_type", "enum string", "Deep-link entity type"], wr)
    pdf.table_row(["reference_id", "number", "Deep-link entity id"], wr)
    pdf.table_row(["created_by", "number | null", "Actor user id"], wr)
    pdf.table_row(["created_by_name", "string | null", "Display name snapshot"], wr)
    pdf.table_row(["is_read", "boolean", ""], wr)
    pdf.table_row(["read_at", "datetime | null", "ISO-8601 with timezone"], wr)
    pdf.table_row(["created_at", "datetime", "ISO-8601 with timezone"], wr)

    # ---------------------------------------------------------
    pdf.sub_title("3.3 GET /doctor/notifications/unread-count")
    pdf.code_block('{ "count": 5 }')
    pdf.body(
        "Use for the nav bell badge. Poll every 15-30 seconds (or on focus/visibility change). "
        "No real-time channel exists."
    )

    # ---------------------------------------------------------
    pdf.sub_title("3.4 PATCH /doctor/notifications/{notification_id}/read")
    pdf.body("Body: none. Returns full NotificationResponse. Idempotent if already read.")
    pdf.bullet("Sets is_read=true and read_at=now (Asia/Kolkata) on first mark")
    pdf.bullet("404 - \"Notification not found\" (wrong id or not owned by current user)")

    # ---------------------------------------------------------
    pdf.sub_title("3.5 PATCH /doctor/notifications/read-all")
    pdf.body("Body: none.")
    pdf.code_block('{ "message": "All notifications marked as read" }')
    pdf.body("After success, set local unread count to 0 and refresh the list if open.")

    # ---------------------------------------------------------
    pdf.sub_title("3.6 Enums")
    pdf.body("NotificationPriority: NORMAL | HIGH | CRITICAL")
    pdf.body("Default priority by type:")
    pdf.bullet("NEW_APPOINTMENT -> NORMAL")
    pdf.bullet("LAB_REPORT_READY, APPOINTMENT_CANCELLED, APPOINTMENT_RESCHEDULED, ADMIN_UPDATE -> HIGH")
    pdf.bullet("EMERGENCY_ALERT -> CRITICAL")

    pdf.body("NotificationType (values that currently appear in data):")
    wt = [48, 122]
    pdf.table_row(["Type", "When created"], wt, bold=True)
    pdf.table_row(["NEW_APPOINTMENT", "Paid patient added to doctor queue (check-in)"], wt)
    pdf.table_row(["APPOINTMENT_CANCELLED", "Appointment cancelled AND visit paid"], wt)
    pdf.table_row(["APPOINTMENT_RESCHEDULED", "scheduled_at changed, not cancelled, paid"], wt)
    pdf.table_row(["LAB_REPORT_READY", "Lab report uploaded / first file report created"], wt)
    pdf.table_row(["EMERGENCY_ALERT", "Critical auto-alert or nurse escalate"], wt)
    pdf.table_row(["ADMIN_UPDATE", "Admin dept change / deactivate / delete doctor"], wt)

    pdf.body("Reserved enum values (exist but not produced yet - may use in filters/UI labels):")
    pdf.bullet("PATIENT_CHECKED_IN, LAB_REPORT_UPDATED, PRESCRIPTION_CREATED, PRESCRIPTION_UPDATED")

    pdf.body("SourceModule: OPD_BILLING | LAB | NURSE | ADMIN (active). Reserved: RECEPTIONIST, PHARMACY, SYSTEM")
    pdf.body("ReferenceType (deep-link):")
    pdf.bullet("APPOINTMENT + reference_id -> appointment / queue / calendar screen")
    pdf.bullet("LAB_ORDER + reference_id -> lab order detail")
    pdf.bullet("PATIENT + reference_id -> patient chart / emergency context")
    pdf.bullet("USER + reference_id -> profile / account notice (admin updates)")
    pdf.bullet("Reserved: PRESCRIPTION, BILL, SCHEDULE, LEAVE")

    # ---------------------------------------------------------
    pdf.sub_title("3.7 Notification trigger details (for UI copy)")
    pdf.bullet("NEW_APPOINTMENT title: \"Paid Appointment Confirmed\" - patient, time, token")
    pdf.bullet("APPOINTMENT_CANCELLED title: \"Appointment Cancelled\" - patient + time")
    pdf.bullet("APPOINTMENT_RESCHEDULED title: \"Appointment Rescheduled\" - patient + new time")
    pdf.bullet("LAB_REPORT_READY title: \"Lab Report Ready\" - \"{test} - {patient}\"")
    pdf.bullet("EMERGENCY_ALERT - priority CRITICAL; reference PATIENT")
    pdf.bullet("ADMIN_UPDATE - e.g. \"Department reassigned\", \"Account disabled by admin\"")
    pdf.bullet("Unpaid appointments do NOT notify on cancel/reschedule")
    pdf.bullet("Replacing an existing lab file report does NOT create another notification")

    # ---------------------------------------------------------
    pdf.sub_title("3.8 Suggested Notifications UI")
    pdf.bullet("Nav: bell icon + unread badge from unread-count (poll)")
    pdf.bullet("Inbox list: title, message (multiline), priority chip, type, relative time, unread style")
    pdf.bullet("Filters: Unread / All, type chips, date range, search box")
    pdf.bullet("Actions: click row -> mark read + navigate via reference_type/reference_id")
    pdf.bullet("Toolbar: \"Mark all as read\"")
    pdf.bullet("Empty state when total === 0")
    pdf.bullet("Visual priority: CRITICAL red, HIGH amber, NORMAL default")
    pdf.bullet("Do not invent delete/archive/preferences UI until backend supports it")

    pdf.sub_title("3.9 TypeScript types (Notifications)")
    pdf.code_block(
        """export type NotificationPriority = "NORMAL" | "HIGH" | "CRITICAL";

export type NotificationType =
  | "NEW_APPOINTMENT"
  | "APPOINTMENT_CANCELLED"
  | "APPOINTMENT_RESCHEDULED"
  | "PATIENT_CHECKED_IN"
  | "LAB_REPORT_READY"
  | "LAB_REPORT_UPDATED"
  | "PRESCRIPTION_CREATED"
  | "PRESCRIPTION_UPDATED"
  | "EMERGENCY_ALERT"
  | "ADMIN_UPDATE";

export type SourceModule =
  | "OPD_BILLING" | "LAB" | "RECEPTIONIST" | "NURSE"
  | "PHARMACY" | "ADMIN" | "SYSTEM";

export type ReferenceType =
  | "APPOINTMENT" | "LAB_ORDER" | "PRESCRIPTION" | "BILL"
  | "PATIENT" | "USER" | "SCHEDULE" | "LEAVE";

export interface Notification {
  id: number;
  user_id: number;
  title: string;
  message: string | null;
  notification_type: NotificationType;
  priority: NotificationPriority;
  source_module: SourceModule;
  reference_type: ReferenceType;
  reference_id: number;
  created_by: number | null;
  created_by_name: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  total: number;
  page: number;
  limit: number;
  items: Notification[];
}

export interface UnreadCountResponse {
  count: number;
}"""
    )

    # =========================================================
    pdf.add_page()
    pdf.section_title("4. Error Handling Cheat Sheet")
    we = [22, 148]
    pdf.table_row(["HTTP", "When / Frontend action"], we, bold=True)
    pdf.table_row(["400", "Empty profile PUT; bad image upload - show field/toast message from detail"], we)
    pdf.table_row(["401", "Redirect to login; clear token"], we)
    pdf.table_row(["403", "Permission denied / inactive / not doctor - show access denied"], we)
    pdf.table_row(["404", "Profile missing (contact admin); notification not found; no image"], we)
    pdf.table_row(["422", "Validation failed / forbidden extra fields - show field errors"], we)
    pdf.table_row(["500", "Image save failure - retry later"], we)

    pdf.body(
        "FastAPI usually returns { \"detail\": \"...\" } or a validation array for 422. "
        "Surface detail in toasts; map 422 to form fields when possible."
    )

    # =========================================================
    pdf.section_title("5. Frontend Implementation Checklist")
    pdf.sub_title("Profile")
    pdf.bullet("[ ] Route/page: Doctor Profile under authenticated doctor layout")
    pdf.bullet("[ ] GET /doctor/profile on mount")
    pdf.bullet("[ ] Separate editable vs read-only sections visually")
    pdf.bullet("[ ] Gender select mapped to 1-4")
    pdf.bullet("[ ] Languages as chip/tag input")
    pdf.bullet("[ ] PUT with only changed fields; handle 400/422")
    pdf.bullet("[ ] Avatar upload via FormData field \"file\"; preview + 5 MB client check")
    pdf.bullet("[ ] Avatar delete + clear preview")
    pdf.bullet("[ ] Show is_profile_completed banner / CTA until true")
    pdf.bullet("[ ] Image URL = API_BASE + profile_image_url")

    pdf.sub_title("Notifications")
    pdf.bullet("[ ] Bell in doctor header with unread badge")
    pdf.bullet("[ ] Poll GET /doctor/notifications/unread-count (15-30s)")
    pdf.bullet("[ ] Notifications page/drawer with pagination")
    pdf.bullet("[ ] Filters: is_read, notification_type, date range, search")
    pdf.bullet("[ ] Mark one read on open; Mark all read button")
    pdf.bullet("[ ] Deep-link by reference_type + reference_id")
    pdf.bullet("[ ] Render message with line breaks; priority colours")
    pdf.bullet("[ ] Optimistic unread decrement after mark-read")

    # =========================================================
    pdf.section_title("6. Permissions Required (Doctor role)")
    pdf.bullet("doctor_profile:view")
    pdf.bullet("doctor_profile:update")
    pdf.bullet("doctor_profile:upload_image")
    pdf.bullet("doctor_profile:delete_image")
    pdf.bullet("notifications:view")
    pdf.bullet("notifications:update")
    pdf.body(
        "These are seeded for the doctor role. Permissions are embedded in the JWT at login. "
        "Gate UI routes/buttons on permissions if your app checks them client-side."
    )

    # =========================================================
    pdf.section_title("7. Quick API Reference")
    pdf.code_block(
        """# Profile
GET    /doctor/profile
PUT    /doctor/profile
POST   /doctor/profile/image          (multipart: file)
DELETE /doctor/profile/image

# Notifications
GET    /doctor/notifications
GET    /doctor/notifications/unread-count
PATCH  /doctor/notifications/{id}/read
PATCH  /doctor/notifications/read-all

# Auth
Authorization: Bearer <token>
OpenAPI: /docs when backend is running"""
    )

    # =========================================================
    pdf.section_title("8. Source Files (Backend)")
    pdf.bullet("Routers/doctor_profile_router.py")
    pdf.bullet("Schemas/doctor_profile_schema.py")
    pdf.bullet("Services/doctor_profile_service.py")
    pdf.bullet("Models/doctor_profile.py")
    pdf.bullet("Routers/doctor_notification_router.py")
    pdf.bullet("Schemas/notification_schema.py")
    pdf.bullet("Enums/notification.py")
    pdf.bullet("Models/notification.py")
    pdf.bullet("Services/notification_service.py")
    pdf.bullet("seed.py (permissions)")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        5,
        "End of document. For live schema details, run the backend and open /docs "
        "(Hospital Management API). Keep this PDF next to frontend tickets for Profile "
        "and Notifications implementation.",
    )

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build_pdf()
