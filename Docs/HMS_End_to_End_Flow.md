# SaffoCare end-to-end flow

SaffoCare has two worlds.

**Platform** people are not inside one hospital. They sell the product, check the papers, take the first payment, and create the hospital. Their `tenant_id` is empty.

**Hospital** people belong to one hospital. They only see that hospital’s patients, bills, beds, and staff.

A person signs in once. The role on the account decides the home screen and which APIs succeed. Hiding a button is not the rule. The API returns 403 when the role is wrong.

## How a hospital is born

This is the path from a sales enquiry to a working hospital.

1. **Platform admin** creates the platform staff: CRM, Legal and Finance, and Accountant. Platform admin also keeps the subscription plan catalog, can see every hospital, and can see company-wide analytics. Platform admin does not review the legal papers and does not record the advance.

2. **CRM** adds a hospital lead. The lead moves through New, Contacted, and then Agreed when the hospital says yes. CRM can also close it as not interested. CRM cannot register the hospital.

3. **The system**, at the moment CRM marks the lead Agreed, opens one Legal and Finance case for that lead. It copies the hospital name, city, and plan. The discount starts at 0. Seven checklist items start as Pending. There are no documents yet. Agreeing the same lead again does not open a second case.

4. **Legal and Finance** reviews that one case.
   - Uploads and verifies the hospital documents.
   - Completes the seven checks.
   - Saves the real price and discount.
   - If the discount is over 10%, asks the Finance Head, then records Approved or Rejected.
   - Decides: Approved, Conditionally Approved, Changes Requested, or Rejected.
   - Changes Requested can be sent back to In Review with resubmit.
   - Approval means the deal is allowed. It does not mean the money arrived.

5. **Accountant** sees the lead in the “agreed” registration list only after the case is Approved. Accountant then records the advance on that case. Only after both are true — case Approved and advance recorded — can Accountant register the hospital. Registration creates the hospital, its code, and its first hospital owner login. Accountant also manages the hospital’s later subscription invoices.

6. The hospital now exists. From here, only people tied to that hospital can work inside it.

```text
Platform admin
    creates CRM, Legal and Finance, Accountant
CRM
    lead → Agreed
System
    one Legal and Finance case
Legal and Finance
    papers, checklist, price → Approved or Rejected
Accountant
    sees it only if Approved → records advance → registers the hospital
Hospital staff
    run that hospital
```

## What happens inside the hospital

The hospital owner signs in and sets the hospital up. Clinical staff then use only their own module. A doctor cannot open IPD by being logged in as a doctor. The browser Back button must not be treated as permission. The API still checks the role.

1. **Hospital owner** (`admin` or `super_admin`) opens `/admin/dashboard`. This is not the platform admin. The owner creates departments, creates the manager and clinical staff, sets module prices and beds, and reads reports and the audit log.

2. **Manager** runs day-to-day hospital operations: clinical staff, departments, beds, nurse roster, and the same module settings. A manager cannot create an owner or any platform user.

3. **Receptionist** watches today’s queues and the doctor schedule. The receptionist does not write the clinical record.

4. **OPD** (and **Billing**, which uses the same outpatient screens) registers the patient, books the appointment, and takes the outpatient payment by Cash, Card, or UPI.

5. **Doctor** sees the doctor dashboard and their own profile, and works the visits that belong to them.

6. **Nurse** takes the ward queue: vitals, notes, medicines, lab reports, handover, alerts, and doctor visits.

7. **Lab technician** sees lab orders, uploads the result, and files the report.

8. **Pharmacist** sees prescriptions, dispenses the medicine, and keeps the dispense history.

9. **IPD** admits the patient, assigns and transfers the bed, bills the stay, handles insurance billing, takes Cash, Card, or UPI, and discharges the patient.

Each of these hospital roles has its own profile. They do not see another hospital’s rows.

## Role at a glance

| Role | Starts | Ends |
|---|---|---|
| Platform admin | Creates platform staff and plans | Does not approve a case or take the advance |
| CRM | A new hospital enquiry | Lead Agreed, or closed as not interested |
| Legal and Finance | The case that opened from that Agreed lead | Approved, conditionally approved, changes requested, or rejected |
| Accountant | An approved case | Advance recorded, hospital registered, later invoices managed |
| Hospital owner | The new hospital | Staff, departments, prices, beds, reports |
| Manager | The owner’s hospital | Clinical staff and daily operations |
| Receptionist | The front desk | Queues and the doctor schedule |
| OPD / Billing | A person at the desk | A registered patient, a visit, and an outpatient payment |
| Doctor | Their own queue | The visit they are allowed to see |
| Nurse | The ward queue | Vitals, notes, medicines, handover |
| Lab technician | A lab order | An uploaded result |
| Pharmacist | A prescription | Medicine dispensed |
| IPD | A patient who needs admission | Bed, stay bill, and discharge |

## What is deliberately separate

- Platform admin and the hospital owner are different people. The hospital owner is `admin` or `super_admin` inside one hospital.
- Legal approval and the advance payment are different facts. A case can be Approved while `advance_received` is still false.
- Subscription invoices are the hospital’s plan bills. They are not the patient’s OPD or IPD bill.
- Conditionally Approved is not enough to register the hospital. The case must be Approved, and the advance must be recorded.
