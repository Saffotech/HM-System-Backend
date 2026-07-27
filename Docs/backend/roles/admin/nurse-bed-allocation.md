# Nurse Bed Allocation — Production Guide (Phase 6)

## Architecture

Nurse Bed Allocation assigns **bed responsibility** to nurses for a shift/date.
It does **not** own patients and does not change `beds.patient_id`.

```
Admin UI
  → Feature API (nurseBedAllocation.js)
  → Shared Service (adminBedAllocation.js)
  → Mapper (adminBedAllocationMapper.js)
  → React Query (useAdminQuery.js)
  → Backend Router (/admin/nurse-bed-allocations)
  → Service + Reports Service
  → Tables: nurse_shift_bed_allocations, nurse_shift_bed_allocation_history
  → audit_logs (via audit_service.log_event)
```

Nurse Dashboard / Handover reuse optional `allocated_only` and allocation-summary
APIs (Phases 4–5). Those contracts remain unchanged.

## Database Schema

### `nurse_shift_bed_allocations`
- `nurse_id`, `bed_id`, `department_id`, `shift_date`, `shift_name`
- `shift_start`, `shift_end`, `assigned_by`, `notes`, `is_active`
- Partial unique: one **active** row per `(bed_id, shift_date, shift_name)`
- Soft delete = `is_active = false`

### `nurse_shift_bed_allocation_history` (Phase 6)
- `allocation_id`, `action`, `actor_id`
- `old_nurse_id`, `new_nurse_id`, `old_bed_id`, `new_bed_id`
- `shift_date`, `shift_name`, `remarks`, `created_at`
- Actions: `created`, `edited`, `reassigned`, `activated`, `deactivated`, `deleted`

### Indexes (Phase 6)
- Composite `ix_nsba_date_shift_active` on `(shift_date, shift_name, is_active)`
- History indexes on `allocation_id`, `action`, `actor_id`, `shift_date`, `created_at`

Migration: `d3e4f5a6b7c8_create_nurse_shift_bed_allocation_history.py`

## API Endpoints

### Existing CRUD (unchanged contracts)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/admin/nurse-bed-allocations` | `bed_allocation:view` |
| GET | `/admin/nurse-bed-allocations/{id}` | `bed_allocation:view` |
| POST | `/admin/nurse-bed-allocations` | `bed_allocation:create` |
| POST | `/admin/nurse-bed-allocations/bulk` | `bed_allocation:assign` |
| PUT | `/admin/nurse-bed-allocations/{id}` | `bed_allocation:update` |
| PUT | `/admin/nurse-bed-allocations/{id}/deactivate` | `bed_allocation:update` |
| DELETE | `/admin/nurse-bed-allocations/{id}` | `bed_allocation:delete` (soft) |

Search supports nurse, bed, ward, shift, and numeric **allocation / nurse / bed / department ID**.

### Phase 6 additive
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/history` | Allocation history |
| GET | `/dashboard-summary` | Admin KPI cards |
| GET | `/conflicts` | Warnings only (no auto-fix) |
| GET | `/analytics/workload` | Beds per nurse analytics |
| GET | `/reports/daily` | Daily allocation report |
| GET | `/reports/shift` | Shift report |
| GET | `/reports/department` | Department report |
| GET | `/reports/nurse-workload` | Workload report |
| GET | `/reports/unallocated-beds` | Unallocated beds |
| GET | `/reports/unassigned-nurses` | Nurses without assignment |
| GET | `/reports/occupied-coverage` | Occupied assigned vs unassigned |

### Nurse (Phases 4–5, unchanged)
- `GET /nurse/beds/patients?allocated_only=`
- `GET /nurse/beds/allocation-summary`

## Permissions

| Code | Used by |
|------|---------|
| `bed_allocation:view` | List, detail, history, reports, conflicts |
| `bed_allocation:create` | Single create |
| `bed_allocation:assign` | Bulk assign |
| `bed_allocation:update` | Edit / deactivate |
| `bed_allocation:delete` | Soft delete |

Admin / Super Admin receive `__all__`. No new nurse permissions.

## Frontend Pages

| Route | Page |
|-------|------|
| `/admin/bed-allocation` | List + search |
| `/admin/bed-allocation/new` | Create / bulk |
| `/admin/bed-allocation/:id` | Detail |
| `/admin/bed-allocation/:id/edit` | Edit |
| `/admin/bed-allocation/history` | History + export |
| `/admin/bed-allocation/reports` | Reports, workload, conflicts + export |

Admin Dashboard shows allocation KPI cards when `bed_allocation:view` is present.

## Workflow

1. Admin assigns beds to a nurse for a shift/date (create or bulk).
2. History + audit log record the change (actor, old/new values, IP when available).
3. Nurse Dashboard **Allocated** mode shows occupied beds for the current shift.
4. Handover pre-selects allocated occupied patients; Take Over does **not** transfer allocations.
5. Reports / conflicts provide visibility; conflicts never auto-modify data.

## Admin Guide

1. Open **Nurse Bed Allocation**.
2. Use filters: date, shift, department, nurse, status, free-text / allocation ID.
3. Create allocations; confirm deactivate before removing responsibility.
4. Use **History** for audit trail; export CSV / Excel / PDF as needed.
5. Use **Reports** for daily/shift/department/workload/coverage and conflict warnings.
6. Dashboard cards show today’s coverage at a glance.

## Nurse Guide

1. Dashboard: toggle **Allocated** / **All**. Default is Allocated when assignments exist.
2. Empty Allocated means no beds for this shift — switch to All manually.
3. Handover: allocated patients are pre-added; you may remove/add freely.
4. Clinical actions (vitals, notes, meds, alerts) are unchanged.

## Audit

Mutations call `audit_service.log_event` with:
- User (actor), action, timestamp, resource type/id
- Old / new values in `details`
- Client IP from `X-Forwarded-For` or request client host when present

Dedicated history table powers the Allocation History UI.

## Export

Client-side utilities in `features/admin/utils/bedAllocationExport.js`:
- **CSV** — Blob download
- **Excel** — CSV file (opens in Excel; no duplicate Excel library)
- **PDF** — print window → Save as PDF (same pattern as Lab reports)

## Security

- All admin routes use `PermissionChecker("bed_allocation:*")`
- Input validated via Pydantic schemas + service checks (nurse role, bed exists, conflicts)
- SQLAlchemy parameterization (no raw SQL concatenation)
- Conflicts endpoint is read-only

## Future Extension Points

- Allocation templates / recurring weekly schedules
- Automated expired-allocation cleanup job (still manual deactivate today)
- Push notifications when assignments change
- Richer Excel/PDF server-side generation if a shared HMS export service is added
- Reporting dashboards beyond admin (Phase-scoped analytics)

## Regression Boundaries

Do **not** change Doctor, Receptionist, OPD, Billing, Lab, Pharmacy, Auth, Notifications,
or existing Nurse Dashboard / Handover contracts when extending this module further.
