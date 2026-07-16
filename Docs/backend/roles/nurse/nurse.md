# Nurse (`nurse`)

Nurse records vitals, nursing notes, medications, shift handovers, and emergency alerts.
Does **not** do billing or prescriptions.

---

## Permissions (seed)

```
patients:view
opd:view
lab:view
nurse_vitals:view|create|update
nurse_notes:view|create|update
nurse_medication:view|create|update
nurse_handover:view|create|update|submit|take_over
nurse_alerts:view|create|update|escalate
nurse_profile:view|update|upload_image|delete_image
notifications:view|update
```

> Note: alert permissions were renamed from `emergency_alerts:*` to `nurse_alerts:*`.
> Run alembic migration `u9v0w1x2y3z4` then `python seed.py`.

---

## Register nurse user

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password, role_id | Yes |
| department_id | **Yes** — ward/department |

---

## API map (current)

| Area | Method | URL | Permission |
|------|--------|-----|------------|
| Dashboard stats | GET | `/nurse/dashboard/stats` | `opd:view` |
| Today queue | GET | `/nurse/queue/today` | `opd:view` |
| Bed patients | GET | `/nurse/beds/patients` | `opd:view` |
| Bed summary | GET | `/nurse/beds/patients/summary` | `opd:view` |
| Patient overview | GET | `/nurse/patients/{id}/overview` | `patients:view` |
| Profile | GET/PUT | `/nurse/profile` | `nurse_profile:*` |
| Profile image | POST/DELETE | `/nurse/profile/image` | `nurse_profile:*` |
| Vitals create | POST | `/nurse/vitals` | `nurse_vitals:create` |
| Vitals update | PUT | `/nurse/vitals/{vital_id}` | `nurse_vitals:update` |
| Vitals list | GET | `/nurse/vitals` | `nurse_vitals:view` |
| Vitals search | GET | `/nurse/vitals/search` | `nurse_vitals:view` |
| Vital detail | GET | `/nurse/vitals/{vital_id}` | `nurse_vitals:view` |
| Notes create | POST | `/nurse/notes` | `nurse_notes:create` |
| Notes update | PUT | `/nurse/notes/{note_id}` | `nurse_notes:update` |
| Notes list | GET | `/nurse/notes` | `nurse_notes:view` |
| Notes search | GET | `/nurse/notes/search` | `nurse_notes:view` |
| Note detail | GET | `/nurse/notes/{note_id}` | `nurse_notes:view` |
| Med patients | GET | `/nurse/medications/patients` | `nurse_medication:view` |
| Patient meds | GET | `/nurse/medications/patient/{patient_id}` | `nurse_medication:view` |
| Administer | POST | `/nurse/medications/administer` | `nurse_medication:create` |
| Update admin | PUT | `/nurse/medications/administer/{id}` | `nurse_medication:update` |
| Med history | GET | `/nurse/medications/history` | `nurse_medication:view` |
| Patient history | GET | `/nurse/medications/history/{patient_id}` | `nurse_medication:view` |
| Handover create | POST | `/nurse/handover` | `nurse_handover:create` |
| Handover update | PUT | `/nurse/handover/{id}` | `nurse_handover:update` |
| Add patients | POST | `/nurse/handover/{id}/patients` | `nurse_handover:update` |
| Update patient row | PUT | `/nurse/handover/patients/{id}` | `nurse_handover:update` |
| Delete patient row | DELETE | `/nurse/handover/patients/{id}` | `nurse_handover:update` |
| Submit | PUT | `/nurse/handover/{id}/submit` | `nurse_handover:submit` |
| Take over | PUT | `/nurse/handover/{id}/take-over` | `nurse_handover:take_over` |
| Handover list | GET | `/nurse/handover` | `nurse_handover:view` |
| Handover detail | GET | `/nurse/handover/{id}` | `nurse_handover:view` |
| Alerts list | GET | `/nurse/alerts` | `nurse_alerts:view` |
| Alerts summary | GET | `/nurse/alerts/summary` | `nurse_alerts:view` |
| Alert create | POST | `/nurse/alerts` | `nurse_alerts:create` |
| Alert detail | GET | `/nurse/alerts/{id}` | `nurse_alerts:view` |
| Assign | PUT | `/nurse/alerts/{id}/assign` | `nurse_alerts:update` |
| Resolve | PUT | `/nurse/alerts/{id}/resolve` | `nurse_alerts:update` |
| Escalate | PUT | `/nurse/alerts/{id}/escalate` | `nurse_alerts:escalate` |
| Notifications | * | `/nurse/notifications` | `notifications:*` |

---

## Vitals / notes identity rules

- Provide **`appointment_id`** (OPD) **or** **`patient_id`** for a patient currently on an occupied bed (IPD).
- Responses include `patient_name`, `patient_uid`, and `bed_number` when available.
- Vitals update may set `status` to `recorded` / `reviewed`.
- Notes update may set `status` to `active` / `archived`.

---

## Module docs

- [Shift Handover](./nurse-handover.md)
- [Emergency Alerts](./nurse-emergency-alerts.md)
