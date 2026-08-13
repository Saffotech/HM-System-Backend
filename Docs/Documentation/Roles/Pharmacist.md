# Role: Pharmacist (`pharmacist`)

**Display name:** Pharmacy Staff  
**PPT slides:** 1

---

## Purpose

Receive prescriptions written by doctors and **dispense medicines** to patients.

---

## Main tools

| Tool | What pharmacist does |
|------|----------------------|
| Prescription list | See pending / ready prescriptions |
| Prescription detail | Patient, medicines, allergies |
| Dispense | Mark items dispensed |
| Dispense history | Past dispenses |

---

## Key actions allowed

- View patients (for name / allergies context)  
- View prescriptions  
- Dispense prescriptions  

## Not for this role

- Create prescriptions (doctor)  
- Billing / payment  
- Lab reports  
- Inventory / suppliers (planned later)

---

## Typical flow for PPT

1. Doctor creates prescription during consultation  
2. Pharmacist opens prescription queue  
3. Verify patient & medicines  
4. Dispense and record  

---

## Permissions (summary)

`patients:view`, `prescriptions:view`, `prescriptions:dispense`
