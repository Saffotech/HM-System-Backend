# Role: Doctor (`doctor`)

**Display name:** Clinical Doctor  
**PPT slides:** 1–2

---

## Purpose

See today’s **paid patients in queue**, run consultation, write prescriptions and lab orders, and **complete** the visit.

---

## Main tools

| Tool | What doctor does |
|------|------------------|
| Today’s queue | Ordered list of eligible patients |
| Start consultation | Begin current patient |
| Current consultation | See who is active now |
| Complete consultation | Finish visit + clinical notes |
| Appointments (doctor) | View today’s / by date (no-show hidden) |
| Prescriptions | Create / view / update |
| Lab orders | Order tests |
| Profile & notifications | Own profile, alerts |
| Request next patient | Notify reception when ready for next |

---

## Status rules (critical for PPT)

| Action | Allowed? |
|--------|----------|
| Mark appointment **completed** | Yes (doctor) |
| Mark **cancelled** | No — OPD does this |
| Mark **no_show** | No — system does this |
| Set waiting / in_progress status | No — removed; use queue start / current |

Only transition supported from doctor status API: **`scheduled → completed`**.

---

## Typical flow for PPT

1. Open today’s queue  
2. Start consultation  
3. Record diagnosis / notes  
4. Add prescription and/or lab order  
5. Complete consultation  

---

## Permissions (summary)

`patients:view`, `opd:view`, `appointments:view/create/update`,  
`prescriptions:*`, `lab:create/view`, doctor profile & notifications
