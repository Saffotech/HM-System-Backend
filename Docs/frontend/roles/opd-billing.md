# OPD Billing — Frontend Flow

**Role name from API:** `opd_billing`  
**Folder:** `src/pages/opd-billing/`  
**URL prefix:** `/opd-billing/`

Front desk staff: register patients, take payment, book appointments.

Queue / check-in is the **[Receptionist module](../../flows/receptionist-module.md)** (separate role).

---

## Screens to build

| # | Screen | Route | Backend ready? |
|---|--------|-------|----------------|
| 1 | Dashboard | `/opd-billing/dashboard` | Partial |
| 2 | Register Patient | `/opd-billing/register-patient` | Yes |
| 3 | Patient Search | `/opd-billing/patients` | Partial |
| 4 | Today's Queue | `/opd-billing/queue` | Yes |
| 5 | View Invoice | `/opd-billing/invoice/:visitId` | Yes |
| 6 | Billing List | `/opd-billing/bills` | No — wait backend |
| 7 | Collect Payment | `/opd-billing/collect-payment/:visitId` | No — wait backend |
| 8 | Book Appointment | `/opd-billing/appointments` | No — wait backend |

---

## Sidebar menu (example)

```
Dashboard
Register Patient
Patient Search
Today's Queue
Billing          (when API ready)
Appointments     (when API ready)
Sign out
```

Show item only if `permissions` includes the right key (e.g. `patients:create`).

---

## Flow 1 — Register new patient (main flow)

This is the **first priority** screen.

```
Dashboard
    → click "Register Patient"
    → Step A: Enter phone → Search
    → Step B: If found → show patient OR fill new form
    → Step C: Select Department → load Doctors
    → Step D: Enter fees (or defaults)
    → Step E: Preview bill
    → Step F: Select payment mode → Submit
    → Step G: Success screen (Patient ID, Bill ID, Token)
    → Optional: Open Invoice / Print
```

### Step A — Search by phone

| | |
|---|---|
| **API** | `GET /opd/patient/search?phone=9567154627` |
| **Token** | Yes |

**If `found: false`** → show full registration form  
**If `found: true`** → show patient summary; maybe skip to new visit only (when backend supports)

### Step B — Patient form fields

| Field | Required | Input type |
|-------|----------|------------|
| first_name | Yes | text |
| phone | Yes | tel (10 digit) |
| last_name | No | text |
| gender | No | select |
| date_of_birth | No | date |
| blood_group | No | select |
| address, state | No | text |
| aadhaar_number | No | text |
| email | No | email |
| emergency_contact_name | No | text |
| emergency_contact_phone | No | tel |
| allergies | No | text |

### Step C — Department & doctor

| Order | API |
|-------|-----|
| 1 | `GET /opd/departments` → fill department dropdown |
| 2 | User picks department |
| 3 | `GET /opd/doctors/department/{department_id}` → fill doctor dropdown |

### Step D — Fees

| Field | Default |
|-------|---------|
| registration_fee | 200 |
| consultation_fee | 800 |
| gst_percent | 5 |

### Step E — Preview bill

| | |
|---|---|
| **API** | `POST /opd/patient/preview-bill` |
| **Body** | Same as register form |

Show: subtotal, GST, grand total (read-only)

### Step F — Payment & submit

| | |
|---|---|
| **API** | `POST /opd/patient/register?payment_mode=cash` |
| **Permission** | `patients:create` |

Payment mode dropdown: `cash` | `card` | `upi` | `insurance`

### Step G — Success page

Show from response:

- `patient_id` (e.g. P-1001)
- `bill_number` (e.g. BILL-001)
- `visit_id` → link to invoice

Button: **View Invoice** → `/opd-billing/invoice/{visitId}`

---

## Flow 2 — View invoice / print

**Route:** `/opd-billing/invoice/:visitId`

| | |
|---|---|
| **API** | `GET /opd/visit/{visitId}/invoice` |

**Show on page:**

- Bill number, date
- Patient name, phone, address
- Department, doctor name
- Line items table
- Payment history
- Totals (subtotal, GST, grand total, paid, balance)

Button: **Print** → `window.print()` or PDF later

---

## Flow 3 — Today's queue

**Route:** `/opd-billing/queue`

| | |
|---|---|
| **API** | `GET /opd/visits/today` |

> **Not** `/receptionist/*` — this screen is **billing visits** only. See [Queue endpoints guide](../../flows/queue-endpoints-guide.md).

**Table columns:**

| Column | Source |
|--------|--------|
| Token | token_number |
| Patient | patient name (may need backend to include) |
| Doctor | doctor name |
| Status | status |
| Time | visit_date |
| Action | View invoice |

---

## Flow 4 — Dashboard (first screen)

**Route:** `/opd-billing/dashboard`

**On load — call these APIs:**

| Card / section | API | Notes |
|----------------|-----|-------|
| Today's queue count | `GET /opd/visits/today` | Use `total` (billing visits, not clinical queue) |
| Quick actions | Links only | Register, Queue, Search |

**Later when backend ready:** pending bills count, appointments

**UI blocks (from Word file):**

- Greeting: `Hello, {first_name}`
- Cards: Total visits today, Pending bills
- Quick buttons: Register Patient, Today's Queue
- Small table: last 5 visits from queue API

---

## Suggested files

```
pages/opd-billing/
├── OpdBillingRoutes.tsx      # all routes for this role
├── Dashboard.tsx
├── RegisterPatient.tsx       # multi-step wizard
├── InvoiceView.tsx
├── TodayQueue.tsx
└── components/
    ├── PatientForm.tsx
    ├── BillPreview.tsx
    └── DepartmentDoctorSelect.tsx
```

---

## Types (add in `src/types/opd.ts`)

```ts
export type PatientSearchResponse = {
  found: boolean
  patient_id?: number
  patient_uid?: string
  name?: string
  phone?: string
  ...
}

export type RegisterPatientResponse = {
  message: string
  patient_id: string
  bill_number: string
  visit_id: number
}
```

---

## Errors to handle

| Status | Show user |
|--------|-----------|
| 409 | Patient already exists (show existing UID) |
| 403 | No permission |
| 401 | Redirect to login |
