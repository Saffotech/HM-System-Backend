# OPD Billing (`opd_billing`)

**Word file name:** Billing Counter / OPD Front Desk

Staff at the front desk: register patients, take payment, book appointments.

Queue management is the **[Receptionist](../flows/receptionist-module.md)** module (separate from billing).

**Do not confuse:** `GET /opd/visits/today` (billing visits) vs `GET /receptionist/doctor-queue/{doctor_id}` (clinical queue). See [Queue endpoints guide](../flows/queue-endpoints-guide.md).

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | Core OPD billing APIs (register, bill, invoice, today's visits) — documented below |
| **Phase 2** | Hospital settings integration, server pagination wiring, doc sync — planned at end of this file |

---

## Permissions (already in seed)

```
patients:view, patients:create, patients:update
opd:create, opd:view
billing:view, billing:create, billing:update
```

---

## Register staff user

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name | Yes |
| email | Yes |
| password | Yes (min 8) |
| role_id | Yes — use id of role `opd_billing` from GET `/roles/` |
| department_id | No |

---

## Phase 1 — Done (backend)

### 1. Search patient by phone

**GET** `/opd/patient/search?phone=9567154627`

Returns patient if found, or message to register new.

### 2. Register patient + bill + payment

**POST** `/opd/patient/register?payment_mode=cash`

**Permission:** `patients:create`

**Body (main fields):**

| Field | Required | Default |
|-------|----------|---------|
| first_name | Yes | |
| phone | Yes | |
| department_id | Yes | |
| doctor_id | Yes | |
| registration_fee | No | 200 |
| consultation_fee | No | 800 |
| gst_percent | No | 5 |

Optional: last_name, gender, blood_group, date_of_birth, address, state, aadhaar_number, email, emergency contacts, allergies.

**Response example:**

```json
{
  "patient_id": "P-1001",
  "bill_number": "BILL-001",
  "visit_id": 1
}
```

### 3. Preview bill (no save)

**POST** `/opd/patient/preview-bill` — same body as register, returns totals only.

### 4. Invoice

**GET** `/opd/visit/{visit_id}/invoice`

### 5. Today's queue

**GET** `/opd/visits/today` — today's **billing visits** (`opd_visits`: bills, payment status).

> **Not** the clinical waiting-room queue. Reception uses `/receptionist/*`.  
> See [Queue endpoints guide](../flows/queue-endpoints-guide.md).

**GET** `/opd/queue/today` — **deprecated** alias of `/opd/visits/today`.

### 6. Departments & doctors

- **GET** `/opd/departments`
- **GET** `/opd/doctors/department/{department_id}`

---

## Tables used

**patients** — patient details (name, phone, aadhaar, etc.)

**opd_visits** — one visit = one bill (fees, GST, payment_status, token_number)

---

## Payment modes

Use string: `cash`, `card`, `upi`, `insurance`

Store in `opd_visits.payment_mode`.

---

## Phase 2 — Planned

Work **after** Phase 1 is stable in production. Phase 1 APIs stay; Phase 2 adds integrations and frontend alignment.

### Backend — Phase 2

| # | Feature | API / area | Why |
|---|---------|------------|-----|
| 1 | **Hospital settings on invoice** | `GET /opd/visit/{visit_id}/invoice` | Read hospital `name`, address, `gstin` from `hospital_settings` instead of hardcoded `"CarePoint Hospital"` |
| 2 | **Default fees from settings** | New read-only `GET /opd/billing-defaults` (or service helper) | Pre-fill `registration_fee`, `consultation_fee`, `gst_percent` from Super Admin settings on register/bill |
| 3 | **Appointments — server pagination** | `GET /opd/appointments` | Backend has `page`, `limit`, `list_filter`, `search`, payment fields — frontend must stop `fetchAll: true` |
| 4 | **Billing list — server pagination** | `GET /opd/bills` | Backend has `page`/`limit`/filters — frontend must stop loading all bills |
| 5 | **Patients — server date filter** | `GET /opd/patients` | Add registration-date filter on backend so frontend does not `fetchAll` for Yesterday/Custom |
| 6 | **Dashboard bed stats** | `GET /opd/dashboard` | Use `ward_bed_stats` from response (backend done; frontend wiring) |
| 7 | **Beds — server filters** | `GET /opd/beds` | Pass `ward`, `status`, `search` from UI; optional SQL pagination later |
| 8 | **Expand Phase 1 doc** | This file | Document all built APIs not yet listed here (patients CRUD, bills, payments, appointments, beds) |
| 9 | **Tests** | `tests/` | Appointments filters, bills pagination, invoice with settings |

### Frontend — Phase 2 (separate developer)

| Screen | Change |
|--------|--------|
| Appointments list | Wire `page`/`limit`/`list_filter` to `GET /opd/appointments`; remove local pagination |
| Billing list | Wire `GET /opd/bills?page=&limit=`; remove `fetchAll` |
| Patient list | Server date filter; remove `fetchAll` for date tabs |
| Register / bill forms | Pre-fill fees from settings defaults |
| Invoice / print | Show hospital name/GST from settings |
| Dashboard | Use `ward_bed_stats` from API |

### Phase 2 — Out of scope

- Multi-hospital settings
- Clinical waiting-room queue (receptionist module — [receptionist.md](./receptionist.md))
- Changing historical bill amounts from settings (defaults apply to **new** visits only)

### Phase 2 — Suggested order

```
1. Hospital settings → invoice + default fees (backend)
2. Frontend wire appointments + billing pagination
3. Patient list server date filter (backend + frontend)
4. Dashboard + beds polish
5. Tests + expand Phase 1 API list in this doc
```

### Related Phase 2 docs

- Hospital settings: [hospital-settings.md](./hospital-settings.md)
- Super Admin settings API: [super-admin.md](./super-admin.md)
