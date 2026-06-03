# Nurse (`nurse`)

Nurse records vitals, nursing notes, helps with patient care. Does **not** do billing or prescriptions.

---

## Permissions (already in seed)

```
patients:view, opd:view, lab:view
```

**Add when you build nurse APIs:**

```
vitals:create, vitals:view
nursing_notes:create, nursing_notes:view
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

## APIs to build

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | Today's OPD list (reuse) | GET | `/opd/queue/today` |
| 2 | Record vitals | POST | `/nurse/vitals` |
| 3 | Vitals history | GET | `/nurse/vitals/patient/{patient_id}` |
| 4 | Add nursing note | POST | `/nurse/notes` |
| 5 | List notes | GET | `/nurse/notes/patient/{patient_id}` |

Build **vitals first**. Medication and shift handover come later (need doctor prescriptions).

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
| status | No | normal / critical |

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

## Tables to create

### patient_vitals
```
id, patient_id, recorded_by (user id),
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

---

## Later (Phase 2)

- Medication administration (needs prescriptions table)
- Shift handover
- Emergency alerts

Do not start these until doctor prescriptions exist.
