# Doctor (`doctor`)

Doctor sees patients, writes consultation, prescriptions, and lab orders.

---

## Permissions (already in seed)

```
patients:view, opd:view
prescriptions:create
lab:create, lab:view
appointments:view, appointments:create, appointments:update
```

---

## Register doctor user

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password, role_id | Yes |
| department_id | **Yes** — e.g. Cardiology |

**Profile fields to add later** (new columns or `doctor_profiles` table):

| Field | Example |
|-------|---------|
| qualification | MBBS, MD |
| registration_no | MH-12345 |
| consultation_fee | 800 |
| specialization | Cardiologist |

---

## APIs to build

| What | Method | URL | Permission |
|------|--------|-----|------------|
| Today's queue | GET | `/doctor/queue/today` | opd:view |
| Search patient | GET | `/doctor/patients?search=` | patients:view |
| Patient detail | GET | `/doctor/patients/{id}` | patients:view |
| Save consultation | POST | `/doctor/consultations` | new: consultations:create |
| Create prescription | POST | `/doctor/prescriptions` | prescriptions:create |
| List prescriptions | GET | `/doctor/prescriptions` | prescriptions:create |
| Order lab test | POST | `/doctor/lab-orders` | lab:create |
| List lab orders | GET | `/doctor/lab-orders` | lab:view |

---

## Consultation (Word file View 7)

**POST** `/doctor/consultations`

| Field | Type |
|-------|------|
| patient_id | int |
| visit_id | int (optional) |
| symptoms | text |
| diagnosis | text |
| treatment_plan | text |
| status | in_progress / completed |

---

## Prescription (Word file View 3)

**POST** `/doctor/prescriptions`

Header: patient_id, doctor_id (from token)

**Items** (list):

| Field | Example |
|-------|---------|
| medicine_name | Paracetamol |
| dosage | 500mg |
| frequency | Twice daily |
| duration_days | 5 |
| instructions | After food |

---

## Lab order (Word file View 4)

**POST** `/doctor/lab-orders`

| Field | Example |
|-------|---------|
| patient_id | 1 |
| test_name | CBC |
| test_category | Blood Test |
| priority | normal / urgent |

Status flow: `pending` → `in_progress` → `completed`

---

## Tables to create

### consultations
- patient_id, doctor_id, visit_id, symptoms, diagnosis, treatment_plan, status, created_at

### prescriptions + prescription_items
- prescription: patient_id, doctor_id, status, created_at
- items: medicine_name, dosage, frequency, duration_days, instructions

### lab_orders
- patient_id, doctor_id, test_name, test_category, priority, status, requested_at

### lab_results (lab tech uploads)
- lab_order_id, report_file, remarks, uploaded_by, completed_at

### lab_result_parameters (optional)
- parameter_name, value, unit, normal_range, flag (normal/low/high)

---

## Build order

1. Queue + view patient (read only)
2. Consultation save
3. Prescription
4. Lab order
