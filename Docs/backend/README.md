# HMS Backend Documentation

API + database only. **No UI.**

## Start here

1. [backend-guide.md](./backend-guide.md) — how the project works
2. Pick your role file in [roles/](./roles/)

Frontend API integration doc: [../frontend/API-REFERENCE.md](../frontend/API-REFERENCE.md)

## Role modules

| File | Database role | Status |
|------|---------------|--------|
| [opd-billing.md](./roles/opd-billing.md) | `opd_billing` | Partly built |
| [doctor.md](./roles/doctor.md) | `doctor` | To build |
| [nurse.md](./roles/nurse.md) | `nurse` | To build |
| [pharmacist.md](./roles/pharmacist.md) | `pharmacist` | To build |
| [lab-test.md](./roles/lab-test.md) | `doctor` + `lab_technician` | Doctor done, lab tech to build |
| [lab-technician.md](./roles/lab-technician.md) | `lab_technician` | Summary → see lab-test.md |

## Test APIs

```bash
cd hms-backend
uvicorn main:app --reload
```

Open http://localhost:8000/docs
