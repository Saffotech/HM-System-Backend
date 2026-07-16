# Nurse — Shift Handover (`nurse`)

Outgoing nurse summarizes patient condition, pending tasks, and warnings for the incoming nurse during shift change.

**Word file:** View 7 — Shift Handover (`_extracted_fields_requirements.txt`)

**Phase 1 doc:** [nurse.md](./nurse.md)

**Depends on (must exist first):**
- `/nurse/vitals`, `/nurse/notes`, `/nurse/queue/today`
- `/nurse/medications` (medication pending list)
- `/opd/beds` (ward / bed)
- Doctor `/prescriptions` (doctor instructions)

---

## Permissions

```
nurse_handover:view
nurse_handover:create
nurse_handover:update
nurse_handover:submit
nurse_handover:take_over
```

Assigned to role `nurse` in `seed.py`.

---

## APIs (built)

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | Create handover | POST | `/nurse/handover` |
| 2 | Add patient summary | POST | `/nurse/handover/{handover_id}/patients` |
| 3 | Submit handover | PUT | `/nurse/handover/{handover_id}/submit` |
| 4 | List handovers | GET | `/nurse/handover` |
| 5 | Take over | PUT | `/nurse/handover/{handover_id}/take-over` |
| 6 | Detail | GET | `/nurse/handover/{handover_id}` |
| 7 | Update handover | PUT | `/nurse/handover/{handover_id}` |
| 8 | Update patient row | PUT | `/nurse/handover/patients/{patient_summary_id}` |
| 9 | Delete patient row | DELETE | `/nurse/handover/patients/{patient_summary_id}` |
| 5 | Handover detail | GET | `/nurse/handover/{handover_id}` |
| 6 | Incoming nurse acknowledge | PUT | `/nurse/handover/{handover_id}/acknowledge` |
| 7 | Mark shift complete | PUT | `/nurse/handover/{handover_id}/complete` |

Build **create + patient summary + submit first**. Then list, detail, acknowledge, complete.

---

## Create handover (Word file View 7)

**POST** `/nurse/handover`

| Field | Required | Example |
|-------|----------|---------|
| incoming_nurse_id | Yes | 8 |
| ward_name | Yes | General Ward A |
| department_id | No | 1 |
| shift_date | No | 2026-06-08 |
| shift_start | No | 08:00 |
| shift_end | No | 16:00 |
| general_notes | No | Busy shift |

| Field (auto) | Source |
|--------------|--------|
| shift_id / handover_uid | Auto-generated unique ID |
| outgoing_nurse | Logged-in nurse (from token) |
| shift_date_time | Auto now if shift_date not sent |
| status | `pending` on create |

**Word file fields covered:**

| Word field | API field |
|------------|-----------|
| Shift ID | `handover_uid` |
| Outgoing Nurse | `outgoing_nurse_id` (from token) |
| Incoming Nurse | `incoming_nurse_id` |
| Ward / Unit | `ward_name` |
| Shift Date & Time | `shift_date`, `shift_start`, `shift_end` |
| Status | `status` |

---

## Add patient summary (Word file View 7)

**POST** `/nurse/handover/{handover_id}/patients`

| Field | Required | Example |
|-------|----------|---------|
| patient_id | Yes | 12 |
| bed_number | No | B-12 |
| ward_name | No | General Ward A |
| patient_summary | No | Stable post-op, alert vitals |
| pending_tasks | No | Vitals at 6 PM, wound dressing |
| critical_alerts | No | Low SpO2 — monitor hourly |
| medication_pending | No | Paracetamol 8 PM dose pending |
| doctor_instructions | No | NPO until doctor review |

| Field (auto) | Source |
|--------------|--------|
| patient_name | From `patients` table |

**Word file fields covered:**

| Word field | API field |
|------------|-----------|
| Patient Summary | `patient_summary` |
| Pending Tasks | `pending_tasks` |
| Critical Alerts | `critical_alerts` |
| Medication Pending | `medication_pending` |
| Doctor Instructions | `doctor_instructions` |

**Optional helper (service layer):**
- Pull `medication_pending` from `GET /nurse/medications/patient/{patient_id}`
- Pull `critical_alerts` from `GET /nurse/alerts?patient_id=` (after emergency alerts module is built)

---

## Submit handover

**PUT** `/nurse/handover/{handover_id}/submit`

No body.

- `status` → `submitted`
- `submitted_at` = auto now

**Frontend action buttons (Word file):**
- Submit Handover
- Print Summary → use `GET /nurse/handover/{handover_id}`
- Mark Shift Complete → `PUT /nurse/handover/{handover_id}/complete`

---

## List handovers

**GET** `/nurse/handover`

| Query | Description |
|-------|-------------|
| ward_name | Filter by ward |
| status | pending / submitted / completed |
| shift_date | YYYY-MM-DD |
| outgoing_nurse_id | Outgoing nurse user id |
| incoming_nurse_id | Incoming nurse user id |
| page | Default 1 |
| limit | Default 20 |

---

## Handover detail (print summary)

**GET** `/nurse/handover/{handover_id}`

Returns header + `patients[]` with all summary fields and nurse names.

**Response example:**
```json
{
  "handover_id": 1,
  "handover_uid": "HO-2026-001",
  "outgoing_nurse": "Priya Sharma",
  "incoming_nurse": "Anita Verma",
  "ward_name": "General Ward A",
  "shift_date": "2026-06-08",
  "shift_start": "08:00",
  "shift_end": "16:00",
  "status": "submitted",
  "patients": [
    {
      "patient_id": 12,
      "patient_name": "Ravi Kumar",
      "bed_number": "B-12",
      "patient_summary": "Stable",
      "pending_tasks": "Vitals at 6 PM",
      "critical_alerts": "None",
      "medication_pending": "Paracetamol 8 PM",
      "doctor_instructions": "Monitor BP"
    }
  ]
}
```

---

## Acknowledge handover (incoming nurse)

**PUT** `/nurse/handover/{handover_id}/acknowledge`

| Field | Required |
|-------|----------|
| acknowledgement_notes | No |

- Logged-in nurse must match `incoming_nurse_id`
- `acknowledged_at` = auto now

---

## Mark shift complete

**PUT** `/nurse/handover/{handover_id}/complete`

- `status` → `completed`
- `completed_at` = auto now

---

## Tables to create

### shift_handovers
```
id, handover_uid (unique),
outgoing_nurse_id (user id), incoming_nurse_id (user id),
department_id, ward_name,
shift_date, shift_start, shift_end,
general_notes,
status (pending / submitted / completed),
submitted_at, acknowledged_at, completed_at,
created_at, updated_at
```

### shift_handover_patients
```
id, handover_id, patient_id,
bed_number, ward_name,
patient_summary, pending_tasks,
critical_alerts, medication_pending,
doctor_instructions,
created_at
```

---

## Status flow

```
pending → submitted → completed
              ↓
        acknowledged (incoming nurse)
```

---

## Register in main.py

```python
from Routers.nurse_handover_router import router as nurse_handover_router
app.include_router(nurse_handover_router)
```

---

## Checklist before you say "done"

- [ ] Permissions in seed + assigned to `nurse`
- [ ] Tables `shift_handovers`, `shift_handover_patients` exist
- [ ] Create, submit, list, detail work in `/docs`
- [ ] Only nurse role can create; incoming nurse can acknowledge
- [ ] Wrong role gets 403
