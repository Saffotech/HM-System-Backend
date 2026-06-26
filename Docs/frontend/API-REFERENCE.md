# HMS API Reference (Frontend Integration)

Complete endpoint list for the Hospital Management System backend. Use this document to integrate React (or any client) with the API.

**Interactive docs (when backend is running):** `http://127.0.0.1:8000/docs`

---

## Base URL

| Environment | URL |
|-------------|-----|
| Local (direct) | `http://127.0.0.1:8000` |
| Local (Vite proxy) | `/api` → proxied to backend (see `hms-frontend/vite.config.ts`) |

All paths below are relative to the base URL (e.g. `POST /auth/login` → `http://127.0.0.1:8000/auth/login`).

---

## Authentication

### How to call protected APIs

1. `POST /auth/login` with email + password.
2. Store `access_token` from the response.
3. Send on every protected request:

```http
Authorization: Bearer <access_token>
```

### Login response (use for routing & UI)

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "opd_billing",
  "permissions": ["patients:view", "opd:view", "billing:view", ...],
  "first_name": "Ravi",
  "user_id": 3
}
```

- **Route by `role`:** `admin`, `doctor`, `nurse`, `opd_billing`, `receptionist`, `pharmacist`
- **Show/hide buttons by `permissions`:** e.g. only show "Register Patient" if `patients:create` is in the array
- **Re-login required** after backend permission changes in the database

### Common HTTP status codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 400 | Validation / business rule error (`detail` in body) |
| 401 | Missing or invalid token |
| 403 | No permission or account deactivated |
| 404 | Resource not found |
| 409 | Conflict (duplicate email, phone, patient, etc.) |

Error body shape (FastAPI):

```json
{ "detail": "Human-readable message" }
```

---

## Route prefixes (important)

Doctor and OPD both use **appointments**, but different URLs:

| Module | Prefix | Who uses it |
|--------|--------|-------------|
| OPD front desk | `/opd/...` | `opd_billing` — billing visits: `GET /opd/visits/today` |
| Reception / queue | `/receptionist/...` | `receptionist` — clinical queue: `GET /receptionist/doctor-queue/{id}` |
| Doctor clinical | `/appointments`, `/queue`, `/patients`, `/prescriptions`, `/lab-tests` | `doctor` |

Do not mix them up. OPD books at `POST /opd/appointments`; doctor reads at `GET /appointments/today`.

---

# 1. Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register staff user |
| POST | `/auth/login` | No | Login, get JWT |
| GET | `/auth/me` | Yes | Current user profile |

### POST `/auth/register`

**Body**

```json
{
  "first_name": "Amit",
  "last_name": "Kumar",
  "email": "doctor@hospital.com",
  "password": "password123",
  "role_id": 2,
  "department_id": 1
}
```

**Response 201**

```json
{
  "message": "Staff registered successfully",
  "user_id": 5,
  "email": "doctor@hospital.com",
  "role": "doctor"
}
```

### POST `/auth/login`

**Body**

```json
{
  "email": "billing@hospital.com",
  "password": "password123"
}
```

**Response 200** — see [Login response](#authentication) above.

### GET `/auth/me`

**Response 200**

```json
{
  "user_id": 3,
  "email": "billing@hospital.com",
  "first_name": "Ravi",
  "last_name": "Singh",
  "role": "opd_billing",
  "role_id": 4,
  "is_active": true,
  "created_at": "2026-05-21 ..."
}
```

---

# 2. Roles (`/roles`)

Mostly **admin** setup. `GET /roles/` has no permission check (public list).

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/roles/` | None | List roles + permission names |
| POST | `/roles/` | `roles:create` | Create role |
| POST | `/roles/permissions` | `roles:create` | Create permission |
| POST | `/roles/{role_id}/permissions` | `roles:create` | Assign permissions to role |

### POST `/roles/{role_id}/permissions`

**Body**

```json
{
  "permission_ids": [1, 2, 5, 8]
}
```

---

# 3. OPD & Billing (`/opd`)

**Role:** `opd_billing` (and admin with full permissions).

### 3.1 Dashboard & lookup

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/opd/dashboard` | `opd:view` | Stats cards + recent visits |
| GET | `/opd/patient/search?phone=` | `patients:view` | Search by phone |
| GET | `/opd/patients?search=&page=&limit=` | `patients:view` | Patient list |
| GET | `/opd/patient/{id}` | `patients:view` | Single patient |
| GET | `/opd/patient/{id}/profile` | `patients:view` | Profile + visits + billing summary |
| PUT | `/opd/patient/{id}` | `patients:update` | Update patient |
| DELETE | `/opd/patient/{id}` | `patients:delete` | Soft-delete patient |
| GET | `/opd/departments` | `opd:view` | Active departments |
| GET | `/opd/doctors/department/{department_id}` | `opd:view` | Doctors in department |

#### GET `/opd/patient/search?phone=9567154627`

**Found**

```json
{
  "found": true,
  "patient_id": 1,
  "patient_uid": "P-1001",
  "name": "Amaresh Maurya",
  "phone": "9567154627",
  "blood_group": "O+",
  "gender": "Male",
  "aadhaar": null
}
```

**Not found**

```json
{
  "found": false,
  "message": "New patient. Please register."
}
```

#### GET `/opd/dashboard`

```json
{
  "visits_today": 12,
  "patients_total": 340,
  "pending_bills": 5,
  "appointments_today": 8,
  "beds_free": 4,
  "beds_total": 8,
  "recent_visits": [ /* QueueVisitItem[] max 5 */ ]
}
```

### 3.2 Billing & registration

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/opd/bill/preview` | `billing:view` | Preview fees only |
| POST | `/opd/patient/preview-bill` | `billing:view` | Same preview (full register body) |
| POST | `/opd/patient/register` | `patients:create` | New patient + visit + bill |
| POST | `/opd/visit` | `opd:create` | Existing patient new visit |
| POST | `/opd/bill/generate` | `billing:create` | Bill with extra line items |
| GET | `/opd/visit/{visit_id}/invoice` | `billing:view` | Printable invoice |
| GET | `/opd/bills` | `billing:view` | Bill list + KPIs |
| POST | `/opd/visit/{visit_id}/pay` | `billing:update` | Collect payment |
| GET | `/opd/payments/history` | `billing:view` | Payment ledger |
| GET | `/opd/visits/today` | `opd:view` | **Today's billing visits** (`opd_visits` — not clinical queue) |
| GET | `/opd/queue/today` | `opd:view` | **Deprecated** — same as `/opd/visits/today` |

#### GET `/opd/visits/today`

Billing counter list for today. **Not** the receptionist/doctor clinical queue.

```json
{
  "source": "opd_visits",
  "description": "Registered OPD visits and bills for today. This is NOT the clinical waiting-room queue...",
  "total": 12,
  "visits": [
    {
      "visit_id": 1,
      "token_number": "OPD-20260623-001",
      "bill_number": "BILL-001",
      "payment_status": "paid",
      "grand_total": 1050.0
    }
  ]
}
```

See [Queue endpoints guide](../flows/queue-endpoints-guide.md) for `/receptionist/*` vs `/opd/visits/today`.

#### POST `/opd/patient/register`

**Query params**

| Param | Default | Description |
|-------|---------|-------------|
| `payment_mode` | `cash` | `cash` \| `card` \| `upi` \| `insurance` |
| `pay_later` | `false` | If true, no payment recorded |
| `amount_received` | null | Partial pay amount (optional) |

**Body** — patient fields + billing fields:

```json
{
  "first_name": "Amaresh",
  "last_name": "Maurya",
  "phone": "9567154627",
  "gender": 1,
  "date_of_birth": "1990-05-15",
  "department_id": 1,
  "doctor_id": 2,
  "registration_fee": 200,
  "consultation_fee": 800,
  "gst_percent": 5
}
```

**Gender codes:** `1` Male, `2` Female, `3` Other, `4` Prefer not to say

**Response 201**

```json
{
  "message": "Patient registered successfully",
  "patient_id": "P-1001",
  "bill_number": "BILL-001",
  "token_number": "OPD-20260602-001",
  "visit_id": 1
}
```

#### POST `/opd/visit`

**Query:** same as register (`payment_mode`, `pay_later`, `amount_received`)

**Body**

```json
{
  "patient_id": 1,
  "department_id": 1,
  "doctor_id": 2,
  "registration_fee": 0,
  "consultation_fee": 800,
  "gst_percent": 5,
  "waive_registration_fee": true
}
```

**Response 201**

```json
{
  "message": "OPD visit created successfully",
  "patient_id": "P-1001",
  "bill_number": "BILL-002",
  "token_number": "OPD-20260602-002",
  "visit_id": 2,
  "grand_total": 840,
  "payment_status": "paid"
}
```

#### POST `/opd/visit/{visit_id}/pay`

**Body**

```json
{
  "payment_mode": "upi",
  "paid_amount": 500,
  "transaction_reference": "TXN123456"
}
```

`transaction_reference` is **required** for `card` and `upi`.

#### GET `/opd/bills`

**Query**

| Param | Description |
|-------|-------------|
| `status` | `paid` \| `partial` \| `pending` |
| `search` | Patient name, UID, bill or token |
| `today_only` | boolean |
| `from_date`, `to_date` | ISO datetime |
| `page`, `limit` | Pagination |

**Response** includes `summary` (total_billed, total_collected, total_outstanding, collection_rate_percent) and `bills[]`.

### 3.3 OPD appointments (front desk booking)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/opd/appointments` | `appointments:create` | Book appointment |
| GET | `/opd/appointments` | `appointments:view` | List appointments |
| PATCH | `/opd/appointments/{id}` | `appointments:update` | Update status/time/notes |
| POST | `/opd/appointments/{id}/cancel` | `appointments:update` | Cancel |
| GET | `/opd/appointments/doctor/{doctor_id}/slots` | `appointments:view` | Slot grid |

#### POST `/opd/appointments`

**Body**

```json
{
  "patient_id": 1,
  "doctor_id": 2,
  "department_id": 1,
  "scheduled_at": "2026-06-05T10:30:00+05:30",
  "reason": "Follow-up",
  "notes": null,
  "appointment_type": "opd"
}
```

**Response 201** — `AppointmentOut`:

```json
{
  "id": 1,
  "appointment_uid": "APT-0001",
  "patient_id": 1,
  "patient_name": "Amaresh Maurya",
  "patient_uid": "P-1001",
  "doctor_id": 2,
  "doctor_name": "Dr. Sharma",
  "department_id": 1,
  "department_name": "General Medicine",
  "scheduled_at": "2026-06-05T10:30:00+05:30",
  "reason": "Follow-up",
  "notes": null,
  "appointment_type": "opd",
  "status": "scheduled"
}
```

#### GET `/opd/appointments/doctor/{doctor_id}/slots`

**Query:** `department_id` (required), `date` (required, `YYYY-MM-DD`)

```json
{
  "doctor_id": 2,
  "date": "2026-06-05",
  "slots": [
    { "time": "09:00", "status": "available" },
    { "time": "09:30", "status": "booked" }
  ]
}
```

### 3.4 Beds

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/opd/beds?ward=&status=&search=` | `opd:view` | All beds + stats |
| GET | `/opd/beds/ward/{ward_name}` | `opd:view` | Ward detail |
| POST | `/opd/beds/assign` | `opd:create` | Assign patient to bed |
| POST | `/opd/beds/{bed_id}/release` | `opd:create` | Release bed |

#### POST `/opd/beds/assign`

```json
{
  "bed_id": 1,
  "patient_id": 1,
  "department_id": 1
}
```

---

# 4. Receptionist (`/receptionist`)

**Role:** `receptionist` (permissions: `patients:view`, `opd:view`, `appointments:view`, `appointments:update`).

Handles patient check-in, doctor queue board, and answering doctor **Next patient** requests. OPD billing creates appointments; reception moves patients into the queue.

### Workflow

```
OPD billing → appointment (scheduled)
Reception check-in → patient_queue (waiting)
Doctor request-next → doctor_queue_next_requests (pending)
Reception call-patient → called + called_at + called_by
Doctor start → in_progress + consultation_started_at
Doctor complete → completed
```

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/receptionist/dashboard` | `opd:view` | Today's queue stats (+ manager metrics); optional `doctor_id` |
| GET | `/receptionist/today-queue` | `opd:view` | **All doctors** — patients checked in today |
| GET | `/receptionist/arrivals` | `appointments:view` | Scheduled, not yet checked in |
| POST | `/receptionist/check-in/{appointment_id}` | `appointments:update` | Add to doctor queue (409 if duplicate) |
| GET | `/receptionist/doctor-queue/{doctor_id}` | `opd:view` | Live queue for one doctor |
| GET | `/receptionist/pending-calls` | `opd:view` | Doctors waiting for patient call |
| POST | `/receptionist/call-patient/{queue_id}` | `appointments:update` | Send patient to doctor room (`called`) |
| PATCH | `/receptionist/queue/{queue_id}/no-show` | `appointments:update` | Mark patient no-show |
| PATCH | `/receptionist/queue/{queue_id}/rejoin` | `appointments:update` | Rejoin after no-show |
| GET | `/receptionist/queue-history` | `opd:view` | Historical queue report |
| GET | `/receptionist/queue-history/export` | `opd:view` | CSV export (same filters) |

#### GET `/receptionist/dashboard`

Optional: `?doctor_id=5`

```json
{
  "success": true,
  "data": {
    "total_patients": 18,
    "waiting": 5,
    "called": 2,
    "in_progress": 1,
    "completed": 10,
    "no_show": 1,
    "pending_doctor_requests": 2,
    "todays_arrivals": 22,
    "todays_checked_in": 18,
    "todays_cancelled": 1,
    "average_waiting_time_minutes": 15.2
  }
}
```

#### GET `/receptionist/today-queue`

All patients **checked in** today across all doctors (`patient_queue`, IST date).

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `doctor_id` | int | Filter by doctor |
| `doctor_name` | string | Partial match on doctor first/last name |
| `patient_id` | int | Exact match on internal patient id |
| `status` | enum | `waiting`, `called`, `in_progress`, `completed`, `no_show`, … |
| `search` | string | Patient name, UHID, phone, patient id, token, **appointment UID**, doctor name |
| `page`, `limit` | int | Pagination (default 1, 20; max limit 100) |

**Example:**

```
GET /receptionist/today-queue?doctor_name=sharma&search=42&status=waiting&page=1&limit=20
```

#### GET `/receptionist/arrivals?doctor_id=5&search=APT-0042&page=1&limit=20`

**Search:** patient name, UHID, phone, **appointment_uid**.

```json
{
  "success": true,
  "total": 3,
  "page": 1,
  "limit": 20,
  "arrivals": [
    {
      "appointment_id": 42,
      "appointment_uid": "APT-0042",
      "patient_id": 1,
      "patient_name": "Nilesh Patil",
      "patient_uid": "P-1001",
      "patient_phone": "9567154627",
      "doctor_id": 5,
      "doctor_name": "Dr. Sharma",
      "scheduled_at": "2026-06-23T09:30:00+05:30"
    }
  ]
}
```

#### POST `/receptionist/check-in/{appointment_id}`

**Response 201** — creates queue row with `status: waiting`.

**Response 409** — patient already checked in (same appointment or same patient+doctor today).

```json
{
  "success": true,
  "message": "Patient checked in successfully",
  "queue": {
    "queue_id": 16,
    "appointment_id": 42,
    "queue_number": 7,
    "patient_id": 1,
    "patient_name": "Nilesh Patil",
    "patient_uid": "P-1001",
    "doctor_id": 5,
    "status": "waiting",
    "checked_in_at": "2026-06-23T09:45:00+05:30"
  }
}
```

#### GET `/receptionist/pending-calls?doctor_id=5`

Poll every 5–10 seconds. Call patient only when a row appears here (doctor clicked **Next patient**).

```json
{
  "success": true,
  "total": 1,
  "pending_calls": [
    {
      "request_id": 3,
      "doctor_id": 5,
      "doctor_name": "Dr. Sharma",
      "queue_id": 16,
      "queue_number": 7,
      "appointment_id": 42,
      "patient_id": 1,
      "patient_name": "Nilesh Patil",
      "patient_uid": "P-1001",
      "requested_at": "2026-06-23T10:30:00+05:30",
      "status": "pending"
    }
  ]
}
```

#### POST `/receptionist/call-patient/{queue_id}`

Requires matching pending doctor request. Sets `called_at`, `called_by`, and status **`called`** (not `in_progress`). Doctor `PUT /queue/start/{queue_id}` moves to `in_progress`.

#### GET `/receptionist/queue-history`

Same filters as list view. **Search** includes appointment UID.

#### GET `/receptionist/queue-history/export?format=csv`

CSV download with same query params as queue history (opens in Excel).

**Legacy equivalents (deprecate):** `POST /queue/add`, `GET /opd/queue/next-requests`, `POST /opd/queue/send-in`

---

# 5. Doctor module

**Role:** `doctor` (permissions: `appointments:view`, `appointments:update`, `prescriptions:create`, etc.)

Uses the **same** `appointments` table as OPD (`scheduled_at`, `appointment_uid`, `status`).

### Appointment status workflow (doctor)

```
scheduled → waiting → in_progress → completed
         ↘ cancelled (from scheduled / waiting / in_progress)
```

Queue flow often sets: add to queue → `waiting`, start consult → `in_progress`, complete → `completed`.

### 4.1 Doctor appointments (`/appointments`)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/appointments/dashboard-stats` | `appointments:view` | Today counts |
| GET | `/appointments/today` | `appointments:view` | Today's list |
| GET | `/appointments/history` | `appointments:view` | Completed history |
| GET | `/appointments/by-date/{appointment_date}` | `appointments:view` | By date (`YYYY-MM-DD`) |
| GET | `/appointments/{appointment_id}` | `appointments:view` | Single appointment |
| PUT | `/appointments/{appointment_id}/status` | `appointments:update` | Change status |

**Wrapper response** (most list endpoints):

```json
{
  "success": true,
  "message": "Today's appointments fetched successfully",
  "appointment": 5,
  "appointments": [ /* appointment objects */ ]
}
```

**Single appointment object** (from doctor services):

```json
{
  "id": 1,
  "appointment_uid": "APT-0001",
  "patient_id": 1,
  "patient_name": "Amaresh Maurya",
  "patient_phone": "9567154627",
  "patient_age": 35,
  "patient_gender": "Male",
  "patient_uhid": "P-1001",
  "doctor_id": 2,
  "department_id": 1,
  "scheduled_at": "2026-06-05T10:30:00+05:30",
  "appointment_date": "2026-06-05",
  "appointment_time": "10:30:00",
  "appointment_type": "opd",
  "status": "scheduled",
  "reason": "Fever",
  "notes": null,
  "created_at": "2026-06-02T09:00:00+05:30"
}
```

#### PUT `/appointments/{appointment_id}/status`

**Body**

```json
{
  "status": "waiting"
}
```

Allowed values: `scheduled`, `waiting`, `in_progress`, `completed`, `cancelled` (must follow workflow).

#### GET `/appointments/dashboard-stats`

```json
{
  "success": true,
  "message": "Dashboard stats fetched successfully",
  "data": {
    "today_appointments": 10,
    "patients_waiting": 3,
    "patients_in_progress": 1,
    "completed_consultations": 4,
    "cancelled_appointments": 0
  }
}
```

### 4.2 Patient queue (`/queue`)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/queue/add` | `appointments:update` | Add appointment to queue |
| GET | `/queue/today` | `appointments:view` | Today's queue |
| PUT | `/queue/start/{queue_id}` | `appointments:update` | Start consultation |
| PUT | `/queue/complete/{queue_id}` | `appointments:update` | Complete consultation |
| GET | `/queue/current` | `appointments:view` | Current in-progress patient |

#### POST `/queue/add`

```json
{
  "appointment_id": 1
}
```

**Response 201**

```json
{
  "success": true,
  "message": "Patient added to queue successfully",
  "queue": { /* PatientQueue row */ }
}
```

#### PUT `/queue/start/{queue_id}`

```json
{
  "success": true,
  "message": "Consultation started successfully",
  "waiting_minutes": 12.5,
  "queue": { /* ... */ }
}
```

### 4.3 Patient history (`/patients`) — doctor only

Not the same as `GET /opd/patients`.

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/patients?page=&limit=&search=&filter_date=&month=&year=` | `appointments:view` | Completed visits list |
| GET | `/patients/{patient_uhid}` | `appointments:view` | History for one patient UID |

**Response** — list uses same appointment-shaped objects as doctor appointments.

### 4.4 Prescriptions (`/prescriptions`)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/prescriptions` | `prescriptions:create` | Create prescription |
| GET | `/prescriptions/{prescription_id}` | Yes (login) | Get one |
| GET | `/prescriptions/patient/{patient_id}` | Yes (login) | List by patient |
| PUT | `/prescriptions/{prescription_id}` | `prescriptions:update` | Update |
| DELETE | `/prescriptions/{prescription_id}` | `prescriptions:delete` | Delete |

> Ensure doctor role has `prescriptions:update` and `prescriptions:delete` in DB if you use PUT/DELETE.

#### POST `/prescriptions`

**Body**

```json
{
  "appointment_id": 1,
  "diagnosis": "Viral fever",
  "notes": "Rest and fluids",
  "items": [
    {
      "medicine_name": "Paracetamol",
      "dosage": "500mg",
      "frequency": "Twice daily",
      "duration": "5 days",
      "instructions": "After food"
    }
  ]
}
```

Requires appointment `status` = `completed`.

### 4.5 Lab tests (`/lab-tests`)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/lab-tests` | Login only | Create order |
| GET | `/lab-tests?search=&skip=&limit=` | Login only | List/search |
| PUT | `/lab-tests/{test_id}` | Login only | Update (ordered only) |
| PATCH | `/lab-tests/{test_id}/cancel` | Login only | Cancel |

#### POST `/lab-tests`

```json
{
  "appointment_id": 1,
  "test_name": "CBC",
  "category": "Blood Test",
  "priority": "Normal",
  "clinical_notes": "Routine check"
}
```

**Status values:** `ordered`, `sample_collected`, `processing`, `completed`, `cancelled`

---

# 6. Permission cheat sheet by role

### `opd_billing`

`patients:view`, `patients:create`, `patients:update`, `patients:delete`, `opd:view`, `opd:create`, `billing:view`, `billing:create`, `billing:update`, `appointments:view`, `appointments:create`, `appointments:update`

### `receptionist`

`patients:view`, `opd:view`, `appointments:view`, `appointments:update`

### `doctor`

`patients:view`, `opd:view`, `prescriptions:create`, `lab:create`, `lab:view`, `appointments:view`, `appointments:update`  
(Add `prescriptions:update`, `prescriptions:delete` if using those endpoints.)

### `admin`

All permissions (from seed).

---

# 7. Frontend integration tips

1. **Axios/fetch:** attach `Authorization: Bearer ${token}` on every call except login/register.
2. **403 on OPD routes:** re-login after DB permission changes.
3. **Date/time:** send ISO 8601 with timezone for `scheduled_at` (e.g. `2026-06-05T10:30:00+05:30`).
4. **Pagination:** OPD patients/bills use `page` + `limit`; lab tests use `skip` + `limit`.
5. **Swagger:** use `/docs` to try requests with "Authorize" button.
6. **Role flows:** screen-by-screen guides in [roles/](./roles/) (OPD, doctor, etc.).

---

# 8. Quick endpoint index (A–Z by path)

| Method | Path |
|--------|------|
| GET | `/` |
| POST | `/auth/login` |
| GET | `/auth/me` |
| POST | `/auth/register` |
| GET | `/appointments/by-date/{date}` |
| GET | `/appointments/dashboard-stats` |
| GET | `/appointments/history` |
| GET | `/appointments/today` |
| GET | `/appointments/{id}` |
| PUT | `/appointments/{id}/status` |
| POST | `/lab-tests` |
| GET | `/lab-tests` |
| PUT | `/lab-tests/{test_id}` |
| PATCH | `/lab-tests/{test_id}/cancel` |
| GET | `/opd/appointments` |
| POST | `/opd/appointments` |
| PATCH | `/opd/appointments/{id}` |
| POST | `/opd/appointments/{id}/cancel` |
| GET | `/opd/appointments/doctor/{doctor_id}/slots` |
| GET | `/opd/beds` |
| POST | `/opd/beds/assign` |
| POST | `/opd/beds/{bed_id}/release` |
| GET | `/opd/beds/ward/{ward_name}` |
| POST | `/opd/bill/generate` |
| POST | `/opd/bill/preview` |
| GET | `/opd/bills` |
| GET | `/opd/dashboard` |
| GET | `/opd/departments` |
| GET | `/opd/doctors/department/{department_id}` |
| GET | `/opd/patient/search` |
| GET | `/opd/patient/{id}` |
| GET | `/opd/patient/{id}/profile` |
| PUT | `/opd/patient/{id}` |
| DELETE | `/opd/patient/{id}` |
| POST | `/opd/patient/preview-bill` |
| POST | `/opd/patient/register` |
| GET | `/opd/patients` |
| GET | `/opd/payments/history` |
| GET | `/opd/visits/today` |
| GET | `/opd/queue/today` |
| POST | `/opd/visit` |
| GET | `/opd/visit/{visit_id}/invoice` |
| POST | `/opd/visit/{visit_id}/pay` |
| GET | `/patients` |
| GET | `/patients/{patient_uhid}` |
| POST | `/prescriptions` |
| GET | `/prescriptions/patient/{patient_id}` |
| GET | `/prescriptions/{prescription_id}` |
| PUT | `/prescriptions/{prescription_id}` |
| DELETE | `/prescriptions/{prescription_id}` |
| GET | `/receptionist/arrivals` |
| POST | `/receptionist/call-patient/{queue_id}` |
| POST | `/receptionist/check-in/{appointment_id}` |
| GET | `/receptionist/dashboard` |
| GET | `/receptionist/today-queue` |
| GET | `/receptionist/doctor-queue/{doctor_id}` |
| GET | `/receptionist/pending-calls` |
| GET | `/receptionist/queue-history` |
| GET | `/receptionist/queue-history/export` |
| PATCH | `/receptionist/queue/{queue_id}/no-show` |
| PATCH | `/receptionist/queue/{queue_id}/rejoin` |
| POST | `/queue/add` |
| PUT | `/queue/complete/{queue_id}` |
| GET | `/queue/current` |
| PUT | `/queue/start/{queue_id}` |
| GET | `/queue/today` |
| GET | `/roles/` |
| POST | `/roles/` |
| POST | `/roles/permissions` |
| POST | `/roles/{role_id}/permissions` |

---

*Last aligned with backend routers: Auth, Roles, OPD (`Routers/opd.py`), Doctor (appointment, queue, patients, prescriptions, lab-tests).*
