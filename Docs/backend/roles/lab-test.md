# Lab Test Module — Backend API Guide

**Roles:** `doctor` (orders tests), `lab_technician` (processes & uploads reports)

**Word file:** Lab Technician Views 1–5 (`_extracted_fields_requirements.txt`)

**Existing table:** `lab_test_orders` (doctor creates)

**Tables:** `lab_test_orders` (doctor), `lab_results`, `lab_result_parameters` (lab tech)

**Important naming:**

- Actual DB table = `lab_test_orders` (not `lab_orders`)
- Doctor API prefix = `/lab-tests` (already built)
- Lab technician API prefix = `/lab` (built)

**Related docs:** [lab-technician.md](./lab-technician.md) (frontend flow), [doctor.md](./doctor.md)

---

## Permissions (add/update in seed.py)

**Already in seed:**

```
lab:view, lab:create, lab:update, lab:upload_report
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
        "lab:create",
        "lab:update",
        "lab:upload_report",
    ]
}
```

---

## Status flow (single source of truth)

```
ordered
   → sample_collected   (PATCH /lab/orders/{id}/sample-collected)
   → processing         (PATCH /lab/orders/{id}/processing)
   → completed          (PATCH /lab/orders/{id}/complete)

Parameters (optional):  POST /lab/orders/{id}/report
PDF file (optional):    POST /lab/orders/{id}/upload-file  (after completed)

ordered → cancelled    (doctor only, while ordered)
```

| Status | Who sets it |
|--------|-------------|
| `ordered` | Doctor on create |
| `sample_collected` | Lab technician |
| `processing` | Lab technician |
| `completed` | Lab technician (`PATCH .../complete`) |
| `cancelled` | Doctor only (while `ordered`) |

**Report types (`source` on history API):**

| source | Meaning |
|--------|---------|
| `PARAMETERS` | Numeric/text parameters only, no uploaded file |
| `PDF` | Uploaded file only, no parameters |
| `BOTH` | Parameters + uploaded file |
| `NONE` | Report row exists but empty (rare) |

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
| status | `ordered`, `sample_collected`, `processing`, `completed`, `cancelled` |
| skip | Offset (default 0) |
| limit | Page size (default 20, max 100) |

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
    "priority": "Normal",
    "status": "ordered",
    "created_at": "2026-06-08T10:00:00+05:30"
  }
]
```

**Example:** completed orders only → `GET /lab-tests?status=completed`

---

## A.2.1 Get single lab order (doctor)

**GET** `/lab-tests/{test_id}`  
**Permission:** `lab:view`

Returns full order for the logged-in doctor, including report summary if a report exists.

```json
{
  "id": 101,
  "appointment_id": 5,
  "patient_id": 12,
  "patient_name": "Ravi Kumar",
  "patient_uhid": "P-1001",
  "doctor_id": 2,
  "test_name": "CBC",
  "category": "Blood Test",
  "priority": "Urgent",
  "clinical_notes": "Fever",
  "status": "completed",
  "created_at": "...",
  "updated_at": "...",
  "report_uploaded": true,
  "has_report": true,
  "report": {
    "id": 5,
    "source": "BOTH",
    "file_name": "cbc.pdf",
    "remarks": "Within normal limits",
    "created_at": "..."
  }
}
```

For full parameters use `GET /lab-tests/{test_id}/report`.

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

## A.5 Doctor report history (BUILT)

Doctor can view lab reports only for orders they created (`lab_test_orders.doctor_id`).

| Method | URL | Permission | Purpose |
|--------|-----|------------|---------|
| GET | `/lab-tests/reports` | `lab:view` | Paginated report history with search/filters |
| GET | `/lab-tests/{test_id}/report` | `lab:view` | Report detail + parameters for one order |
| GET | `/lab-tests/{test_id}/report/file` | `lab:view` | Download PDF/image for one order |

### `GET /lab-tests/reports` query params

| Param | Description |
|-------|-------------|
| search | Patient name, UHID, test name, order id, patient id |
| patient_id | Filter by patient |
| patient_uhid | Partial UHID match |
| patient_name | Partial patient name |
| test_name | Partial test name |
| status | `ordered`, `sample_collected`, `processing`, `completed`, `cancelled` |
| source | `PARAMETERS`, `PDF`, `BOTH` |
| from_date / to_date | Report upload date (YYYY-MM-DD) |
| page / page_size | Pagination (max 100) |

**Response item fields:** `report_id`, `order_id`, `patient_name`, `patient_uhid`, `test_name`, `category`, `status`, `source`, `has_file`, `uploaded_at`, `uploaded_by_name`

### Example: completed CBC reports for a patient

```
GET /lab-tests/reports?patient_uhid=P-1001&status=completed&source=BOTH
```

### Example: open report with parameters

```
GET /lab-tests/101/report
```

### Example: download PDF

```
GET /lab-tests/101/report/file
```

**Security:** All three endpoints enforce `LabTestOrder.doctor_id == logged-in doctor`. Wrong doctor gets 404.

---

# Part B — Lab Technician APIs (BUILT)

**Router:** `Routers/lab_router.py`  
**Service:** `Services/lab_service.py`  
**Schemas:** `Schemas/lab_schema.py`  
**Models:** `Models/lab_result.py`

**Environment (optional):**

```
LAB_UPLOAD_DIR=uploads/lab_reports
```

Default upload directory. Files are stored on disk; DB stores a relative (or absolute) path plus `file_name`, `file_type`, `file_size`.

Registered in `main.py`.

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

Returns full order + doctor name + report summary if a report exists.

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
  "status": "processing",
  "created_at": "...",
  "report_uploaded": false,
  "report": {
    "id": 5,
    "report_file": null,
    "remarks": "Within normal limits",
    "created_at": "...",
    "file_name": null,
    "file_type": null,
    "file_size": null,
    "source": "PARAMETERS"
  }
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

## B.6 Create report (parameters / metadata)

**POST** `/lab/orders/{order_id}/report`  
**Permission:** `lab:upload_report`  
**Content-Type:** `application/json`

Saves parameters and optional metadata. Does **not** upload a binary file and does **not** set order to `completed`.

```json
{
  "sample_collected_at": "2026-06-08T10:30:00+05:30",
  "test_performed_at": "2026-06-08T11:00:00+05:30",
  "remarks": "Within normal limits",
  "parameters": [
    {
      "parameter_name": "Hemoglobin",
      "value": "13.5",
      "unit": "g/dL",
      "normal_range": "12-16",
      "flag": "normal"
    }
  ]
}
```

| Field | Required |
|-------|----------|
| sample_collected_at | No |
| test_performed_at | No |
| report_file | No (legacy string path only — prefer `upload-file` for PDFs) |
| remarks | No |
| parameters | No (at least one of `report_file` or `parameters` required) |

**Parameter flag values:** `normal`, `low`, `high`

**Rules:**

- Order must not be `cancelled`
- One report per order (unique `lab_test_order_id`)
- Creates `lab_results` + `lab_result_parameters`
- `uploaded_by` = logged-in lab technician id

**Response 201:**

```json
{
  "message": "Report uploaded successfully",
  "report_id": 1,
  "order_id": 1,
  "status": "processing"
}
```

---

## B.7 Complete test

**PATCH** `/lab/orders/{order_id}/complete`  
**Permission:** `lab:update`

**Rules:**

- Current status must be `processing`
- Sets `status` → `completed`
- Does not require parameters or file (PDF-only flow: complete first, then `upload-file`)

**Response:**

```json
{
  "message": "Test completed successfully",
  "order_id": 1,
  "status": "completed"
}
```

---

## B.8 Upload report file (PDF / image)

**POST** `/lab/orders/{order_id}/upload-file`  
**Permission:** `lab:upload_report`  
**Content-Type:** `multipart/form-data`

| Part | Type |
|------|------|
| file | PDF, JPG, JPEG, PNG (max 10 MB) |

**Rules:**

- Order status must be `completed`
- Creates `lab_results` row if missing (PDF-only workflow)
- Re-upload replaces previous file on disk
- Stores `file_name`, `file_type`, `file_size` on report

**Response:**

```json
{
  "message": "Report generated successfully",
  "report_id": 1,
  "order_id": 1,
  "file_name": "cbc-report.pdf",
  "file_type": "application/pdf",
  "file_size": 245760
}
```

---

## B.9 List reports (history)

**GET** `/lab/reports`  
**Permission:** `lab:view`

| Query | Description |
|-------|-------------|
| search | Patient name, UHID, test name |
| patient_id | Filter by patient |
| patient_name | Partial match on patient name |
| test_name | Partial match on test name |
| source | `PARAMETERS`, `PDF`, or `BOTH` |
| from_date | Report `created_at` (YYYY-MM-DD) |
| to_date | Report `created_at` (inclusive end of day IST) |
| page | Default 1 |
| page_size | Default 20, max 100 |

**Response items:**

| Field | Source |
|-------|--------|
| report_id | `lab_results.id` |
| order_id | `lab_test_order_id` |
| patient_name | from order |
| patient_uhid | from order |
| test_name | from order |
| uploaded_at | `lab_results.created_at` |
| uploaded_by_name | join users |
| status | order status |
| report_file | stored path (metadata only on list) |
| source | `PARAMETERS` / `PDF` / `BOTH` / `NONE` |

---

## B.10 Get single report

**GET** `/lab/reports/{report_id}`  
**Permission:** `lab:view`

Returns report header + `parameters[]` + linked `order` + `source` + file metadata (`file_name`, `file_type`, `file_size`).

---

## B.11 Download report file

**GET** `/lab/reports/{report_id}/file`  
**Permission:** `lab:view`

Returns binary file (`FileResponse`). List/detail endpoints return path metadata only.

---

## B.12 Re-upload report (optional — future)

**PUT** `/lab/reports/{report_id}`  
**Permission:** `lab:upload_report`

Not implemented. Use `POST /lab/orders/{order_id}/upload-file` to replace PDF.

---

# Part C — Tables

## C.1 `lab_test_orders` (EXISTS)

```
id, appointment_id, patient_id, patient_name, patient_uhid,
doctor_id, test_name, category, priority, clinical_notes,
status, created_at, updated_at
```

## C.2 `lab_results` (EXISTS)

```
id,
lab_test_order_id (FK lab_test_orders.id, unique),
uploaded_by (FK users.id),
sample_collected_at,
test_performed_at,
report_file (string — relative path on disk),
remarks (text),
file_name, file_type, file_size,
created_at (indexed),
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
| Lab upload report (parameters) | Not `cancelled`; one report per order |
| Lab complete | Only from `processing` |
| Lab upload file | Only when order `completed` |
| Lab download file | Path must resolve under `LAB_UPLOAD_DIR` |
| One report per order | Unique constraint on `lab_test_order_id` |
| Doctor name | Join `users` on `doctor_id` |
| Urgent first | Sort `priority` desc in lab list |
| Timezone | Use `Asia/Kolkata` like nurse module |

---

# Part F — APIs (all built)

| # | What | Method | URL | Permission |
|---|------|--------|-----|------------|
| 1 | Dashboard stats | GET | `/lab/dashboard` | lab:view |
| 2 | List orders | GET | `/lab/orders` | lab:view |
| 3 | Order detail | GET | `/lab/orders/{id}` | lab:view |
| 4 | Sample collected | PATCH | `/lab/orders/{id}/sample-collected` | lab:update |
| 5 | Processing | PATCH | `/lab/orders/{id}/processing` | lab:update |
| 6 | Create report | POST | `/lab/orders/{id}/report` | lab:upload_report |
| 7 | Complete test | PATCH | `/lab/orders/{id}/complete` | lab:update |
| 8 | Upload file | POST | `/lab/orders/{id}/upload-file` | lab:upload_report |
| 9 | List reports | GET | `/lab/reports` | lab:view |
| 10 | Report detail | GET | `/lab/reports/{id}` | lab:view |
| 11 | Download file | GET | `/lab/reports/{id}/file` | lab:view |

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

# Part J — Checklist

- [x] `lab_technician` role in seed with permissions
- [x] Tables `lab_results`, `lab_result_parameters` exist
- [x] `GET /lab/orders` returns all doctors' orders (not doctor-scoped)
- [x] Status transitions enforced in service layer
- [x] Report create + file upload are separate steps
- [x] Complete sets order `completed` (not report upload)
- [x] Doctor cannot cancel after `sample_collected`
- [ ] Works in `/docs` with lab tech token (manual test)
- [ ] Wrong role gets 403 (manual test)
- [x] Registered in `main.py`
- [x] Alembic migration `c3d4e5f6a7b8` for file metadata columns

---

# Part K — Quick reference: Doctor vs Lab URLs

| Action | Doctor | Lab technician |
|--------|--------|----------------|
| Create order | `POST /lab-tests` | — |
| List orders | `GET /lab-tests` (own only) | `GET /lab/orders` (all) |
| Order detail | `GET /lab-tests/{id}` | `GET /lab/orders/{id}` |
| Update order | `PUT /lab-tests/{id}` | — |
| Cancel | `PATCH /lab-tests/{id}/cancel` | — |
| Sample collected | — | `PATCH /lab/orders/{id}/sample-collected` |
| Processing | — | `PATCH /lab/orders/{id}/processing` |
| Create report | — | `POST /lab/orders/{id}/report` |
| Complete test | — | `PATCH /lab/orders/{id}/complete` |
| Upload PDF | — | `POST /lab/orders/{id}/upload-file` |
| View reports | `GET /lab-tests/reports` | `GET /lab/reports` |
| Report detail | `GET /lab-tests/{id}/report` | `GET /lab/reports/{id}` |
| Download file | `GET /lab-tests/{id}/report/file` | `GET /lab/reports/{id}/file` |
| Download file | — | `GET /lab/reports/{id}/file` |

---

## Build order (recommended)

1. Doctor lab orders must work first (done)
2. Seed `lab_technician` role + permissions
3. Create `lab_results` + `lab_result_parameters` models
4. Lab tech pending list (`GET /lab/orders`)
5. Status transitions (sample collected, processing)
6. Upload report (`POST /lab/orders/{id}/report`)
7. Completed reports list (`GET /lab/reports`)
