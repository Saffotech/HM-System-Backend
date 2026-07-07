# Queue endpoints — which API to use

HMS has **four different “queue” concepts**. Using the wrong URL is a common integration mistake.

---

## Quick reference

| Who | What you need | Correct API | Data source |
|-----|---------------|-------------|-------------|
| **OPD billing** | Today’s registered visits, bills, payment status | `GET /opd/visits/today` | `opd_visits` |
| **Receptionist** | **All doctors** — checked in today | `GET /receptionist/today-queue` | `patient_queue` |
| **Receptionist** | One doctor — live waiting room / tokens | `GET /receptionist/doctor-queue/{doctor_id}` | `patient_queue` |
| **Receptionist** | Queue history (reporting) | `GET /receptionist/queue-history` | `patient_queue` |
| **Doctor** | My patients today in queue | `GET /queue/today` | `patient_queue` |
| **Nurse** | Vitals queue view | `GET /nurse/queue/today` | `patient_queue` (+ vitals flags) |

**Receptionist is view-only** — no arrivals, check-in, pending-calls, call-patient, no-show, rejoin, or CSV export on `/receptionist/*`.

**`today-queue` filters:** `doctor_id`, `doctor_name`, `patient_id`, `status`, `search`, `page`, `limit`.  
**Sort:** priority (high first) → `called` / `waiting` → token.

---

## OPD billing vs receptionist (most confused pair)

### `GET /opd/visits/today` — billing visits

- **Role:** `opd_billing`
- **Table:** `opd_visits`
- **Shows:** Bill number, billing token, payment status, fees
- **Use for:** Billing counter

### `GET /receptionist/*` — clinical queue (view)

- **Role:** `receptionist`
- **Table:** `patient_queue` (+ `appointments`)
- **Shows:** Queue token, status, `called_at`, `called_by` (read-only)
- **Use for:** Front desk monitoring boards

---

## Removed / deprecated paths

| Old path | Status |
|----------|--------|
| `GET /receptionist/arrivals` | **Removed** |
| `GET /opd/queue/today` | Deprecated → `GET /opd/visits/today` |
| `GET /opd/queue/next-requests` | **Removed** |
| `POST /opd/queue/send-in` | **Removed** |
| `POST /queue/add` | **Removed** |
| `POST /receptionist/check-in/{id}` | **Removed** |
| `GET /receptionist/pending-calls` | **Removed** |
| `POST /receptionist/call-patient/{id}` | **Removed** |
| `PATCH /receptionist/queue/{id}/no-show` | **Removed** |
| `PATCH /receptionist/queue/{id}/rejoin` | **Removed** |
| `GET /receptionist/queue-history/export` | **Removed** |

---

## Typical day flow

```
OPD Billing                    Receptionist (view)              Doctor
───────────                    ───────────────────              ──────
POST /opd/patient/register     GET /receptionist/today-queue
   + check-in (queue row)      GET /receptionist/today-queue
                               GET /receptionist/doctor-queue/{id}    POST /queue/request-next
                                                                        PUT /queue/start/{id}
                                                                        PUT /queue/complete/{id}
```

---

## Related docs

- [Receptionist module](./receptionist-module.md)
- [OPD billing (backend)](../backend/roles/opd-billing.md)
- [API Reference](../frontend/API-REFERENCE.md)
