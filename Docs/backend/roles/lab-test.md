# Lab Test Module — Backend API Guide

**Roles:** `doctor` (orders tests), `lab_technician` (processes & uploads reports)

**Word file:** Lab Technician Views 1–5 (`_extracted_fields_requirements.txt`)

**Existing table:** `lab_test_orders` (doctor creates)

**Tables to add:** `lab_results`, `lab_result_parameters`

**Important naming:**

- Actual DB table = `lab_test_orders` (not `lab_orders`)
- Doctor API prefix = `/lab-tests` (already built)
- Lab technician API prefix = `/lab` (to build)

**Related docs:** [lab-technician.md](./lab-technician.md) (frontend flow), [doctor.md](./doctor.md)

---

## Permissions (add/update in seed.py)

**Already in seed:**

```
lab:view, lab:create
```

**Add new permissions:**

```
lab:update
lab:upload_report
```

**Role assignments:**

| Role | Permissions |
|------|-------------|
| `doctor` | `lab:create`, `lab:view` (already) |
| `lab_technician` | `lab:view`, `lab:update`, `lab:upload_report`, `patients:view` |
| `nurse` | `lab:view` (read-only later — optional) |
| `admin` | all |

**Add role to `roles_data` in seed.py:**

```python
"lab_technician": {
    "description": "Laboratory staff",
    "permissions": [
        "patients:view",
        "lab:view",
        "lab:update",
        "lab:upload_report",
    ]
}
```

---

## Status flow (single source of truth)

```
ordered
   → sample_collected   (lab tech)
   → processing         (lab tech)
   → completed          (lab tech uploads report)

ordered → cancelled    (doctor only, before sample collected)
```

| Status | Who sets it |
|--------|-------------|
| `ordered` | Doctor on create |
| `sample_collected` | Lab technician |
| `processing` | Lab technician |
| `completed` | Lab technician on report upload |
| `cancelled` | Doctor only (while `ordered`) |

---

# Part A — Doctor APIs (ALREADY BUILT)

**Router:** `Routers/doctor_lab_test_router.py`  
**Prefix:** `/lab-tests`  
**Model:** `Models/doctor_lab_test_order.py` → `LabTestOrder`  
**Service:** `Services/doctor_lab_test_service.py`

Register in `main.py` (already done).

---

## A.1 Create lab order

**POST** `/lab-tests`  
**Auth:** Bearer token  
**Permission:** `lab:create` (recommended — currently only `get_current_user`)

**Body:**

```json
{
  "appointment_id": 1,
  "test_name": "CBC",
  "category": "Blood Test",
  "priority": "Normal",
  "clinical_notes": "Routine check"
}
```

| Field | Required | Rules |
|-------|----------|-------|
| appointment_id | Yes | Must belong to logged-in doctor |
| test_name | Yes | 1–255 chars |
| category | Yes | e.g. Blood Test, Radiology, Urine |
| priority | No | Default `"Normal"` — use `Normal` / `Urgent` |
| clinical_notes | No | Max 500 chars |

**Auto-filled on create:**

- `patient_id`, `patient_name`, `patient_uhid` from appointment's patient
- `doctor_id` from token
- `status` = `ordered`

**Business rules:**

- Appointment must exist and `appointment.doctor_id == current_user.id`
- Duplicate blocked: same `appointment_id` + `test_name` if not cancelled → **400**

**Response 201:** `LabTestResponse` (full order object)

---

## A.2 List doctor's lab orders

**GET** `/lab-tests?search=&skip=0&limit=20`  
**Auth:** Bearer token

| Query | Description |
|-------|-------------|
| search | Patient name, UHID, test name, or numeric id/patient_id |
| skip | Offset (default 0) |
| limit | Page size (default 20) |

**Scope:** Only orders where `doctor_id == current_user.id`

**Response:** Array of `LabTestListResponse`

```json
[
  {
    "id": 1,
    "patient_id": 12,
    "patient_name": "Ravi Kumar",
    "patient_uhid": "P-1001",
    "test_name": "CBC",
    "category": "Blood Test",
    "status": "ordered",
    "created_at": "2026-06-08T10:00:00+05:30"
  }
]
```

---

## A.3 Update lab order (doctor)

**PUT** `/lab-tests/{test_id}`  
**Auth:** Bearer token

**Body (all optional):**

```json
{
  "test_name": "CBC Full",
  "category": "Blood Test",
  "priority": "Urgent",
  "clinical_notes": "Updated note"
}
```

**Rules:**

- Only own orders (`doctor_id` match)
- Only when `status == ordered`
- Else **400** "Only ordered tests can be updated"

---

## A.4 Cancel lab order (doctor)

**PATCH** `/lab-tests/{test_id}/cancel`  
**Auth:** Bearer token

**Rules:**

- Only own orders
- Only when `status == ordered`

**Response:**

```json
{ "message": "Lab test cancelled successfully" }
```

---

## A.5 Doctor APIs still missing (optional Phase 2)

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/lab-tests/{test_id}` | Single order detail |
| GET | `/lab-tests?status=completed` | Filter by status (add query param to service) |
| GET | `/lab-tests/{test_id}/report` | View uploaded report (after lab tech completes) |

---

# Part B — Lab Technician APIs (TO BUILD)

**Suggested folder structure:**

```
Models/
  lab_result.py              # lab_results + lab_result_parameters
Schemas/
  lab_order_schema.py        # lab tech list/detail
  lab_report_schema.py       # upload report + parameters
Services/
  lab_order_service.py
  lab_report_service.py
Routers/
  lab_router.py              # prefix /lab
```

Register in `main.py`:

```python
from Routers.lab_router import router as lab_router
app.include_router(lab_router)
```

---

## B.1 Dashboard stats

**GET** `/lab/dashboard`  
**Permission:** `lab:view`

**Response:**

```json
{
  "total_today": 15,
  "pending": 8,
  "sample_collected": 2,
  "processing": 1,
  "completed_today": 4,
  "urgent_pending": 2
}
```

**Logic:** Count from `lab_test_orders` where `created_at` date = today (IST).  
`urgent_pending` = `priority` ilike urgent AND status in (`ordered`, `sample_collected`, `processing`).

---

## B.2 List all lab orders (lab queue)

**GET** `/lab/orders`  
**Permission:** `lab:view`

| Query | Description |
|-------|-------------|
| status | `ordered`, `sample_collected`, `processing`, `completed`, `cancelled` |
| priority | `Normal`, `Urgent` |
| category | Blood Test, Radiology, etc. |
| search | Patient name, UHID, test name, order id |
| doctor_id | Filter by ordering doctor |
| from_date | YYYY-MM-DD (created_at) |
| to_date | YYYY-MM-DD |
| page | Default 1 |
| page_size | Default 20, max 100 |

**Word file View 2 columns:**

| Word field | API field |
|------------|-----------|
| Request ID | `id` |
| Patient Name | `patient_name` |
| Patient ID | `patient_id` / `patient_uhid` |
| Doctor Name | `doctor_name` (join `users`) |
| Test Name | `test_name` |
| Test Category | `category` |
| Priority | `priority` |
| Requested Date & Time | `created_at` |
| Status | `status` |

**Response:**

```json
{
  "total": 25,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 1,
      "appointment_id": 5,
      "patient_id": 12,
      "patient_name": "Ravi Kumar",
      "patient_uhid": "P-1001",
      "doctor_id": 2,
      "doctor_name": "Dr. Amit Kumar",
      "test_name": "CBC",
      "category": "Blood Test",
      "priority": "Urgent",
      "clinical_notes": "Fever 3 days",
      "status": "ordered",
      "created_at": "2026-06-08T09:00:00+05:30"
    }
  ]
}
```

**Default for pending screen:** `GET /lab/orders?status=ordered`

**Sort:** `priority` desc (Urgent first), then `created_at` asc

---

## B.3 Order detail

**GET** `/lab/orders/{order_id}`  
**Permission:** `lab:view`

Returns full order + doctor name + existing report if `status == completed`.

```json
{
  "id": 1,
  "patient_name": "Ravi Kumar",
  "patient_uhid": "P-1001",
  "doctor_name": "Dr. Amit Kumar",
  "test_name": "CBC",
  "category": "Blood Test",
  "priority": "Urgent",
  "clinical_notes": "Fever",
  "status": "sample_collected",
  "created_at": "...",
  "report": null
}
```

---

## B.4 Mark sample collected

**PATCH** `/lab/orders/{order_id}/sample-collected`  
**Permission:** `lab:update`

**Body (optional):**

```json
{
  "sample_collected_at": "2026-06-08T10:30:00+05:30"
}
```

**Rules:**

- Current status must be `ordered`
- Set `status` → `sample_collected`
- If `sample_collected_at` omitted → auto now (IST)

**Response:**

```json
{
  "message": "Sample marked as collected",
  "order_id": 1,
  "status": "sample_collected"
}
```

---

## B.5 Mark processing

**PATCH** `/lab/orders/{order_id}/processing`  
**Permission:** `lab:update`

**Rules:**

- Current status must be `sample_collected`
- Set `status` → `processing`

**Optional body:**

```json
{
  "test_performed_at": "2026-06-08T11:00:00+05:30"
}
```

---

## B.6 Upload report (Word file View 3)

**POST** `/lab/orders/{order_id}/report`  
**Permission:** `lab:upload_report`  
**Content-Type:** `multipart/form-data` OR `application/json` (MVP: JSON + file path string)

### Option A — JSON body (MVP, no file server yet)

```json
{
  "sample_collected_at": "2026-06-08T10:30:00+05:30",
  "test_performed_at": "2026-06-08T11:00:00+05:30",
  "report_file": "/uploads/lab/report-001.pdf",
  "remarks": "Within normal limits",
  "parameters": [
    {
      "parameter_name": "Hemoglobin",
      "value": "13.5",
      "unit": "g/dL",
      "normal_range": "12-16",
      "flag": "normal"
    },
    {
      "parameter_name": "WBC",
      "value": "11.2",
      "unit": "10^3/uL",
      "normal_range": "4-11",
      "flag": "high"
    }
  ]
}
```

| Field | Required |
|-------|----------|
| sample_collected_at | No |
| test_performed_at | No |
| report_file | No (path/URL after upload) |
| remarks | No |
| parameters | No (list, can be empty for radiology) |

**Parameter flag values:** `normal`, `low`, `high`

### Option B — Multipart (production)

| Part | Type |
|------|------|
| report_file | file (PDF, JPG, PNG) |
| data | JSON string with remarks, parameters, dates |

**Rules:**

- Order status must be `ordered`, `sample_collected`, or `processing` (not `cancelled` or already `completed`)
- Create row in `lab_results`
- Bulk insert `lab_result_parameters`
- Set order `status` → `completed`
- `uploaded_by` = logged-in lab technician id

**Response 201:**

```json
{
  "message": "Report uploaded successfully",
  "report_id": 1,
  "order_id": 1,
  "status": "completed"
}
```

---

## B.7 List completed reports (Word file View 4)

**GET** `/lab/reports`  
**Permission:** `lab:view`

| Query | Description |
|-------|-------------|
| search | Patient name, UHID, test name |
| from_date | uploaded date |
| to_date | uploaded date |
| page | |
| page_size | |

**Response items:**

| Field | Source |
|-------|--------|
| report_id | `lab_results.id` |
| order_id | `lab_test_order_id` |
| patient_name | from order |
| test_name | from order |
| uploaded_at | `lab_results.created_at` |
| uploaded_by_name | join users |
| status | `completed` |
| report_file | path/URL |

---

## B.8 Get single report

**GET** `/lab/reports/{report_id}`  
**Permission:** `lab:view`

Returns report header + `parameters[]` + linked order info (for View / Print).

---

## B.9 Re-upload report (optional)

**PUT** `/lab/reports/{report_id}`  
**Permission:** `lab:upload_report`

Replace file, remarks, parameters. Keep audit `updated_at`, `updated_by`.

---

# Part C — Tables

## C.1 `lab_test_orders` (EXISTS)

```
id, appointment_id, patient_id, patient_name, patient_uhid,
doctor_id, test_name, category, priority, clinical_notes,
status, created_at, updated_at
```

## C.2 `lab_results` (CREATE)

```
id,
lab_test_order_id (FK lab_test_orders.id, unique),
uploaded_by (FK users.id),
sample_collected_at,
test_performed_at,
report_file (string — path or URL),
remarks (text),
created_at,
updated_at
```

One report per order (`unique` on `lab_test_order_id`).

## C.3 `lab_result_parameters` (CREATE)

```
id,
lab_result_id (FK lab_results.id),
parameter_name (string, required),
value (string),
unit (string),
normal_range (string),
flag (enum: normal, low, high)
```

---

# Part D — Schemas to create

## `LabOrderListItem` (response)

```
id, appointment_id, patient_id, patient_name, patient_uhid,
doctor_id, doctor_name, test_name, category, priority,
clinical_notes, status, created_at
```

## `LabReportCreate` (request)

```
sample_collected_at, test_performed_at, report_file, remarks,
parameters: List[LabParameterCreate]
```

## `LabParameterCreate`

```
parameter_name, value, unit, normal_range, flag
```

## `LabReportResponse`

```
id, lab_test_order_id, uploaded_by, uploaded_by_name,
sample_collected_at, test_performed_at, report_file, remarks,
parameters[], created_at
```

---

# Part E — Service business rules

| Rule | Detail |
|------|--------|
| Doctor create | Appointment must belong to doctor |
| Doctor update/cancel | Only `status == ordered` |
| Lab sample collected | Only from `ordered` |
| Lab processing | Only from `sample_collected` |
| Lab upload report | Not `cancelled` or already `completed` |
| One report per order | Unique constraint on `lab_test_order_id` |
| Doctor name | Join `users` on `doctor_id` |
| Urgent first | Sort `priority` desc in lab list |
| Timezone | Use `Asia/Kolkata` like nurse module |

---

# Part F — APIs to build (checklist)

| Step | What | Method | URL | Permission |
|------|------|--------|-----|------------|
| 1 | Seed role + permissions | — | `seed.py` | — |
| 2 | Models + migration | — | Alembic | — |
| 3 | Dashboard stats | GET | `/lab/dashboard` | lab:view |
| 4 | List orders | GET | `/lab/orders` | lab:view |
| 5 | Order detail | GET | `/lab/orders/{id}` | lab:view |
| 6 | Sample collected | PATCH | `/lab/orders/{id}/sample-collected` | lab:update |
| 7 | Processing | PATCH | `/lab/orders/{id}/processing` | lab:update |
| 8 | Upload report | POST | `/lab/orders/{id}/report` | lab:upload_report |
| 9 | List reports | GET | `/lab/reports` | lab:view |
| 10 | Report detail | GET | `/lab/reports/{id}` | lab:view |
| 11 | (Optional) Doctor view report | GET | `/lab-tests/{id}/report` | lab:view |

Build order: **3 → 4 → 5 → 6 → 8 → 9 → 10**

---

# Part G — Register lab technician user

**POST** `/auth/register`

```json
{
  "first_name": "Suresh",
  "last_name": "Patel",
  "email": "lab@hospital.com",
  "password": "password123",
  "role_id": 6,
  "department_id": 10
}
```

Use `role_id` from `GET /roles/` after seed (Radiology department suggested).

---

# Part H — Protect endpoints

Use same pattern as OPD:

```python
from dependencies import get_current_user, PermissionChecker

@router.get("/orders")
def list_orders(
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    ...
```

---

# Part I — Do not build yet

- PACS / radiology machine integration
- Patient portal download
- Email/SMS report to patient
- Lab billing integration

---

# Part J — Checklist before you say "done"

- [ ] `lab_technician` role in seed with permissions
- [ ] Tables `lab_results`, `lab_result_parameters` exist
- [ ] `GET /lab/orders` returns all doctors' orders (not doctor-scoped)
- [ ] Status transitions enforced in service layer
- [ ] Upload creates report + sets order `completed`
- [ ] Doctor cannot cancel after `sample_collected`
- [ ] Works in `/docs` with lab tech token
- [ ] Wrong role gets 403
- [ ] Registered in `main.py`

---

# Part K — Quick reference: Doctor vs Lab URLs

| Action | Doctor | Lab technician |
|--------|--------|----------------|
| Create order | `POST /lab-tests` | — |
| List orders | `GET /lab-tests` (own only) | `GET /lab/orders` (all) |
| Update order | `PUT /lab-tests/{id}` | — |
| Cancel | `PATCH /lab-tests/{id}/cancel` | — |
| Sample collected | — | `PATCH /lab/orders/{id}/sample-collected` |
| Upload report | — | `POST /lab/orders/{id}/report` |
| View reports | (future) | `GET /lab/reports` |

---

## Build order (recommended)

1. Doctor lab orders must work first (done)
2. Seed `lab_technician` role + permissions
3. Create `lab_results` + `lab_result_parameters` models
4. Lab tech pending list (`GET /lab/orders`)
5. Status transitions (sample collected, processing)
6. Upload report (`POST /lab/orders/{id}/report`)
7. Completed reports list (`GET /lab/reports`)
