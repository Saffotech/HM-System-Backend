# Receptionist (`receptionist`)

Front desk **queue management**: check-in, today's queue (all doctors), doctor queues, pending doctor calls, call patient, no-show, rejoin, queue history, CSV export.

**Full module spec:** [Receptionist Module](../../flows/receptionist-module.md)  
**Frontend UI spec:** [Receptionist frontend flow](../../frontend/roles/receptionist.md)

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | Receptionist APIs — check-in, queues, call patient, history (backend done) |
| **Phase 2** | Frontend screens + polish — end of file |

---

## Workflow (why this module exists)

Reception does **not** decide when the doctor is ready (consultation length varies).  
**Doctor** clicks **Next patient** → **Reception** sees pending call → **Reception** calls patient to the room → **Doctor** starts consultation when patient arrives.

```
OPD Billing → appointment (scheduled)
Reception   → check-in (patient_queue, waiting)
Doctor      → complete → request-next (auto FIFO)
Reception   → pending-calls → call-patient (called + called_at + called_by)
Doctor      → start (in_progress) → complete
```

**Queue status flow:** `waiting` → `called` → `in_progress` → `completed`  
(`no_show` / `rejoin` / `cancelled` as exceptions)

---

## Permissions (seed)

```
patients:view
opd:view
appointments:view
appointments:update
```

`Constants/constants.py` already has `Role.RECEPTIONIST = "receptionist"`.

---

## Register receptionist user

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password | Yes |
| role_id | Yes — `receptionist` from `GET /roles/` |
| department_id | No |

---

## APIs (11)

| # | Method | Path | Query params |
|---|--------|------|--------------|
| 1 | GET | `/receptionist/dashboard` | `doctor_id?` |
| 2 | GET | `/receptionist/today-queue` | `doctor_id`, `doctor_name`, `patient_id`, `status`, `search`, `page`, `limit` |
| 3 | GET | `/receptionist/arrivals` | `doctor_id`, `search`, `page`, `limit` |
| 4 | POST | `/receptionist/check-in/{appointment_id}` | — |
| 5 | GET | `/receptionist/doctor-queue/{doctor_id}` | `status`, `search`, `date`, `page?`, `limit?` |
| 6 | GET | `/receptionist/pending-calls` | `doctor_id?` |
| 7 | POST | `/receptionist/call-patient/{queue_id}` | — |
| 8 | PATCH | `/receptionist/queue/{queue_id}/no-show` | — |
| 9 | PATCH | `/receptionist/queue/{queue_id}/rejoin` | — |
| 10 | GET | `/receptionist/queue-history` | `date`, `date_from`, `date_to`, `doctor_id`, `status`, `search`, `page`, `limit` |
| 11 | GET | `/receptionist/queue-history/export` | Same as history + `format=csv` |

Request/response examples → [Receptionist Module §6](../../flows/receptionist-module.md#6-apis).

---

## Code files

```
Routers/receptionist_router.py       # Thin — delegates to service
Services/receptionist_service.py     # Orchestration; reuses existing queue services
Schemas/receptionist_schema.py       # Pydantic models + paginated wrappers
```

### Service delegation (no duplicate queue logic)

| `receptionist_service` function | Reuses / notes |
|---------------------------------|----------------|
| `get_dashboard` | Aggregates `patient_queue`, `appointments`, `doctor_queue_next_requests`; optional `doctor_id` |
| `get_today_queue` | All doctors checked-in today; priority + attention sort |
| `get_arrivals` | `appointments` not in queue; search includes `appointment_uid` |
| `check_in_patient` | `add_patient_to_queue_service` — **409** on duplicate |
| `get_doctor_queue` | Filtered `patient_queue` with attention sort |
| `get_pending_calls` | `list_pending_next_requests_service` |
| `call_patient` | `fulfill_call_patient` — sets `called`, `called_at`, `called_by` |
| `mark_no_show` / `rejoin_queue` | Queue status updates; clears `called_by` on no-show/rejoin |
| `get_queue_history` | Date-range query; search includes `appointment_uid` |
| `export_queue_history_csv` | Same filters as history → CSV download |

---

## Tables

| Table | Role |
|-------|------|
| `appointments` | Arrivals list, dashboard arrival/cancelled counts |
| `patient_queue` | Check-in, queue, history, `called_at`, `called_by` |
| `doctor_queue_next_requests` | Pending doctor next calls |

**Schema (migrations):**

| Change | Migration |
|--------|-----------|
| `called_at`, `no_show` enum | `7954ceb7aea4` |
| `appointmentstatus` enum, `queue_id` FK | `e1f2a3b4c5d6` |
| `called` enum, `called_by` FK | `f7a8b9c0d1e2` |

---

## Pagination

| Endpoint | Pagination |
|----------|------------|
| `/arrivals` | **Required** — `page`, `limit` (default 20, max 100) |
| `/today-queue` | **Required** |
| `/queue-history` | **Required** |
| `/doctor-queue` | Optional |
| Others | No |

Standard response: `{ success, total, page, limit, ... }`

---

## Duplicate check-in (409)

**POST** `/receptionist/check-in/{appointment_id}` returns **409 Conflict** when:

- Same `appointment_id` already has a row in today's `patient_queue`, or
- Same `patient_id` + `doctor_id` already has a queue entry today

---

## Legacy endpoints (deprecated)

| Old | New |
|-----|-----|
| `POST /queue/add` | `POST /receptionist/check-in/{appointment_id}` |
| `GET /opd/queue/next-requests` | `GET /receptionist/pending-calls` |
| `POST /opd/queue/send-in` | `POST /receptionist/call-patient/{queue_id}` |

**Do not use** `GET /opd/queue/today` for reception queue — returns `opd_visits`.

---

## Does not include

- Patient registration / billing → [opd-billing.md](./opd-billing.md)
- Doctor consultation → [doctor.md](./doctor.md)

---

## Implementation status

| Item | Status |
|------|--------|
| Router, service, schema | Done |
| Dashboard manager metrics + `doctor_id` filter | Done |
| `today-queue` filters and attention sort | Done |
| `called` status + `called_by` audit | Done |
| Arrivals / history `appointment_uid` search | Done |
| Queue history CSV export | Done |
| Duplicate check-in 409 | Done |
| `receptionist` role in seed | Done |
| Frontend screens | Phase 2 — to build |

---

## Phase 2 — Planned

Phase 1 backend (table above) is **done**. Phase 2 is primarily **frontend**.

### Frontend — Phase 2

| # | Screen | API |
|---|--------|-----|
| 1 | Reception dashboard | `GET /receptionist/dashboard` |
| 2 | Today queue (all doctors) | `GET /receptionist/today-queue` |
| 3 | Doctor queue view | `GET /receptionist/doctor-queue/{doctor_id}` |
| 4 | Pending calls | `GET /receptionist/pending-calls` |
| 5 | Check-in patient | `POST /receptionist/check-in/{appointment_id}` |
| 6 | Call patient | `POST /receptionist/call-patient/{queue_id}` |
| 7 | No-show / rejoin | Receptionist update endpoints |
| 8 | Queue history + CSV export | History + export APIs |

### Backend — Phase 2 (optional)

| # | Feature | Notes |
|---|---------|--------|
| 1 | Real-time pending calls | WebSocket or polling (optional) |
| 2 | Tests | Check-in 409, call flow, CSV export |
| 3 | Doc sync | Keep aligned with [receptionist-module.md](../flows/receptionist-module.md) |

### Phase 2 — Out of scope

- Patient registration / billing → [opd-billing.md](./opd-billing.md)
- Doctor consultation → [doctor.md](./doctor.md)
