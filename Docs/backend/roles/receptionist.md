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
opd:view
receptionist:view_doctor_schedule
```

## What receptionist sees

- All **non-cancelled** appointments for the selected date(s)
- **Paid** and **unpaid** (`pending` / `partial`) patients
- Optional filter: `payment_status=paid` or `payment_status=unpaid`
- Appointment `status` in list responses: **`scheduled`** or **`completed`** only (not queue workflow statuses)

Unpaid patients appear in receptionist lists but are **not** in the doctor's live queue until paid.

## APIs (view only)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/receptionist/dashboard` | `opd:view` |
| GET | `/receptionist/today-queue` | `opd:view` |
| GET | `/receptionist/doctor-queue/{doctor_id}` | `opd:view` |
| GET | `/receptionist/queue-history` | `opd:view` |
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
| *(omit)* | — | Both scheduled and completed |

Receptionist `status` is derived from `appointments.status`, not `patient_queue.status`.
Appointment and queue statuses are: `scheduled`, `completed`, `cancelled`, `no_show` only.

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
