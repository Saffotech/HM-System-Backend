# SaffoCare roles and features

The product has **14 sign-in roles**.

Three are organization (platform) roles. They are not tied to one hospital (`tenant_id` is null).

Eleven are hospital roles. Each belongs to one hospital.

`opd_billing`, `opd_staff`, and `opd_receptionist` are older names for the same OPD role. They sign in as `opd`.

## Organization roles (3)

### Platform admin (`platform_admin`)

Home: `/platform`

- Dashboard and platform analytics
- Hospitals / tenants, including register a hospital
- CRM and performance across the organization
- Subscription plans, subscriptions, and billing and revenue
- Platform staff (create CRM and accountant accounts only)
- Own profile

### CRM (`crm`)

Home: `/platform/crm`

Permission: `leads:manage`

- Lead list and lead detail
- Add a lead (optionally leave it unclaimed)
- Claim a new enquiry
- Log a contact (call, email, WhatsApp, meeting, or visit)
- Set or move a follow-up
- Add notes and edit contact and plan details
- Send an agreed lead to Accounts
- Close a lead as not interested, or reopen a closed lead
- Own performance

### Accountant (`accountant`)

Home: `/platform/accounts`

Permissions: `registrations:create`, `invoices:manage`

- Agreed registrations waiting to become hospitals
- Registered hospitals (includes hospital code)
- Open one registration and prefill the form
- Register the hospital from that lead (code, address, pincode, admin password, plan, billing cycle)
- Invoices

## Hospital roles (11)

These roles only see their own hospital.

### Hospital owner — Super admin (`super_admin`) and Admin (`admin`)

Home: `/admin/dashboard`

Both use the hospital owner screens. `super_admin` is not the same as platform admin.

- Dashboard
- Staff (create, view, update)
- Departments
- Roles and permission assignment
- Reports, including visits
- Audit log
- Bed allocation
- Nurse workforce (shifts and roster)
- Module settings: OPD, doctor, receptionist, lab, nurse, pharmacy
- Profile and notifications

The hospital owner (`admin`) can assign `manager` plus the clinical roles below. A manager cannot create another admin, super admin, or any platform role.

### Manager (`manager`)

Home: `/manager/dashboard`

Hospital operations. Separate from the hospital owner.

- Dashboard
- Staff for clinical roles: doctor, nurse, OPD billing, IPD, pharmacist, receptionist, lab technician
- Departments
- Roles (view)
- Reports, including visits
- Bed allocation
- Nurse workforce (shifts and roster)
- The same module settings as the owner panel
- Profile and notifications

### Doctor (`doctor`)

Home: `/doctor/dashboard`

- Doctor dashboard
- Own profile

### OPD (`opd`)

Also stored as `opd_billing`. Home: `/dashboard`

Front desk for outpatient visits.

- Dashboard
- Patients (register, profile, update)
- Appointments (book, availability)
- OPD visit billing and bill view
- Pricing
- Payment history
- Profile and notifications

Payment modes on OPD: Cash, Card, UPI.

### Billing (`billing`)

Uses the same outpatient screens as OPD: dashboard, patients, appointments, billing, pricing, and payment history.

### Receptionist (`receptionist`)

Home: `/receptionist/dashboard`

- Today’s queue
- Doctor queues
- Pricing
- Queue history
- Profile and notifications

### Nurse (`nurse`)

Home: `/nurse/dashboard`

- My duty and patient queue
- Patient chart
- Vitals (list, add, view, edit)
- Nursing notes (list, add, view, edit)
- Lab reports
- Medications and medication history
- Handover
- Alerts
- Doctor visits
- Profile and notifications

### Lab technician (`lab_technician`)

Home: `/lab/dashboard`

- Lab orders
- Upload a result for an order
- Lab reports
- Profile and notifications

### Pharmacist (`pharmacist`)

Home: `/pharmacy/prescriptions`

- Prescriptions and prescription detail
- Dispense
- Dispense history
- Pharmacy dashboard
- Profile and notifications

### IPD (`ipd`)

Home: `/ipd/dashboard`

Inpatient front desk.

- Patients and admission detail
- Admit a patient
- Beds and bed transfer
- Stay billing, bill preview, and bill view
- Insurance patient and insurance billing
- Payment history
- Discharge
- Pricing
- Profile

Collect and discharge payment modes: Cash, Card, UPI. Insurance claims go through the claim module.
