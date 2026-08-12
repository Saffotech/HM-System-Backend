# Receptionist backend — optimization inventory (Phase 1.1)

Snapshot of hot paths before/after the Aug 2026 optimize pass.

## Frontend → API map

| Screen | Calls |
|--------|--------|
| Dashboard | `GET /receptionist/dashboard` |
| Today queue | `GET /receptionist/today-queue` |
| Doctor queues | `GET /receptionist/doctor-queue/{id}` (+ schedule for doctor list) |
| Queue history | `GET /receptionist/queue-history` |
| Doctor schedule | `GET /receptionist/doctors/schedule` |

Notifications / profile are separate routers (not in this pass).

## Bottlenecks found

1. Dashboard loaded all today’s rows into Python to count paid/unpaid.
2. Queue/history loaded full day/range, then paginated in Python.
3. Day-rollover (`mark_past_scheduled_as_no_show`) ran on every GET.
4. Visit enrich re-queried every appointment even when join already had a visit.
5. Schedule with `include_slots` ran one booked-appointments query per doctor.

## What we changed

See service `Services/receptionist_service.py`, migration `i2j3k4l5m6n7`, and frontend note `Docs/frontend/receptionist-module-backend-changes.md`.
