# Role: Receptionist (`receptionist`)

**Display name:** Reception / Front Desk Monitor  
**PPT slides:** 1

---

## Purpose

Front desk **monitoring** of today’s appointments and doctor queues.  
Queue rows are created by **OPD after payment** — receptionist does **not** create queue entries.

---

## Main tools

| Tool | What staff does |
|------|-----------------|
| Dashboard | Counts: total, completed, paid, unpaid, cancelled |
| Today’s queue board | All doctors’ appointments for today |
| Doctor queue | Filter one doctor’s list |
| Queue history | Past dates |
| Doctors’ schedule | View availability (permission-gated) |

---

## Key actions allowed

- View patients (read)  
- View OPD / queue boards  
- Filter by payment: paid / unpaid  
- Filter by appointment status: scheduled / completed  

## Not for this role (by design)

- Collect payment  
- Cancel appointments  
- Complete consultation  
- Create queue manually  

---

## Important message for PPT

> Receptionist **sees** unpaid patients.  
> Doctor live queue shows **paid** patients only.

---

## Permissions (summary)

`patients:view`, `opd:view`, `receptionist:view_doctor_schedule`
