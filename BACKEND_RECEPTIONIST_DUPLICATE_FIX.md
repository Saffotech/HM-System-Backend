# Backend Fix — Receptionist Dashboard: Duplicate Appointments & Wrong Statistics

**Status:** Documentation only — not implemented  
**Audience:** Backend developers  
**Date:** July 2026  
**Rule:** Backend must be the single source of truth. Do not fix with frontend deduplication.

---

## 1. Executive summary

The Receptionist Dashboard shows **wrong scheduled counts** (e.g. 90 instead of 2) and **duplicate patient rows** (same patient twice with different times). OPD Billing shows the correct appointments (1:00 PM, 1:30 PM) because it uses a different API.

This document explains **why** it happens, **which files** to change, and **how** to fix it in three phases.

| Phase | Scope | Fixes |
|-------|--------|--------|
| **A** | Receptionist only | Correct counts, one queue row per patient, `scheduled_at` in API |
| **B** | OPD registration | Stop creating duplicate appointments at source |
| **C** | One-time cleanup | Cancel existing duplicate rows in database |

**If you must touch receptionist only first:** implement **Phase A + Phase C**. Phase B is a separate OPD change.

---

## 2. Symptoms (what users see)

### 2.1 Dashboard stat cards wrong

| Card | User sees | Expected |
|------|-----------|----------|
| Scheduled | 90 | 2 (Abhay + Aman) |
| Completed | 0 | 0 |
| Cancelled | 0 | 0 |

**API:** `GET /receptionist/dashboard`  
**Field mapped to Scheduled in UI:** `data.todays_paid_appointments`

### 2.2 Today's Patients table — duplicates

| Patient | Time shown | Problem |
|---------|------------|---------|
| Abhay P-1024 | 11:55 AM | Walk-in created at registration |
| Abhay P-1024 | — or wrong | Second duplicate row |
| Aman P-1025 | 02:14 PM | Check-in time, not slot 1:30 PM |

**API:** `GET /receptionist/today-queue`

### 2.3 OPD Billing dashboard (correct reference)

| Patient | Time | Status |
|---------|------|--------|
| Abhay | 1:00 PM | Scheduled |
| Aman | 1:30 PM | Scheduled |

**API:** `GET /opd/appointments` (different module — has `scheduled_at`)

---

## 3. Root cause analysis

### 3.1 Duplicate appointments in database

**Current OPD registration flow** (`opd_service.py` → `register_new_patient`):

```text
POST /opd/patient/register
        │
        ▼
create_visit()                    → opd_visits row
        │
        ▼
create_walk_in_appointment()      → appointment at NOW (e.g. 11:55 AM)
        │
        ▼
_finalize_visit_appointment_and_queue()
        │
        ▼
Frontend (workaround)             → PATCH reschedule OR POST /opd/appointments
        │
        ▼
TWO appointment rows OR one updated + one orphan
```

**Relevant code today** (`HM-Backend/Services/opd_service.py` ~line 221):

```python
apt = appointment_service.create_walk_in_appointment(
    db,
    patient_id=patient.id,
    doctor_id=data.doctor_id,
    department_id=data.department_id,
    created_by=registered_by,
)
```

`create_walk_in_appointment()` sets `scheduled_at = now_ist()` — not the user-selected slot.

### 3.2 Inflated SQL counts

**Dashboard today** (`receptionist_service.py` → `get_dashboard` ~line 222):

```python
paid_appointments = _todays_appointments_query(..., payment_filter="paid")
return {
    "todays_paid_appointments": paid_appointments.count(),  # ← problem
}
```

`_todays_appointments_query()` uses `_receptionist_appointments_query()` which **JOINs**:

- `Appointment` → `Patient`
- `OpdVisit` (latest per appointment)
- `PatientQueue` (outer join on appointment + queue_date)
- `User`, `Department`

When duplicate appointments exist **or** joins multiply rows, `.count()` returns **joined row count**, not **distinct appointment count**.

### 3.3 Missing `scheduled_at` in queue API

`_appointment_row_to_dict()` (~line 67) returns:

- `checked_in_at` ✓
- `consultation_started_at` ✓
- **`scheduled_at` ✗ missing**

Frontend (`receptionist.js`) tries `row.scheduled_at` first; when absent it shows `—` or wrongly uses check-in time.

`QueueItemOut` in `Schemas/receptionist_schema.py` also has no `scheduled_at` field — FastAPI strips it even if added to dict.

### 3.4 Cause chain diagram

```text
                    ┌─────────────────────────┐
                    │  OPD Register + Book    │
                    │  (2 appointment rows)   │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │ Dashboard count │ │ Today queue  │ │ Doctor dashboard │
    │ inflated (90)   │ │ dup patients │ │ reports wrong    │
    └─────────────────┘ └──────────────┘ └──────────────────┘
```

---

## 4. Business rules (target behavior)

1. **One active appointment** per patient + doctor + calendar day (IST).
2. **Completed** — show when consultation finished (`appointment.status = completed`).
3. **Cancelled** — show when staff cancelled (`appointment.status = cancelled`).
4. **Scheduled** — paid, not completed, appointment day is today.
5. **Queue time** — display `appointment.scheduled_at` (booked slot), not `checked_in_at`.
6. **Past appointments** — if not completed/cancelled, auto-cancel when day passes (separate optional task in `appointment_service.py`).

---

## 5. Phase A — Receptionist module only

### 5.1 Files to change

| File | Change |
|------|--------|
| `Services/receptionist_service.py` | Canonical appointment logic + fix `get_dashboard`, `get_today_queue`, `get_doctor_queue` |
| `Schemas/receptionist_schema.py` | Add `scheduled_at: Optional[datetime]` to `QueueItemOut` |
| `tests/test_receptionist_canonical.py` | New tests |

### 5.2 Step 1 — Add `scheduled_at` to API response

**File:** `Services/receptionist_service.py`  
**Function:** `_appointment_row_to_dict()`

Add to returned dict:

```python
"scheduled_at": appointment.scheduled_at,
```

**File:** `Schemas/receptionist_schema.py`  
**Class:** `QueueItemOut`

```python
scheduled_at: Optional[datetime] = None
```

Place after `payment_status`, before `checked_in_at`.

### 5.3 Step 2 — Base query without join inflation

Add helper (appointment table only — no PatientQueue join for counting):

```python
def _base_appointments_for_day_query(
    db: Session,
    *,
    target_date: date,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
):
    range_start = datetime.combine(target_date, time.min, tzinfo=IST)
    range_end = range_start + timedelta(days=1)
    q = (
        db.query(Appointment)
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at < range_end,
            Appointment.status != AppointmentStatus.cancelled,
        )
    )
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if department_id is not None:
        q = q.join(User, Appointment.doctor_id == User.id).filter(
            User.department_id == department_id
        )
    return q.order_by(Appointment.scheduled_at.asc(), Appointment.id.asc())
```

### 5.4 Step 3 — Canonical deduplication

**Group key:** `(patient_id, doctor_id, scheduled_date_in_IST)`

**Pick one appointment per group** using rank (highest wins):

1. Has linked `OpdVisit` with `payment_status = paid`
2. Has any linked `OpdVisit`
3. Latest `scheduled_at` (slot 1:00 PM beats walk-in 11:55 AM)
4. Highest `appointment.id`

**Pseudocode:**

```python
def pick_canonical_appointment(group: list[Appointment], visit_by_apt_id: dict) -> Appointment:
    def rank(apt):
        visit = visit_by_apt_id.get(apt.id)
        paid = 1 if visit and visit.payment_status == "paid" else 0
        linked = 1 if visit else 0
        ts = apt.scheduled_at.astimezone(IST).timestamp() if apt.scheduled_at else 0
        return (paid, linked, ts, apt.id)
    return max(group, key=rank)
```

**Example — Abhay on 10 Jul 2026:**

| apt_id | scheduled_at | visit linked | Keep? |
|--------|--------------|--------------|-------|
| 101 | 11:55 AM | yes (walk-in) | No |
| 102 | 1:00 PM | yes (paid) | **Yes** |

### 5.5 Step 4 — Fix `get_dashboard()`

Replace `.count()` on joined queries with counts from **canonical list**:

```python
def get_dashboard(db: Session, *, doctor_id: Optional[int] = None) -> dict:
    canonical, visit_map = _canonical_today_appointments(db, doctor_id=doctor_id)

    completed = paid_active = unpaid_active = 0
    for apt in canonical:
        if apt.status == AppointmentStatus.completed:
            completed += 1
            continue
        visit = visit_map.get(apt.id)
        if visit and is_visit_paid(visit):
            paid_active += 1
        else:
            unpaid_active += 1

    return {
        "total_patients": len(canonical),
        "completed": completed,
        "todays_paid_appointments": paid_active,      # UI "Scheduled"
        "todays_unpaid_appointments": unpaid_active,  # UI "Pending"
        "todays_cancelled": _count_cancelled_today(db, doctor_id),
    }
```

### 5.6 Step 5 — Fix `get_today_queue()`

1. Load canonical appointments (with filters: status, payment, search).
2. Paginate in Python: `canonical[start:start+limit]`.
3. For each page row, load patient/doctor/queue and build dict via `_appointment_row_to_dict()`.

**Do not** paginate the joined SQL query directly — duplicates break page totals.

### 5.7 Step 6 — Fix `get_doctor_queue()` (same pattern)

Use `_canonical_appointments_for_day(db, target_date=..., doctor_id=...)` instead of raw `_receptionist_appointments_query().count()`.

### 5.8 Frontend after Phase A

No deduplication needed. `receptionist.js` already formats `row.scheduled_at` when present:

```javascript
if (row.scheduled_at) {
  return formatTime(row.scheduled_at);
}
```

Remove any temporary `dedupeReceptionistQueue` client code if it exists.

---

## 6. Phase B — Stop new duplicates (OPD — separate PR)

> **Coordinate with OPD team.** Touches registration, not receptionist-only.

### 6.1 Files

| File | Change |
|------|--------|
| `Schemas/opd_schema.py` | `scheduled_at: Optional[datetime]` on `PatientRegisterRequest`, `OpdVisitCreate` |
| `Services/appointment_service.py` | New `resolve_appointment_for_visit()` |
| `Services/opd_service.py` | Use resolve in `register_new_patient()` |
| `Services/queue_enqueue_service.py` | Skip enqueue for future slots; use resolve not walk-in |

### 6.2 `resolve_appointment_for_visit()` logic

```text
IF appointment_id provided
    → validate and return that appointment

ELSE find active appointments same patient + doctor + department + day

IF found
    → update scheduled_at to requested slot
    → return existing row

ELSE
    → create new Appointment at scheduled_at
```

### 6.3 Register request body (after fix)

```json
{
  "first_name": "Abhay",
  "doctor_id": 2,
  "department_id": 1,
  "scheduled_at": "2026-07-10T13:00:00+05:30",
  "registration_fee": 200,
  "consultation_fee": 800
}
```

**One** appointment at 1:00 PM. No second `POST /opd/appointments`.

### 6.4 Queue enqueue rule

In `enqueue_after_payment_if_eligible()`:

```python
if appointment.scheduled_at > now_ist():
    return None  # future slot stays "scheduled", not "waiting"
```

---

## 7. Phase C — Clean existing bad data

### 7.1 New files

| File | Purpose |
|------|---------|
| `Services/appointment_integrity_service.py` | `cleanup_duplicate_active_appointments()` |
| `Scripts/cleanup_duplicate_appointments.py` | Run once after deploy |

### 7.2 Cleanup algorithm

```text
FOR each group (patient_id, doctor_id, day) with 2+ active appointments:
    keep = pick_canonical_appointment(group)
    FOR each other apt in group:
        apt.status = cancelled
        apt.notes += "[auto-cancelled: duplicate appointment]"
    COMMIT
```

### 7.3 Run command

```bash
cd HM-Backend
python Scripts/cleanup_duplicate_appointments.py
```

**Run after Phase A deploy** so dashboard immediately shows correct data for existing patients.

---

## 8. API reference (after fix)

### 8.1 `GET /receptionist/dashboard`

**Permission:** `opd:view`  
**Router:** `Routers/receptionist_router.py` line 24

**Response:**

```json
{
  "success": true,
  "data": {
    "total_patients": 2,
    "completed": 0,
    "todays_paid_appointments": 2,
    "todays_unpaid_appointments": 0,
    "todays_cancelled": 0
  }
}
```

| Field | UI mapping |
|-------|------------|
| `todays_paid_appointments` | Scheduled pill |
| `todays_unpaid_appointments` | Pending (if shown) |
| `completed` | Completed pill |
| `todays_cancelled` | Cancelled pill |

### 8.2 `GET /receptionist/today-queue`

**Query params:** `doctor_id`, `department_id`, `status`, `payment_status`, `search`, `page`, `limit`

**Response row (each patient once):**

```json
{
  "appointment_id": 102,
  "patient_uid": "P-1024",
  "patient_name": "Abhay",
  "doctor_name": "Dr. Amaresh Maurya",
  "department_name": "General Medicine",
  "scheduled_at": "2026-07-10T13:00:00+05:30",
  "status": "scheduled",
  "payment_status": "paid",
  "checked_in_at": null
}
```

---

## 9. Tests to add

### 9.1 `tests/test_receptionist_canonical.py`

```python
def test_dedupe_prefers_paid_slot_appointment(db):
    # Create walk-in 11:55 + slot 13:00 for same patient
    # Link paid visit to slot appointment
    # assert canonical list has length 1
    # assert kept appointment is 13:00 slot

def test_dashboard_counts_match_canonical(db):
    # 2 patients, 1 duplicate for patient A
    # assert todays_paid_appointments == 2

def test_today_queue_single_row_per_patient(db):
    # assert Abhay appears once
    # assert scheduled_at is not null

def test_cleanup_cancels_duplicate(db):
    # run cleanup
    # assert walk-in status == cancelled
```

### 9.2 `tests/test_register_single_appointment.py` (Phase B)

```python
def test_register_with_scheduled_at_creates_one_appointment(db):
    # POST register body with scheduled_at
    # assert exactly 1 appointment row for patient today
```

---

## 10. Verification checklist (manual QA)

After Phase A + C deploy:

- [ ] Receptionist Dashboard → Scheduled = **2** (not 90)
- [ ] Today's Patients → **one** Abhay row
- [ ] Abhay time = **1:00 PM** (from `scheduled_at`)
- [ ] Aman time = **1:30 PM**
- [ ] OPD Appointments list still shows same 2 rows
- [ ] No frontend dedupe code active

After Phase B:

- [ ] New patient register + slot → **one** DB appointment row
- [ ] No second appointment at registration time

---

## 11. What NOT to do

| Wrong approach | Why |
|--------------|-----|
| Frontend dedupe in `receptionistQueueUtils.js` | Hides symptom; other APIs still wrong |
| Frontend recount dashboard stats | Backend and reports stay inconsistent |
| `DISTINCT` only in SQL without business pick | Still returns 2 rows for Abhay |
| Show `checked_in_at` as appointment time | Wrong time (11:55 vs 1:00) |

---

## 12. File checklist

### Phase A — Receptionist only

```
[ ] HM-Backend/Services/receptionist_service.py
    [ ] _base_appointments_for_day_query()
    [ ] _canonical_appointments_for_day()
    [ ] pick_canonical_appointment() / dedupe helper
    [ ] get_dashboard() — count canonical
    [ ] get_today_queue() — paginate canonical
    [ ] get_doctor_queue() — paginate canonical
    [ ] _appointment_row_to_dict() — add scheduled_at

[ ] HM-Backend/Schemas/receptionist_schema.py
    [ ] QueueItemOut.scheduled_at

[ ] HM-Backend/tests/test_receptionist_canonical.py
```

### Phase B — OPD (separate approval)

```
[ ] HM-Backend/Schemas/opd_schema.py
[ ] HM-Backend/Services/appointment_service.py
[ ] HM-Backend/Services/opd_service.py
[ ] HM-Backend/Services/queue_enqueue_service.py
[ ] HM-Backend/tests/test_register_single_appointment.py
```

### Phase C — Cleanup

```
[ ] HM-Backend/Services/appointment_integrity_service.py
[ ] HM-Backend/Scripts/cleanup_duplicate_appointments.py
```

---

## 13. Related documentation

| Document | Topic |
|----------|--------|
| `BACKEND_CHANGES_REQUIRED.md` | OPD duplicate appointment at register (broader) |
| `HM-Frontend/src/features/receptionist/BACKEND_GAPS.md` | Frontend gaps list |
| `Docs/flows/receptionist-module.md` | Receptionist API overview |

---

## 14. Contact / ownership

| Area | Owner |
|------|--------|
| Receptionist dashboard fix | Backend — Phase A |
| OPD registration fix | Backend — Phase B (OPD billing team) |
| Data cleanup | Backend / DBA — Phase C |
| Frontend | No changes after Phase A (remove workarounds only)
