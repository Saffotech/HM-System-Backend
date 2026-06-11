# Nurse Module — Frontend Functional Specification

**Document scope:** Nurse role only, based on implemented backend APIs in `HM-System`  
**API base:** `http://127.0.0.1:8000` (or Vite proxy `/api`)  
**Auth:** JWT Bearer — default expiry **30 minutes** (no refresh token endpoint)  
**Role name from API:** `nurse`  
**Folder:** `src/pages/nurse/`  
**URL prefix:** `/nurse/`

**Implemented nurse API prefixes:**
- `/auth` (shared login)
- `/nurse/queue/today`
- `/nurse/vitals`
- `/nurse/notes`
- `/nurse/medications`
- `/nurse/handover`

**Not implemented (excluded from spec):** `/nurse/alerts`, nurse dashboard stats API, assigned-patients API, patient profile API, notifications API

**Backend docs:** [../../backend/roles/nurse/nurse.md](../../backend/roles/nurse/nurse.md)

---

# 1. Project Overview

## What type of application

Hospital Management System (HMS) — **Nurse Clinical Operations Portal** (web SPA). A staff-facing internal tool for day-to-day nursing workflows in OPD/IPD context.

## Main business purpose

Enable nurses to:

1. View today's patient queue
2. Record and review patient vitals
3. Document nursing observations
4. Administer prescribed medications (bedded patients)
5. Complete shift handover summaries

## Key user groups

| User group | Access |
|------------|--------|
| **Nurse** | Primary user — full nurse module |
| **Admin** | Can log in but nurse UI should only render for `role === "nurse"` |
| Other roles (doctor, opd_billing, pharmacist) | Must **not** see nurse module routes (route guard by role) |

---

# 2. User Roles

## 2.1 Nurse (`nurse`)

| Attribute | Detail |
|-----------|--------|
| **Role name (API)** | `nurse` |
| **Responsibilities** | Queue monitoring, vitals, nursing notes, medication administration, shift handover |
| **Seed permissions** | `patients:view`, `opd:view`, `lab:view` |
| **API enforcement** | Nurse endpoints use `get_current_user` (JWT valid). **PermissionChecker is NOT applied** on nurse routers today |

### Allowed screens

- Login
- Nurse Dashboard
- Today's Queue
- Vitals (create, edit, view, search)
- Nursing Notes (create, edit, view, search)
- Medication Administration (patients, administer, history)
- Shift Handover (create, edit, submit, list, detail/print)
- My Profile (read-only via `/auth/me`)

### Allowed actions

| Action | API support |
|--------|-------------|
| View today's queue | Yes |
| Search/filter queue | Yes |
| Record vitals (once per appointment) | Yes |
| Update existing vitals | Yes |
| Search vitals history | Yes |
| Create/update nursing notes | Yes |
| Search nursing notes | Yes |
| List medication patients | Yes |
| View patient prescriptions | Yes |
| Administer/update medication records | Yes |
| View medication history | Yes |
| Create handover draft | Yes |
| Bulk add handover patients | Yes |
| Update/delete handover patient rows | Yes (own draft only) |
| Submit handover | Yes (own draft, min 1 patient) |
| List/view handovers | Yes |

### Restricted actions

| Action | Reason |
|--------|--------|
| Patient registration / billing | No nurse billing APIs |
| Write prescriptions | Doctor module only |
| Order lab tests | Doctor module only |
| OPD queue management | OPD billing module |
| Edit submitted handover | API returns 400 |
| Modify another nurse's handover | API returns 403 |
| Record duplicate vitals for same appointment | API returns 400 |
| Emergency alerts / escalate to doctor | **No API** |
| Export CSV/PDF | **No API** (client-side only if built) |

## 2.2 Other roles (nurse module context)

| Role | Nurse module access |
|------|---------------------|
| admin | Block by default |
| doctor | No |
| opd_billing | No |
| pharmacist | No |
| lab_technician | Not in seed — No |

---

# 3. Application Modules

| Module | API prefix | Status |
|--------|------------|--------|
| Authentication | `/auth` | Ready |
| Nurse Dashboard | `/nurse/queue/today` | Partial (no dedicated stats API) |
| Queue Management | `/nurse/queue/today` | Ready |
| Vitals Management | `/nurse/vitals` | Ready |
| Nursing Notes | `/nurse/notes` | Ready |
| Medication Administration | `/nurse/medications` | Ready |
| Shift Handover | `/nurse/handover` | Ready |

**Excluded** (no API): Emergency Alerts, Notifications Center, Admission/Discharge Support, Reports, Administration

---

# 4. Screen Inventory

## Module: Authentication

### Screen: Staff Login

| Field | Value |
|-------|-------|
| **Purpose** | Authenticate nurse and obtain JWT |
| **Route** | `/login` |
| **Roles** | All staff (nurse uses same login) |
| **APIs** | `POST /auth/login` |
| **Actions** | Submit credentials, show errors, redirect to `/nurse/dashboard` if `role === "nurse"` |

---

## Module: Nurse Dashboard

### Screen: Nurse Dashboard

| Field | Value |
|-------|-------|
| **Purpose** | Landing page with queue summary and quick actions |
| **Route** | `/nurse/dashboard` |
| **Roles** | `nurse` |
| **APIs** | `GET /nurse/queue/today`, `GET /auth/me` |
| **Actions** | View KPI cards, view recent queue slice, quick navigate |

---

## Module: Queue

### Screen: Today's Queue

| Field | Value |
|-------|-------|
| **Purpose** | Master list of today's patients for nursing actions |
| **Route** | `/nurse/queue` |
| **Roles** | `nurse` |
| **APIs** | `GET /nurse/queue/today` |
| **Actions** | Search, filter by status/doctor/priority, paginate, navigate to vitals/notes |

### Screen: Patient Context (Drawer)

| Field | Value |
|-------|-------|
| **Purpose** | Show queue row details before action |
| **Route** | `/nurse/queue` (overlay) |
| **Roles** | `nurse` |
| **APIs** | Data from selected queue row |
| **Actions** | Record vitals, add note, open patient overview |

---

## Module: Patient Context (Composite)

### Screen: Patient Nursing Overview

| Field | Value |
|-------|-------|
| **Purpose** | Unified view of one patient's nursing data |
| **Route** | `/nurse/patients/:patientId` |
| **Roles** | `nurse` |
| **APIs** | `GET /nurse/vitals/search?patient_id=`, `GET /nurse/notes/search?patient_id=`, `GET /nurse/medications/patient/:id`, `GET /nurse/medications/history/:id` |
| **Actions** | View timelines, jump to create vitals/note/medication |

> **Assumption:** Frontend composes this from multiple APIs. No `GET /nurse/patients/:id` exists.

---

## Module: Vitals

### Screen: Record Vitals

| Route | `/nurse/vitals/new?appointmentId=:id` |
| **APIs** | `POST /nurse/vitals` |
| **Actions** | Fill form, submit, handle duplicate error |

### Screen: Edit Vitals

| Route | `/nurse/vitals/:vitalId/edit` |
| **APIs** | `GET /nurse/vitals/:vitalId`, `PUT /nurse/vitals/:vitalId` |

### Screen: Vital Detail

| Route | `/nurse/vitals/:vitalId` |
| **APIs** | `GET /nurse/vitals/:vitalId` |

### Screen: Vitals Search / Registry

| Route | `/nurse/vitals` |
| **APIs** | `GET /nurse/vitals/search`, `GET /nurse/vitals` |

### Screen: Patient Vitals Timeline

| Route | `/nurse/patients/:patientId/vitals` |
| **APIs** | `GET /nurse/vitals/search?patient_id=` |

---

## Module: Nursing Notes

### Screen: Create Nursing Note

| Route | `/nurse/notes/new?appointmentId=:id` |
| **APIs** | `POST /nurse/notes` |

### Screen: Edit Nursing Note

| Route | `/nurse/notes/:noteId/edit` |
| **APIs** | `GET /nurse/notes/:noteId`, `PUT /nurse/notes/:noteId` |

### Screen: Nursing Note Detail

| Route | `/nurse/notes/:noteId` |
| **APIs** | `GET /nurse/notes/:noteId` |

### Screen: Notes Search / Registry

| Route | `/nurse/notes` |
| **APIs** | `GET /nurse/notes/search`, `GET /nurse/notes` |

### Screen: Patient Notes Timeline

| Route | `/nurse/patients/:patientId/notes` |
| **APIs** | `GET /nurse/notes/search?patient_id=` |

---

## Module: Medication Administration

### Screen: Medication Patients List

| Route | `/nurse/medications` |
| **APIs** | `GET /nurse/medications/patients` |

### Screen: Patient Medication Administration

| Route | `/nurse/medications/patient/:patientId` |
| **APIs** | `GET /nurse/medications/patient/:patientId`, `POST /nurse/medications/administer`, `PUT /nurse/medications/administer/:id` |

### Screen: Medication History (Global)

| Route | `/nurse/medications/history` |
| **APIs** | `GET /nurse/medications/history` |

### Screen: Patient Medication History

| Route | `/nurse/medications/history/:patientId` |
| **APIs** | `GET /nurse/medications/history/:patientId` |

---

## Module: Shift Handover

### Screen: Handover List

| Route | `/nurse/handover` |
| **APIs** | `GET /nurse/handover` |

### Screen: Create / Edit Handover (Wizard)

| Route | `/nurse/handover/new`, `/nurse/handover/:id/edit` |
| **APIs** | `POST /nurse/handover`, `PUT /nurse/handover/:id`, `POST /nurse/handover/:id/patients/bulk`, `PUT /nurse/handover/patients/:summaryId`, `DELETE /nurse/handover/patients/:summaryId`, `PUT /nurse/handover/:id/submit` |

### Screen: Handover Detail / Print

| Route | `/nurse/handover/:id` |
| **APIs** | `GET /nurse/handover/:id` |

---

## Module: Profile

### Screen: My Profile

| Route | `/nurse/profile` |
| **APIs** | `GET /auth/me` |
| **Actions** | View only |

---

# 5. Detailed Screen Design Requirements

## 5.1 Nurse Dashboard (`/nurse/dashboard`)

**Header:** App logo + "Nurse Portal", logged-in name, shift date, Sign out

**Breadcrumb:** `Dashboard`

**KPI cards (computed client-side from queue API):**

| Card | API call |
|------|----------|
| Total in queue | `GET /nurse/queue/today` → `total` |
| Waiting for vitals | `?status=waiting` |
| Vitals completed | `?status=vitals_completed` |
| Emergency priority | `?priority=emergency` |
| In consultation | `?status=in_consultation` |

**Recent queue table (top 5–10):** Token, Patient Name, UHID, Phone, Doctor ID, Priority, Status, Actions

**Quick actions:** View Full Queue, Record Vitals, Medications, New Handover

**Empty state:** "No patients in queue today" + Refresh

**Loading:** Skeleton cards + table rows

**Error:** Toast with API `detail` + Retry

---

## 5.2 Today's Queue (`/nurse/queue`)

**Search:** Debounced 400ms → `search` param (name, UHID, phone, token, patient ID)

**Filters:**

| Filter | API param | Values |
|--------|-----------|--------|
| Status | `status` | `waiting`, `vitals_completed`, `in_consultation`, `completed`, `cancelled` |
| Priority | `priority` | `normal`, `urgent`, `emergency` |
| Doctor | `doctor_id` | integer |

**Table columns:** Token, Patient, UHID, Phone, Appointment UID, Doctor ID, Priority (badge), Status (badge), Actions

**Row actions:**
- View patient → `/nurse/patients/:patientId`
- Record vitals → `/nurse/vitals/new?appointmentId=:id`
- Add note → `/nurse/notes/new?appointmentId=:id`
- Vitals history → `/nurse/patients/:patientId/vitals`

**Pagination:** `page`, `page_size` (max 100)

---

## 5.3 Record Vitals (`/nurse/vitals/new`)

**Breadcrumb:** `Dashboard > Queue > Record Vitals`

**Buttons:** Save Vitals (primary), Cancel

**Error mapping:**

| API detail | UI message |
|------------|------------|
| Appointment not found | "Invalid appointment. Return to queue." |
| Vitals already recorded for this appointment | "Vitals already recorded. Open edit instead." |

**Success:** Toast "Vitals recorded successfully" → redirect queue or patient vitals timeline

---

## 5.4 Medication Patients (`/nurse/medications`)

**Filters:** `patient_name`, `patient_uid`, `bed_number`, `patient_id`

**Table:** Patient, UHID, Bed, Ward, Medicine Count, Administer action

**Empty state:** "No patients with active prescriptions on occupied beds"

---

## 5.5 Patient Medication Administration

**Per-medicine actions:** Mark Given / Missed / Refused / Delayed with confirmation dialog

**Administer body:** `prescription_item_id`, `status`, `remarks`, `scheduled_time` (optional)

---

## 5.6 Handover Wizard

**Step 1:** ward_name*, department_id, shift_date, shift_start, shift_end, general_notes → `POST /nurse/handover`

**Step 2:** Bulk patient summaries → `POST /nurse/handover/:id/patients/bulk`, edit `PUT`, delete `DELETE`

**Step 3:** Review → `PUT /nurse/handover/:id/submit`

**Locked when submitted:** Read-only, hide edit/delete/submit

---

# 6. Navigation Structure

```
Nurse Portal
├── Dashboard                          /nurse/dashboard
├── Today's Queue                      /nurse/queue
├── Vitals
│   ├── All Vitals                     /nurse/vitals
│   └── Patient Vitals                 /nurse/patients/:id/vitals
├── Nursing Notes
│   ├── All Notes                      /nurse/notes
│   └── Patient Notes                  /nurse/patients/:id/notes
├── Medications
│   ├── Patients                       /nurse/medications
│   ├── Administer                     /nurse/medications/patient/:id
│   └── History                        /nurse/medications/history
├── Shift Handover
│   ├── Handover List                  /nurse/handover
│   ├── Create Handover                /nurse/handover/new
│   └── Handover Detail                /nurse/handover/:id
└── My Profile                         /nurse/profile

(Auth)
└── Login                              /login
```

---

# 7. Dashboard Design

| Widget | API |
|--------|-----|
| Total Queue | `GET /nurse/queue/today` → `total` |
| Waiting | `?status=waiting` |
| Vitals Done | `?status=vitals_completed` |
| In Consultation | `?status=in_consultation` |
| Emergency Cases (red) | `?priority=emergency` |
| Recent Queue Table | `?page=1&page_size=10` |

**Do NOT build without API:** medication task count, critical alerts, activity feed, charts, shift timing from server

**Quick actions:** Open Queue, Vitals (waiting), Medications, New Handover

---

# 8. Forms Specification

## Login (`POST /auth/login`)

| Field | Type | Required |
|-------|------|----------|
| email | email | Yes |
| password | password | Yes |

## Record Vitals (`POST /nurse/vitals`)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| appointment_id | hidden | **Yes** | From `?appointmentId=` |
| temperature | number | No | e.g. 98.6 |
| blood_pressure | text | No | e.g. 120/80 |
| heart_rate | number | No | BPM |
| respiratory_rate | number | No | |
| oxygen_saturation | number | No | 0–100 |
| blood_sugar | number | No | |
| weight | number | No | |
| pain_level | number/slider | No | 1–10 |
| observation_notes | textarea | No | |

> API sets `status = "recorded"` automatically. Queue status updates `waiting` → `vitals_completed` on create.

## Create Nursing Note (`POST /nurse/notes`)

| Field | Type | Required |
|-------|------|----------|
| appointment_id | hidden | **Yes** |
| symptoms | textarea | No |
| treatment_response | textarea | No |
| additional_notes | textarea | No |

## Administer Medication (`POST /nurse/medications/administer`)

| Field | Type | Required | Values |
|-------|------|----------|--------|
| prescription_item_id | hidden | **Yes** | From med list `id` |
| status | select | **Yes** | `given`, `refused`, `missed`, `delayed` |
| remarks | textarea | No | |
| scheduled_time | datetime | No | |

## Create Handover (`POST /nurse/handover`)

| Field | Type | Required |
|-------|------|----------|
| ward_name | text | **Yes** (2–150 chars) |
| department_id | select | No |
| shift_date | date | No (default today) |
| shift_start | time | No |
| shift_end | time | No |
| general_notes | textarea | No |

## Handover Patient Row (bulk)

| Field | Type | Required |
|-------|------|----------|
| patient_id | number | **Yes** |
| patient_summary | textarea | No |
| pending_tasks | textarea | No |
| critical_alerts | textarea | No |
| medication_pending | textarea | No |
| doctor_instructions | textarea | No |

`patient_name`, `bed_number` auto-filled by backend.

---

# 9. Tables Specification

## Today's Queue

| Column | Filter |
|--------|--------|
| Token | search |
| Patient Name | search |
| UHID | search |
| Phone | search |
| Priority | priority dropdown |
| Status | status dropdown |
| Doctor | doctor_id |

Pagination: server `page`, `page_size`. No bulk actions.

## Vitals Search

Filters: `patient_id`, `appointment_id`, `name`, `phone`, `uhid`, `status`, `recorded_by`, `from_date`, `to_date`, `page`, `page_size`

## Nursing Notes Search

Filters: `patient_id`, `appointment_id`, `name`, `phone`, `uhid`, `status`, `nurse_id`, `from_date`, `to_date`

## Medication History

Filters: `patient_id`, `patient_name`, `patient_uid`, `bed_number`, `status`, `from_date`, `to_date`

Status: `given`, `refused`, `missed`, `delayed`

## Handover List

Filters: `handover_uid`, `patient_id`, `patient_name`, `status`, `ward_name`, `shift_date`, `outgoing_nurse_id`

Response: `total_records`, `page`, `limit`, `data[]`

---

# 10. API Mapping

| Screen | Action | Endpoint | Method |
|--------|--------|----------|--------|
| Login | Sign in | `/auth/login` | POST |
| Profile | Load user | `/auth/me` | GET |
| Dashboard | Queue stats | `/nurse/queue/today` | GET |
| Queue | List/search | `/nurse/queue/today` | GET |
| Vitals | Create | `/nurse/vitals` | POST |
| Vitals | Update | `/nurse/vitals/{vital_id}` | PUT |
| Vitals | Get one | `/nurse/vitals/{vital_id}` | GET |
| Vitals | List all | `/nurse/vitals` | GET |
| Vitals | Search | `/nurse/vitals/search` | GET |
| Notes | Create | `/nurse/notes` | POST |
| Notes | Update | `/nurse/notes/{note_id}` | PUT |
| Notes | Get one | `/nurse/notes/{note_id}` | GET |
| Notes | List all | `/nurse/notes` | GET |
| Notes | Search | `/nurse/notes/search` | GET |
| Medications | Patient list | `/nurse/medications/patients` | GET |
| Medications | Patient meds | `/nurse/medications/patient/{patient_id}` | GET |
| Medications | Administer | `/nurse/medications/administer` | POST |
| Medications | Update | `/nurse/medications/administer/{administration_id}` | PUT |
| Medications | Global history | `/nurse/medications/history` | GET |
| Medications | Patient history | `/nurse/medications/history/{patient_id}` | GET |
| Handover | Create | `/nurse/handover` | POST |
| Handover | Update | `/nurse/handover/{handover_id}` | PUT |
| Handover | Bulk patients | `/nurse/handover/{handover_id}/patients/bulk` | POST |
| Handover | Update patient row | `/nurse/handover/patients/{patient_summary_id}` | PUT |
| Handover | Delete patient row | `/nurse/handover/patients/{patient_summary_id}` | DELETE |
| Handover | Submit | `/nurse/handover/{handover_id}/submit` | PUT |
| Handover | List | `/nurse/handover` | GET |
| Handover | Detail | `/nurse/handover/{handover_id}` | GET |

---

# 11. Authentication Flow

## Login

1. Open `/login`
2. `POST /auth/login` with email + password
3. Store: `access_token`, `role`, `permissions`, `user_id`, `first_name`
4. If `role === "nurse"` → `/nurse/dashboard`
5. Else → unauthorized message or redirect to correct role dashboard

## Logout

1. Clear auth storage
2. Redirect `/login`
3. No backend logout endpoint

## Token handling

```http
Authorization: Bearer <access_token>
```

Default expiry: **30 minutes**. No refresh token — re-login on 401.

## Unauthorized

- **401** → clear token → `/login?reason=session_expired`
- **403** → toast with `detail`
- Route guard: block `/nurse/*` if `role !== "nurse"`

---

# 12. Role Based Access Control

| Feature | Nurse | Doctor | OPD Billing | Pharmacist | Admin |
|---------|:-----:|:------:|:-----------:|:----------:|:-----:|
| Nurse Dashboard | ✅ | — | — | — | — |
| Today's Queue | ✅ | — | — | — | — |
| Vitals | ✅ | — | — | — | — |
| Nursing Notes | ✅ | — | — | — | — |
| Medications | ✅ | — | — | — | — |
| Shift Handover | ✅ | — | — | — | — |

Frontend enforces `role === "nurse"`. Backend mostly checks JWT only.

---

# 13. Notifications

## Success toasts

| Action | Message |
|--------|---------|
| Login | "Welcome, {first_name}" |
| Vitals saved | "Vitals recorded successfully" |
| Note saved | "Nursing note saved" |
| Medication | "Medication marked as {status}" |
| Handover submitted | "Handover submitted successfully" |

## Error toasts

- Show API `detail` when present
- Fallback: "Something went wrong. Please try again."
- Network: "Unable to reach server."

## Confirmation dialogs

| Action | Message |
|--------|---------|
| Administer medication | "Confirm {medicine} as {status}?" |
| Submit handover | "Submit handover? Cannot edit after submission." |
| Delete handover row | "Remove this patient from handover?" |
| Sign out | "Sign out of Nurse Portal?" |

---

# 14. Frontend Architecture Recommendation

```
src/
├── pages/nurse/
│   ├── NurseLayout.tsx
│   ├── NurseRoutes.tsx
│   ├── DashboardPage.tsx
│   ├── QueuePage.tsx
│   ├── PatientOverviewPage.tsx
│   ├── vitals/
│   ├── notes/
│   ├── medications/
│   └── handover/
├── services/
│   ├── apiClient.ts
│   └── nurseService.ts
├── hooks/
│   ├── useAuth.ts
│   └── useNurseQueue.ts
├── components/
│   ├── layout/ Sidebar, TopBar, Breadcrumb
│   ├── data/ DataTable, Pagination, EmptyState
│   └── nurse/ PriorityBadge, StatusBadge
└── routes/ProtectedRoute.tsx
```

**State:** React Query for server data, React Hook Form + Zod for forms, Context/Zustand for auth.

---

# 15. UI/UX Recommendations

- **Layout:** Fixed sidebar (240px) + top bar (56px)
- **Priority badges:** emergency=red, urgent=orange, normal=gray
- **Queue rows:** red left border for `priority=emergency`
- **Forms:** two-column desktop, single column mobile
- **Mobile:** Queue, Vitals, Medications must work on tablet
- **Accessibility:** labels on all inputs, keyboard nav, `aria-live` for toasts

---

# 16. User Workflows

## WF-01: Login → Dashboard

```
/login → POST /auth/login → store token → /nurse/dashboard → GET /nurse/queue/today
```

## WF-02: Record Vitals

```
/nurse/queue → select row → /nurse/vitals/new?appointmentId={id}
→ POST /nurse/vitals → queue status becomes vitals_completed → back to queue
```

## WF-03: Nursing Note

```
queue → /nurse/notes/new?appointmentId={id} → POST /nurse/notes → /nurse/patients/{id}/notes
```

## WF-04: Administer Medication

```
/nurse/medications → GET patients → select patient → GET patient meds
→ confirm → POST /administer { prescription_item_id, status: "given" }
```

## WF-05: Shift Handover

```
/nurse/handover/new → POST header → POST bulk patients → PUT submit → GET detail (print)
```

## WF-06: Patient Overview

```
/nurse/patients/{id} → parallel: vitals/search, notes/search, medications/patient, medications/history
```

---

# 17. Missing Requirements

## Missing APIs

| Feature | Status |
|---------|--------|
| Emergency alerts | ❌ |
| Nurse dashboard stats | ❌ (compute client-side) |
| Single patient profile | ❌ (compose from multiple APIs) |
| Doctor name in queue | ❌ (only `doctor_id`) |
| Handover acknowledge / incoming nurse | ❌ |
| Notify doctor | ❌ |
| Refresh token | ❌ |
| Export PDF/CSV | ❌ |

## Ambiguous / gaps

- Queue router docs say `in_progress` but model uses `in_consultation` — use **`in_consultation`**
- `GET /nurse/handover` list may lack auth on backend — still send token from frontend
- Medication patients returns **array** not paginated wrapper
- Vitals require **`appointment_id`** not `patient_id` on create

## Important rule

**Do NOT use** `GET /opd/queue/today` for nurse — use **`GET /nurse/queue/today`**

---

# 18. Final Deliverables

## Complete Screen List (22 screens)

| # | Screen | Route |
|---|--------|-------|
| 1 | Login | `/login` |
| 2 | Nurse Dashboard | `/nurse/dashboard` |
| 3 | Today's Queue | `/nurse/queue` |
| 4 | Patient Overview | `/nurse/patients/:patientId` |
| 5 | Record Vitals | `/nurse/vitals/new` |
| 6 | Edit Vitals | `/nurse/vitals/:vitalId/edit` |
| 7 | Vital Detail | `/nurse/vitals/:vitalId` |
| 8 | Vitals Registry | `/nurse/vitals` |
| 9 | Patient Vitals Timeline | `/nurse/patients/:patientId/vitals` |
| 10 | Create Note | `/nurse/notes/new` |
| 11 | Edit Note | `/nurse/notes/:noteId/edit` |
| 12 | Note Detail | `/nurse/notes/:noteId` |
| 13 | Notes Registry | `/nurse/notes` |
| 14 | Patient Notes Timeline | `/nurse/patients/:patientId/notes` |
| 15 | Medication Patients | `/nurse/medications` |
| 16 | Administer Medications | `/nurse/medications/patient/:patientId` |
| 17 | Medication History | `/nurse/medications/history` |
| 18 | Patient Med History | `/nurse/medications/history/:patientId` |
| 19 | Handover List | `/nurse/handover` |
| 20 | Handover Wizard | `/nurse/handover/new` |
| 21 | Handover Detail/Print | `/nurse/handover/:id` |
| 22 | My Profile | `/nurse/profile` |

## Development Roadmap

| Phase | Week | Deliverables |
|-------|------|--------------|
| P0 | 1 | Auth, layout, route guards, apiClient, nurseService |
| P1 | 2 | Dashboard + Queue |
| P2 | 3 | Vitals create/edit/search |
| P3 | 4 | Nursing notes |
| P4 | 5 | Patient overview (composite) |
| P5 | 6 | Medications + history |
| P6 | 7 | Shift handover wizard |
| P7 | 8 | Profile, polish, QA |
| P8 | Future | Emergency alerts (when API ready) |

## Suggested files

```
pages/nurse/
├── NurseRoutes.tsx
├── NurseLayout.tsx
├── DashboardPage.tsx
├── QueuePage.tsx
├── PatientOverviewPage.tsx
├── vitals/VitalsFormPage.tsx
├── notes/NursingNoteFormPage.tsx
├── medications/MedicationPatientsPage.tsx
├── medications/MedicationAdminPage.tsx
└── handover/HandoverWizardPage.tsx
```

---

**Document status:** Ready for frontend implementation  
**Interactive API docs:** `http://127.0.0.1:8000/docs`
