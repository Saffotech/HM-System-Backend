# Receptionist module — backend optimizations (frontend notes)

**For:** Frontend  
**Backend:** `GET /receptionist/*` boards are optimized.  
**Goal:** Same response shapes; faster dashboard / today-queue / doctor-queue / history / schedule.

No frontend code change is required for this release. Keep calling the same endpoints.

---

## Endpoints (unchanged contracts)

| API | Notes |
|-----|--------|
| `GET /receptionist/dashboard` | Same KPI fields. Counts are **canonical** (one row per patient+doctor today). |
| `GET /receptionist/today-queue` | Same pagination + filters. Dedupe: one row per patient. |
| `GET /receptionist/doctor-queue/{id}` | Same. Pass `page` + `limit` when possible. |
| `GET /receptionist/queue-history` | Same. |
| `GET /receptionist/doctors/schedule` | Same. Use `include_slots=true` only when you need the slot grid (prefer with `doctor_id`). |

---

## Dashboard fields (unchanged names)

| Field | Meaning |
|-------|---------|
| `total_patients` | Canonical today’s appointments (excl. cancelled/no_show) |
| `completed` | Among those, status completed |
| `todays_paid_appointments` | Canonical rows with paid visit |
| `todays_unpaid_appointments` | Canonical rows without paid visit |
| `todays_cancelled` | Today’s cancelled appointment count |

Frontend mapping in `receptionist.js` (`scheduled` ← paid, `pending` ← unpaid) stays valid.

---

## Performance tips (optional)

1. Doctor filter list: keep `doctors/schedule` **without** `include_slots` (current `getDoctors`).
2. Slot grid: `include_slots=true` + `doctor_id` (current `getDoctorTimeSlots`).
3. Prefer paginated `doctor-queue` (`page` + `limit`) instead of loading the full board when the UI is paged.

---

## Do not do

- Do not invent new dashboard routes.
- Do not remove receptionist API calls globally for other screens.
- Do not expect `token_number` / room on queue rows yet (still a gap).

---

## How to verify

1. Receptionist dashboard KPIs load and match today’s board filters.
2. Today queue / doctor queue: no duplicate patient rows for same-day walk-in + slot.
3. Network: same endpoints; responses should feel faster under load.
4. Schedule page: doctors list without slots; one doctor with slots still works.
