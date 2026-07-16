# Receptionist (`receptionist`)

Front desk **view-only** monitoring of appointments and the clinical queue. Queue rows are created automatically by OPD Billing after payment — receptionist does not create queue entries.

## Workflow

```
Patient arrives → OPD Billing (register / appointment / pay)
        ↓
Appointment created (paid or unpaid)
        ↓
Receptionist views all today's appointments (paid + unpaid)
        ↓
Payment completed → system auto-creates patient_queue row
        ↓
Doctor views GET /queue/today (paid patients in queue only)
```

## Permissions

```
patients:view
receptionist:view_queue
receptionist:view_doctor_schedule
```

## What receptionist sees

- By default, all **non-cancelled** appointments for the selected date(s) (use `status=cancelled` to view cancelled appointments)
- **Paid** and **unpaid** (`pending` / `partial`) patients
- Optional filter: `payment_status=paid` or `payment_status=unpaid`
- Appointment `status` in list responses: **`scheduled`**, **`completed`**, or **`cancelled`** (cancelled are hidden by default)

Unpaid patients appear in receptionist lists but are **not** in the doctor's live queue until paid.

## APIs (view only)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/receptionist/dashboard` | `receptionist:view_queue` |
| GET | `/receptionist/today-queue` | `receptionist:view_queue` |
| GET | `/receptionist/doctor-queue/{doctor_id}` | `receptionist:view_queue` |
| GET | `/receptionist/queue-history` | `receptionist:view_queue` |
| GET | `/receptionist/doctors/schedule` | `receptionist:view_doctor_schedule` |

### Payment filter (today-queue, doctor-queue, queue-history)

| Query param | Values | Description |
|-------------|--------|-------------|
| `payment_status` | `paid` | Only fully paid visits |
| `payment_status` | `unpaid` | `pending`, `partial`, or no visit row |
| *(omit)* | — | Both paid and unpaid |

### Appointment status filter (today-queue, doctor-queue, queue-history)

| Query param | Values | Description |
|-------------|--------|-------------|
| `status` | `scheduled` | Appointment not yet completed by doctor |
| `status` | `completed` | Doctor marked consultation completed |
| `status` | `cancelled` | Cancelled appointment |
| *(omit)* | — | Scheduled + completed only (cancelled are hidden by default) |

Receptionist `status` is derived from `appointments.status`, not `patient_queue.status`.
Doctor queue still uses `waiting`, `called`, `in_progress`, etc. internally.

### Canonicalization & ordering (today-queue / doctor-queue)
For the same patient with multiple appointments on the selected date, the API collapses to **one canonical row per patient** using:
paid visit > linked visit > latest `scheduled_at` > highest appointment id.

### GET `/receptionist/doctors/schedule`

View-only doctor availability. Required query: `date=YYYY-MM-DD`.

Optional: `doctor_id`, `department_id`, `search`, `page`, `page_size`.

## OPD Billing responsibilities

| Action | API |
|--------|-----|
| Register + bill + appointment | `POST /opd/patient/register` |
| Existing patient visit | `POST /opd/visit` (optional `appointment_id` for pre-booked) |
| Collect later payment → auto queue | `POST /opd/visit/{visit_id}/pay` |

After `payment_status` becomes `paid`, `queue_enqueue_service.enqueue_after_payment_if_eligible()` runs automatically.

## Code files

```
Services/queue_enqueue_service.py   # Auto-enqueue after payment
Services/opd_service.py             # Links visit ↔ appointment, triggers enqueue
Services/receptionist_service.py    # Appointment-based views + payment filter
Services/queue_helpers.py           # apply_receptionist_payment_filter
Services/doctor_patient_queue_service.py  # Doctor queue: paid only
Models/patient.py                   # OpdVisit.appointment_id
```
