# Nurse (`nurse`)

Nurse records vitals, nursing notes, helps with patient care. Does **not** do billing or prescriptions.

**Source:** `_extracted_fields_requirements.txt` (Word file: `Fieds and Requirements.docx`)

---

## Permissions (already in seed)

```
patients:view, opd:view, lab:view
```

**Add when you build nurse APIs:**

```
vitals:create, vitals:view
nursing_notes:create, nursing_notes:view
medications:create, medications:view
handover:create, handover:view, handover:update
emergency_alerts:create, emergency_alerts:view, emergency_alerts:update, emergency_alerts:escalate
```

---

## Register nurse user

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password, role_id | Yes |
| department_id | **Yes** — ward/department |

**Profile fields (not same as doctor):**

| Field | Required |
|-------|----------|
| phone | Yes |
| nursing_license_no | Yes |
| qualification | Yes — e.g. BSc Nursing |

---

## Phase 1 — APIs (built)

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | Today's queue | GET | `/nurse/queue/today` |
| 2 | Record vitals | POST | `/nurse/vitals` |
| 3 | Vitals history | GET | `/nurse/vitals/patient/{patient_id}` |
| 4 | Add nursing note | POST | `/nurse/notes` |
| 5 | List notes | GET | `/nurse/notes/patient/{patient_id}` |

---

## Phase 2 — APIs

| Module | Status | Doc |
|--------|--------|-----|
| Medication administration | Done | `/nurse/medications` |
| Shift handover | To build | [nurse-handover.md](./nurse-handover.md) |
| Emergency alerts | To build | [nurse-emergency-alerts.md](./nurse-emergency-alerts.md) |

---

## Record vitals (Word file View 4)

**POST** `/nurse/vitals`

| Field | Required | Example |
|-------|----------|---------|
| patient_id | Yes | 1 |
| temperature | No | 98.6 |
| blood_pressure | No | 120/80 |
| heart_rate | No | 72 |
| respiratory_rate | No | 18 |
| oxygen_saturation | No | 98 |
| blood_sugar | No | |
| weight | No | |
| pain_level | No | 1–10 |
| observation_notes | No | text |
| status | No | recorded / reviewed |

`recorded_by` = logged-in nurse (from token).  
`recorded_at` = auto now.

---

## Nursing note (Word file View 6)

**POST** `/nurse/notes`

| Field | Required |
|-------|----------|
| patient_id | Yes |
| symptoms | No |
| treatment_response | No |
| additional_notes | No |

---

## Medication administration (Word file View 5) — Done

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | Medication patients list | GET | `/nurse/medications/patients` |
| 2 | Patient medications | GET | `/nurse/medications/patient/{patient_id}` |
| 3 | Administer medication | POST | `/nurse/medications/administer` |
| 4 | Update administration | PUT | `/nurse/medications/administer/{administration_id}` |
| 5 | Medication history | GET | `/nurse/medications/history` |
| 6 | Patient medication history | GET | `/nurse/medications/history/{patient_id}` |

---

## Tables (Phase 1)

### patient_vitals
```
id, patient_id, appointment_id, recorded_by (user id),
temperature, blood_pressure, heart_rate,
respiratory_rate, oxygen_saturation,
blood_sugar, weight, pain_level,
observation_notes, status, recorded_at
```

### nursing_notes
```
id, patient_id, nurse_id,
symptoms, treatment_response, additional_notes,
status, created_at
```

### medication_administrations
```
id, prescription_item_id, patient_id, administered_by,
medicine_name, dosage, frequency, bed_number, ward_name,
scheduled_time, status, remarks, administered_at
```

---

## Phase 2 docs (read next)

- [Shift Handover](./nurse-handover.md) — Word file View 7
- [Emergency Alerts](./nurse-emergency-alerts.md) — Word file View 8
