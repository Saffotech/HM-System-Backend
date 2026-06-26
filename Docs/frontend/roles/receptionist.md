# Receptionist — Frontend Flow

**Role name from API:** `receptionist`  
**Folder:** `src/pages/receptionist/`  
**URL prefix:** `/receptionist/`

**Full module spec:** [Receptionist Module](../../flows/receptionist-module.md)

---

## Module purpose

Reception manages the **live OPD waiting line** after OPD Billing has booked an appointment.

| Reception does | Reception does not |
|----------------|-------------------|
| Check-in arriving patients | Register patients or collect payment |
| View doctor queue boards | Start or complete consultations |
| Answer doctor **Next patient** requests | Guess when doctor is ready |

**Workflow in one line:** OPD Billing books → Reception check-in → Doctor completes & requests next → Reception calls patient → Doctor consults.

---

## Screens to build

| # | Screen | Route | Primary API |
|---|--------|-------|-------------|
| 1 | Dashboard | `/receptionist/dashboard` | `GET /receptionist/dashboard` |
| 2 | Arrivals | `/receptionist/arrivals` | `GET /receptionist/arrivals` |
| 2b | Today's queue (all doctors) | `/receptionist/today` | `GET /receptionist/today-queue` |
| 3 | Doctor queues | `/receptionist/queues` | `GET /receptionist/doctor-queue/{doctor_id}` |
| 4 | Pending calls | `/receptionist/pending-calls` | `GET /receptionist/pending-calls` |
| 5 | Queue history | `/receptionist/history` | `GET /receptionist/queue-history` |
| 5b | Queue history export | — | `GET /receptionist/queue-history/export` |

---

## Sidebar menu

```
Dashboard
Arrivals
Today's Queue
Doctor Queues
Pending Calls
Queue History
Sign out
```

**Badge:** Show count on **Pending Calls** when `pending_doctor_requests > 0` (from dashboard or poll).

---

## Global UI rules

| Rule | Detail |
|------|--------|
| Auth | Redirect to `/login` on 401 |
| Permissions | Hide module if role ≠ `receptionist` |
| Status badges | `waiting`, `called`, `in_progress`, `completed`, `no_show` — use consistent colors |
| API status values | Lowercase strings from backend |
| Date/time | Display in IST; store ISO from API |
| Toast errors | Show API `detail` message |
| Do not use | `GET /opd/visits/today` or `GET /opd/queue/today` for queue — billing visits only. See [Queue endpoints guide](../../flows/queue-endpoints-guide.md) |

---

## Screen 1 — Dashboard (`/receptionist/dashboard`)

**Purpose:** Landing page with today’s queue summary and quick navigation.

**API:** `GET /receptionist/dashboard`  
Optional filter: `?doctor_id=5` for one doctor’s stats.

### UI layout

| Block | Content |
|-------|---------|
| Greeting | `Hello, {first_name}` |
| Stat cards | Waiting, Called, In consultation, Completed, No-show, Pending doctor calls |
| Manager metrics | Today's arrivals, Today's checked-in, Today's cancelled, Avg waiting time |
| Quick actions | Links to Arrivals, Today's queue, Doctor Queues, Pending Calls |
| Optional | Mini table — last 5 pending calls or recent check-ins |

### Controls

| Control | Needed? | Notes |
|---------|---------|--------|
| Doctor filter | Optional | `doctor_id` — stats for one doctor |
| Search bar | No | Summary screen |
| Pagination | No | |
| Refresh | Optional | Manual button or auto every 30–60s |

### Stat card → API field

| Card label | Field |
|------------|-------|
| Waiting | `waiting` |
| Called (not yet in room) | `called` |
| In consultation | `in_progress` |
| Completed today | `completed` |
| No-show | `no_show` |
| Doctors waiting for call | `pending_doctor_requests` |
| Total in queue today | `total_patients` |
| Today's arrivals | `todays_arrivals` |
| Today's checked-in | `todays_checked_in` |
| Today's cancelled | `todays_cancelled` |
| Avg waiting time | `average_waiting_time_minutes` (minutes; `null` if none started yet) |

**Example:**

```
GET /receptionist/dashboard?doctor_id=5
```

**Empty state:** N/A — show zeros on cards.

**Loading:** Skeleton cards.

**Error:** Toast + Retry button.

---

## Screen 2 — Arrivals (`/receptionist/arrivals`)

**Purpose:** Today’s appointments that are **scheduled** but **not yet checked in**.

**API:** `GET /receptionist/arrivals`  
**Action:** `POST /receptionist/check-in/{appointment_id}`

### Flow

```
Load arrivals (with filters)
    → User clicks "Check in" on row
    → POST /receptionist/check-in/{appointment_id}
    → Remove row from list (or refetch)
    → Toast: "Token #7 — checked in"
```

### Toolbar controls

| Control | Type | API param | Default | Notes |
|---------|------|-----------|---------|-------|
| **Search** | Text input | `search` | — | Debounce **400ms** |
| **Doctor** | Select dropdown | `doctor_id` | All doctors | Load doctors via `GET /opd/doctors/department/{id}` |
| **Department** | Select (optional) | — | All | Filters doctor dropdown only (client-side) |
| **Page size** | Select | `limit` | 20 | Options: 10, 20, 50 |
| **Pagination** | Bottom pager | `page` | 1 | Server-side |

**Search matches:** patient name, UHID, phone, **appointment UID** (backend).

**Example request:**

```
GET /receptionist/arrivals?doctor_id=5&search=nilesh&page=1&limit=20
```

**Paginated response:**

```json
{
  "success": true,
  "total": 45,
  "page": 1,
  "limit": 20,
  "arrivals": []
}
```

### Table columns

| Column | Source | Sortable |
|--------|--------|----------|
| Time | `scheduled_at` | Yes (default asc) |
| Appointment UID | `appointment_uid` | — |
| Patient | `patient_name` | — |
| UHID | `patient_uid` | — |
| Phone | `patient_phone` | — |
| Doctor | `doctor_name` | — |
| Action | Check in button | — |

### Row action

| Button | API | Enabled when |
|--------|-----|--------------|
| Check in | `POST /receptionist/check-in/{appointment_id}` | Always on arrivals list |

### States

| State | UI |
|-------|-----|
| Empty | "No arrivals waiting for check-in today" + link to refresh |
| Loading | Skeleton table rows |
| Error | Toast with `detail` + Retry |
| After check-in | Row removed; optional link "View in today's queue" |
| 409 Conflict | Toast: patient already checked in today |

---

## Screen 2b — Today's queue — all doctors (`/receptionist/today`)

**Purpose:** Single board of every patient **checked in today** across all doctors (reception dashboard table).

**API:** `GET /receptionist/today-queue`

### Toolbar controls

| Control | Type | API param | Default | Notes |
|---------|------|-----------|---------|-------|
| **Doctor** | Select dropdown | `doctor_id` | All | Optional |
| **Doctor name** | Text input | `doctor_name` | — | Partial match; alternative to dropdown |
| **Patient ID** | Number input | `patient_id` | — | Exact internal id |
| **Status tabs** | Tab bar | `status` | All | Same values as doctor queue |
| **Search** | Text input | `search` | — | Debounce 400ms; patient name, UHID, phone, patient id, token, **appointment UID**, doctor name |
| **Page size** | Select | `limit` | 20 | 10, 20, 50 |
| **Pagination** | Bottom pager | `page` | 1 | Server-side |

**Sort order (server):** priority (high first) → `called` / `waiting` patients first → token number.

**Example:**

```
GET /receptionist/today-queue?doctor_name=sharma&patient_id=12&status=waiting&search=rahul&page=1&limit=20
```

### Table columns

| Column | Source |
|--------|--------|
| Token | `queue_number` |
| Appointment UID | `appointment_uid` |
| Patient | `patient_name` |
| UHID | `patient_uid` |
| Doctor | `doctor_name` |
| Status | `status` |
| Checked in | `checked_in_at` |
| Called | `called_at` |
| Called by (ID) | `called_by` |
| Called by (name) | `called_by_name` |

---

## Screen 3 — Doctor queues (`/receptionist/queues`)

**Purpose:** Live queue board for **one doctor** today (`waiting`, `called`, `in_progress`, `completed`, `no_show`).

**API:** `GET /receptionist/doctor-queue/{doctor_id}`

### Flow

```
Select department (optional) → Select doctor (required)
    → GET /receptionist/doctor-queue/{doctor_id}?status=&search=
    → Table with row actions
```

### Toolbar controls

| Control | Type | API param | Default | Notes |
|---------|------|-----------|---------|-------|
| **Doctor** | Select (required) | path `{doctor_id}` | First doctor or none | Required before load |
| **Department** | Select | — | All | Filters doctor list (client) |
| **Status tabs** | Tab bar | `status` | All | `waiting`, `called`, `in_progress`, `completed`, `no_show` |
| **Search** | Text input | `search` | — | Debounce 400ms; name, UHID, token, patient id, appointment UID |
| **Date** | Date picker | `date` | Today | v1: today only; v2: past dates |
| **Refresh** | Button | — | — | Manual reload |
| **Pagination** | Optional | `page`, `limit` | — | Only if queue > ~50/day |

**Example:**

```
GET /receptionist/doctor-queue/5?status=waiting&search=rahul
```

### Table columns

| Column | Source |
|--------|--------|
| Token | `queue_number` |
| Patient | `patient_name` |
| UHID | `patient_uid` |
| Status | `status` (badge) |
| Checked in | `checked_in_at` |
| Called | `called_at` |
| Actions | Context menu |

### Row actions

| Action | API | Show when |
|--------|-----|-----------|
| No-show | `PATCH /receptionist/queue/{queue_id}/no-show` | `status` is `waiting`, `called`, or `vitals_completed` |
| Rejoin | `PATCH /receptionist/queue/{queue_id}/rejoin` | `status = no_show` |
| Call patient | — | Use **Pending Calls** screen instead (doctor must request first) |

### States

| State | UI |
|-------|-----|
| No doctor selected | "Select a doctor to view queue" |
| Empty queue | "No patients in queue for Dr. {name} today" |
| Loading | Skeleton rows |

---

## Screen 4 — Pending calls (`/receptionist/pending-calls`)

**Purpose:** Doctors clicked **Next patient** — reception must call these patients to the room.

**Why this screen exists:** Reception does not know how long consultations take. Doctor signals when ready; reception calls the patient.

**API:** `GET /receptionist/pending-calls` (poll)  
**Action:** `POST /receptionist/call-patient/{queue_id}`

### Flow

```
Poll GET /receptionist/pending-calls every 5–10s
    → Card per pending request: doctor, patient, token, time
    → Click "Call patient"
    → POST /receptionist/call-patient/{queue_id}
    → Queue status becomes `called` (patient heading to room; not `in_progress` yet)
    → Card removed on next poll
```

### Controls

| Control | Type | API param | Notes |
|---------|------|-----------|-------|
| **Doctor filter** | Select (optional) | `doctor_id` | When many doctors |
| **Search** | No | — | List is usually small |
| **Pagination** | No | — | |
| **Polling** | Auto | — | Every **5–10 seconds** while tab focused |
| **Sound / badge** | UI | — | On new `request_id` |

**Example:**

```
GET /receptionist/pending-calls?doctor_id=5
```

### Card content

| Field | Source |
|-------|--------|
| Doctor | `doctor_name` |
| Patient | `patient_name` |
| UHID | `patient_uid` |
| Token | `queue_number` |
| Requested at | `requested_at` |
| Action | **Call patient** button |

### UX rules

| Rule | Detail |
|------|--------|
| Badge on sidebar | When `total > 0` |
| New request sound | Compare `request_id` to previous poll |
| Disable button | After successful call until refetch |
| Confirm dialog | Optional: "Call Token #7 to Dr. Sharma's room?" |
| If patient missing | Use No-show from Doctor Queues screen |

### States

| State | UI |
|-------|-----|
| Empty | "No doctors waiting for patient call" |
| Loading first fetch | Spinner |
| Error on poll | Silent retry; toast only on manual refresh fail |

---

## Screen 5 — Queue history (`/receptionist/history`)

**Purpose:** Past queue records for reporting and lookup (completed, no-show, etc.).

**API:** `GET /receptionist/queue-history`  
**Export:** `GET /receptionist/queue-history/export?format=csv` (same filters; CSV download — opens in Excel)

### Toolbar controls

| Control | Type | API param | Default |
|---------|------|-----------|---------|
| **Date from / to** | Date range | `date_from`, `date_to` | Today only |
| **Single date** | Date | `date` | Today |
| **Doctor** | Select | `doctor_id` | All |
| **Status** | Multi-select | `status` | `completed` |
| **Search** | Text | `search` | Debounce 400ms — name, UHID, phone, patient id, token, **appointment UID**, doctor name |
| **Pagination** | Required | `page`, `limit` | page=1, limit=20 |
| **Export** | Button | — | Calls export endpoint with current filters |

**Example:**

```
GET /receptionist/queue-history?date_from=2026-06-01&date_to=2026-06-23&doctor_id=5&status=completed&search=APT-0042&page=1&limit=20
GET /receptionist/queue-history/export?date_from=2026-06-01&date_to=2026-06-23&format=csv
```

### Table columns

| Column | Source |
|--------|--------|
| Date | `queue_date` |
| Token | `queue_number` |
| Appointment UID | `appointment_uid` |
| Patient | `patient_name` |
| Doctor | `doctor_name` |
| Status | `status` |
| Checked in | `checked_in_at` |
| Called | `called_at` |
| Called by (ID) | `called_by` |
| Called by (name) | `called_by_name` |
| Completed | `consultation_completed_at` |

**Note:** For **today only**, use **Today's queue** or Doctor Queues with status filters.

---

## Filters, search & pagination — summary

| Screen | Search | Filters | Pagination | Polling |
|--------|--------|---------|------------|---------|
| Dashboard | — | Doctor (`doctor_id`) | — | Optional refresh |
| **Arrivals** | **Yes** | Doctor, Dept (UI) | **Yes** | — |
| **Today's queue** | **Yes** | Doctor id/name, patient id, status | **Yes** | Manual refresh |
| **Doctor queues** | Optional | Doctor (required), Status, Date | Optional | Manual refresh |
| **Pending calls** | — | Doctor (optional) | — | **Yes (5–10s)** |
| **Queue history** | **Yes** | Date range, Doctor, Status | **Yes** | Export CSV |

---

## Suggested files

```
pages/receptionist/
├── ReceptionistRoutes.tsx
├── Dashboard.tsx
├── Arrivals.tsx
├── TodayQueue.tsx
├── DoctorQueues.tsx
├── PendingCalls.tsx
├── QueueHistory.tsx
├── hooks/
│   ├── useReceptionistArrivals.ts    # search, filters, pagination
│   ├── useDoctorQueue.ts
│   └── usePendingCallsPoll.ts        # interval poll
└── components/
    ├── QueueTable.tsx
    ├── ArrivalTable.tsx
    ├── ArrivalFilters.tsx
    ├── DoctorQueueFilters.tsx
    ├── PendingCallCard.tsx
    ├── QueueStatusBadge.tsx
    └── PaginationBar.tsx
```

---

## Types (`src/types/receptionist.ts`)

```ts
export type PaginatedMeta = {
  total: number
  page: number
  limit: number
}

export type ReceptionistDashboard = {
  total_patients: number
  waiting: number
  called: number
  in_progress: number
  completed: number
  no_show: number
  pending_doctor_requests: number
  todays_arrivals: number
  todays_checked_in: number
  todays_cancelled: number
  average_waiting_time_minutes: number | null
}

export type Arrival = {
  appointment_id: number
  appointment_uid: string
  patient_id: number
  patient_name: string
  patient_uid: string
  patient_phone?: string
  doctor_id: number
  doctor_name: string
  scheduled_at: string
}

export type ArrivalsResponse = PaginatedMeta & {
  arrivals: Arrival[]
}

export type QueueItem = {
  queue_id: number
  appointment_id: number
  appointment_uid?: string
  queue_number: number
  patient_id: number
  patient_name: string
  patient_uid: string
  status: string
  checked_in_at: string
  called_at: string | null
  called_by: number | null
  called_by_name: string | null
  consultation_started_at?: string | null
  consultation_completed_at?: string | null
  doctor_name?: string
}

export type PendingCall = {
  request_id: number
  doctor_id: number
  doctor_name: string
  queue_id: number
  queue_number: number
  patient_name: string
  patient_uid: string
  requested_at: string
}
```

---

## API client (`src/api/receptionist.ts`)

```ts
// Example function signatures
getDashboard(params?: { doctor_id?: number })
getTodayQueue(params?: { doctor_id?: number; doctor_name?: string; patient_id?: number; status?: string; search?: string; page?: number; limit?: number })
getArrivals(params: { doctor_id?: number; search?: string; page?: number; limit?: number })
checkIn(appointmentId: number)
getDoctorQueue(doctorId: number, params?: { status?: string; search?: string; date?: string })
getPendingCalls(params?: { doctor_id?: number })
callPatient(queueId: number)
markNoShow(queueId: number)
rejoinQueue(queueId: number)
getQueueHistory(params: { date?: string; date_from?: string; date_to?: string; doctor_id?: number; status?: string; search?: string; page?: number; limit?: number })
exportQueueHistory(params: { date?: string; date_from?: string; date_to?: string; doctor_id?: number; status?: string; search?: string; format?: 'csv' })
```

---

## Related modules

| Module | Job |
|--------|-----|
| [OPD Billing](./opd-billing.md) | Register, pay, book appointments (before check-in) |
| [Doctor](./doctor.md) | Complete, request next, start consultation |

**Shared APIs for doctor dropdown:**

- `GET /opd/departments`
- `GET /opd/doctors/department/{department_id}`

---

## Errors to handle

| Status | Show user |
|--------|-----------|
| 400 | Already checked in / invalid queue state / patient not waiting |
| 404 | Appointment or queue not found |
| 403 | No permission — contact admin |
| 401 | Redirect to login |
| 409 | Duplicate check-in — patient already in today's queue |

| API `detail` (examples) | UI message |
|-------------------------|------------|
| Patient already checked in for this appointment today | "Patient already checked in" |
| Patient already has a queue entry with this doctor today | "Patient already in queue with this doctor today" |
| Cannot call patient when status is … | "Patient is not in waiting state" |

---

## Implementation status

| Item | Status |
|------|--------|
| All receptionist screens | To build |
| API client + hooks | To build |
| Backend `/receptionist/*` APIs | Done — see [API Reference](../API-REFERENCE.md#4-receptionist-receptionist) |

---

## Build order (frontend)

| Phase | Screens |
|-------|---------|
| P1 | Arrivals (search + pagination) + Check-in |
| P2 | Doctor Queues + Pending Calls (poll) |
| P3 | Dashboard |
| P4 | Queue History |
| P5 | Polish — badges, sounds, empty states |

Match backend build order in [Receptionist Module §7](../../flows/receptionist-module.md#7-build-order).
