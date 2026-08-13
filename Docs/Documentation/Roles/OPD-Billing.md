# Role: OPD Billing (`opd_billing`)

**Display name:** Billing Counter / OPD Front Desk  
**PPT slides:** 1–2

---

## Purpose

Front-desk staff who **register patients**, **create bills**, **collect payment**, and **book / cancel appointments**.

---

## Main tools

| Tool | What staff does |
|------|-----------------|
| Patient search | Find existing patient by phone |
| Register new patient | Capture demographics + department + doctor |
| Bill preview | Show fees + GST before confirm |
| Collect payment | Cash / UPI / Card (UPI & Card need transaction reference) |
| Appointments | Book slot, list pending/scheduled/completed/cancelled |
| Today’s billing visits | See today’s registered visits/bills |
| Invoice | Print/view bill for a visit |

---

## Key actions allowed

- Create / update / view patients  
- Create OPD visit and bill  
- Collect or update payment  
- Create, update, cancel appointments  
- View OPD dashboard  

## Not for this role

- Doctor consultation complete  
- Writing prescriptions  
- Lab result upload  
- Creating staff users (Admin)

---

## Tabs that matter (appointments UI)

| Tab | Meaning |
|-----|---------|
| **Pending** | Appointment `scheduled` + bill unpaid |
| **Scheduled** | Appointment `scheduled` + bill paid |
| **Completed** | Doctor finished |
| **Cancelled** | Cancelled by OPD |

---

## Typical flow for PPT

1. Search or register patient  
2. Select department & doctor  
3. Choose appointment slot  
4. Generate bill → Confirm & pay  
5. Patient ready for doctor queue (after pay + appointment link)

---

## Permissions (summary)

`patients:*`, `opd:*`, `billing:*`, `appointments:view/create/update`
