# Nurse — Emergency Alerts (`nurse`)

Critical patient monitoring. Alerts for dangerous vitals, overdue medication, or manual emergency raised by nurse.

**Word file:** View 8 — Emergency Alerts (`_extracted_fields_requirements.txt`)

Also used in:
- View 1 — Dashboard (Emergency Alerts, Critical Patients Alert)
- View 4 — Update Vitals (Mark Critical, Notify Doctor)

**Phase 1 doc:** [nurse.md](./nurse.md)

**Depends on (must exist first):**
- `/nurse/vitals`
- `/nurse/medications`
- `/nurse/queue/today`
- `/opd/beds` (ward / bed location)
- Doctor module (escalate to doctor)

---

## Permissions (add in seed.py)

**Already in seed:**
```
patients:view, opd:view, lab:view
```

**Add when you build emergency alert APIs:**
```
emergency_alerts:create, emergency_alerts:view, emergency_alerts:update, emergency_alerts:escalate
```

Assign all four to role `nurse`.

---

## APIs to build

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | List alerts | GET | `/nurse/alerts` |
| 2 | Dashboard summary | GET | `/nurse/alerts/summary` |
| 3 | Create manual alert | POST | `/nurse/alerts` |
| 4 | Alert detail | GET | `/nurse/alerts/{alert_id}` |
| 5 | Assign nurse | PUT | `/nurse/alerts/{alert_id}/assign` |
| 6 | Resolve alert | PUT | `/nurse/alerts/{alert_id}/resolve` |
| 7 | Escalate to doctor | PUT | `/nurse/alerts/{alert_id}/escalate` |

Build **list + create + resolve first**. Then auto-trigger from vitals/medications. Then escalate.

---

## List emergency alerts (Word file View 8)

**GET** `/nurse/alerts`

| Query | Description |
|-------|-------------|
| status | active / resolved (default: active) |
| severity | medium / high / critical |
| alert_type | low_bp / high_bp / high_fever / cardiac / low_spo2 / overdue_medication / manual / other |
| ward_name | Filter by ward |
| patient_id | Filter by patient |
| assigned_nurse_id | Filter by nurse |
| from_date | YYYY-MM-DD |
| to_date | YYYY-MM-DD |
| page | Default 1 |
| limit | Default 20 |

**Word file table columns:**

| Field | API field |
|-------|-----------|
| Alert ID | `alert_uid` |
| Patient Name | `patient_name` |
| Ward / Bed | `ward_name`, `bed_number` |
| Alert Type | `alert_type` |
| Triggered Time | `triggered_at` |
| Severity | `severity` |
| Current Status | `status` |
| Assigned Nurse | `assigned_nurse_name` |
| Action | View / Escalate |

**Frontend features (Word file):**
- Red highlight when `severity = critical`
- Sound notification (frontend only)
- Escalate to doctor button

---

## Dashboard summary (Word file View 1)

**GET** `/nurse/alerts/summary`

```json
{
  "active_total": 5,
  "critical_count": 2,
  "high_count": 2,
  "medium_count": 1,
  "unassigned_count": 1
}
```

Use on nurse dashboard for **Emergency Alerts** and **Critical Patients Alert** cards.

---

## Create manual alert

**POST** `/nurse/alerts`

| Field | Required | Example |
|-------|----------|---------|
| patient_id | Yes | 12 |
| alert_type | Yes | manual |
| severity | Yes | critical |
| title | No | Patient collapsed |
| description | No | Sudden dizziness, BP dropping |
| ward_name | No | General Ward A |
| bed_number | No | B-12 |
| vital_id | No | 45 |
| medication_administration_id | No | 10 |

| Field (auto) | Source |
|--------------|--------|
| alert_uid | Auto-generated unique ID |
| triggered_by | Logged-in nurse (from token) |
| triggered_at | Auto now |
| status | `active` |

**alert_type values:**
```
low_bp, high_bp, high_fever, cardiac, low_spo2,
overdue_medication, manual, other
```

**severity values:**
```
medium, high, critical
```

---

## Alert detail

**GET** `/nurse/alerts/{alert_id}`

Returns full alert + patient snapshot (name, patient_uid, ward, bed) + linked vital or medication if any.

---

## Assign nurse to alert

**PUT** `/nurse/alerts/{alert_id}/assign`

| Field | Required |
|-------|----------|
| assigned_nurse_id | Yes |

If omitted, assign to logged-in nurse.

---

## Resolve alert

**PUT** `/nurse/alerts/{alert_id}/resolve`

| Field | Required |
|-------|----------|
| resolution_notes | No |

- `status` → `resolved`
- `resolved_by` = logged-in nurse
- `resolved_at` = auto now

---

## Escalate to doctor

**PUT** `/nurse/alerts/{alert_id}/escalate`

| Field | Required |
|-------|----------|
| doctor_id | No (default: patient's assigned doctor) |
| escalation_notes | No |

- `escalated` = true
- `escalated_at` = auto now
- `escalated_to_doctor_id` = doctor user id
- Alert stays `active` until resolved

---

## Auto-trigger rules (service layer — no separate API)

Create alert automatically after save in vitals or medication services:

| Source | Rule | alert_type | severity |
|--------|------|------------|----------|
| Vitals | BP systolic < 90 or diastolic < 60 | low_bp | high |
| Vitals | BP systolic > 180 or diastolic > 120 | high_bp | high |
| Vitals | Temperature > 103°F (39.4°C) | high_fever | high |
| Vitals | SpO2 < 90 | low_spo2 | critical |
| Vitals | Heart rate < 50 or > 120 | cardiac | high |
| Vitals | Nurse marks critical on save | manual | critical |
| Medications | Status = missed and overdue | overdue_medication | medium |

Call from:
- `Services/nurse_patient_vitals_service.py` (after create/update)
- `Services/nurse_medication_administration_service.py` (after missed status)

---

## Tables to create

### emergency_alerts
```
id, alert_uid (unique),
patient_id,
alert_type, severity,
title, description,
ward_name, bed_number,
status (active / resolved),
triggered_by (user id), triggered_at,
assigned_nurse_id (user id),
resolved_by (user id), resolved_at, resolution_notes,
escalated (bool), escalated_at,
escalated_to_doctor_id (user id), escalation_notes,
vital_id (nullable),
medication_administration_id (nullable),
created_at, updated_at
```

---

## Status flow

```
active → resolved
   ↓
escalated (flag set; alert stays active until resolved)
```

---

## Links to other nurse modules

| Use case | API |
|----------|-----|
| Trigger from vitals | POST `/nurse/vitals` |
| Trigger from meds | POST `/nurse/medications/administer` |
| Patient location | `/opd/beds` or medication `ward_name` / `bed_number` |
| Handover critical list | GET `/nurse/alerts?status=active&ward_name=` |
| Dashboard count | GET `/nurse/alerts/summary` |

---

## Register in main.py

```python
from Routers.nurse_emergency_alerts_router import router as nurse_alerts_router
app.include_router(nurse_alerts_router)
```

---

## Checklist before you say "done"

- [ ] Permissions in seed + assigned to `nurse`
- [ ] Table `emergency_alerts` exists
- [ ] List, create, resolve work in `/docs`
- [ ] Auto-trigger fires on critical vitals
- [ ] Escalate sets doctor id
- [ ] Wrong role gets 403

---

## Later (Phase 3)

- Notifications center (View 11) — acknowledge / clear
- Doctor inbox for escalated alerts
- WebSocket / real-time push (optional)
