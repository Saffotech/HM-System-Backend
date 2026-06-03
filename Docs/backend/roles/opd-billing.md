# OPD Billing (`opd_billing`)

**Word file name:** Billing Counter / OPD Front Desk

Staff at the front desk: register patients, take payment, manage OPD queue.

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

## Already built APIs

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

**GET** `/opd/queue/today`

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
