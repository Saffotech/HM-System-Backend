# End-to-End Patient Journey (OPD)

**Audience:** Manager / PPT  
**Purpose:** One story that connects all roles.

---

## Happy path (paid same day)

```
1. Patient arrives at OPD counter
2. OPD registers patient (details + department + doctor)
3. OPD books appointment (date + time slot)
4. OPD generates bill and collects payment (Cash / UPI / Card)
5. System adds patient to doctor queue (after paid + linked appointment)
6. Receptionist can see patient on today’s board / doctor queue
7. Doctor starts consultation from queue
8. Doctor writes notes / prescription / lab order
9. Doctor marks consultation completed
10. Pharmacist dispenses medicines (if prescribed)
11. Lab technician processes tests (if ordered)
12. Nurse may record vitals / notes / medication as needed
```

---

## “Pending payment” path

```
1–3. Same as above (register + book)
4. Bill created as pay later → appointment stays scheduled, payment = pending
5. Patient appears in OPD “Pending” tab (scheduled + unpaid)
6. Receptionist may see unpaid appointments, but patient is NOT in doctor live queue
7. OPD collects payment later
8. Then patient enters doctor queue → continue from step 7 above
```

---

## Who is involved at each step

| Step | Role tool |
|------|-----------|
| Register + bill + pay | OPD Billing |
| Book / cancel appointment | OPD Billing |
| Monitor waiting room / boards | Receptionist |
| Consult & complete | Doctor |
| Support care | Nurse |
| Medicines | Pharmacist |
| Lab reports | Lab Technician |

---

## Frontend vs backend note (important for PPT honesty)

The **frontend UI** often shows one wizard:

> Details & Slot → Payment → Confirm & Register

Backend currently:

- Register creates **patient + visit/bill**  
- Appointment is booked via **separate appointment API**  
- Queue needs **paid visit linked to appointment**

So the **user experience can look like one form**, while the system may call more than one API behind the scenes.

---

## Status journey (appointment)

```
scheduled  →  completed     (doctor)
scheduled  →  cancelled     (OPD)
scheduled  →  no_show       (system, after appointment day)
```

Payment is tracked **separately** on the bill (`pending` / `partial` / `paid`).

---

## Presentation tip

Use this as a **single flow diagram slide**, then zoom into each role’s tools in the following slides.
