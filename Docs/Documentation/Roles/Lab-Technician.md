# Role: Lab Technician (`lab_technician`)

**Display name:** Laboratory Staff  
**PPT slides:** 1

---

## Purpose

Receive **lab test orders** from doctors, enter results, and **upload reports**.

---

## Main tools

| Tool | What lab staff does |
|------|---------------------|
| Pending / ordered tests | See doctor lab orders |
| Enter results | Capture parameters / values |
| Upload report | Attach report file |
| Update status | Mark progress / completed |

---

## Key actions allowed

- View patients  
- View / create / update lab work  
- Upload lab report  

## Not for this role

- Order tests for a patient (doctor does)  
- Billing  
- Dispense medicines  

---

## Typical flow for PPT

1. Doctor places lab order  
2. Lab technician sees order in lab queue  
3. Perform test / enter results  
4. Upload report for doctor / nurse to view  

---

## Permissions (summary)

`patients:view`, `lab:view`, `lab:create`, `lab:update`, `lab:upload_report`
