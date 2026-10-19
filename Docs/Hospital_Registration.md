# Hospital registration (frontend)

Registering a hospital now saves the subscription with the hospital. Both screens call the same backend rules. The Platform Admin forms still keep the hospital in this browser through `addHospital`. Replace that call with the API below.

Header on every call: `Authorization: Bearer <access_token>`

The signed-in platform user needs the permission `hospitals:create`.

Do not send `adminPasswordConfirm`. The form checks that the two passwords match. The API stores only `admin_password`.

## Which screen calls which endpoint

| Screen | File | Call |
|---|---|---|
| Platform admin, Register Hospital | `Platform Admin/panels/superAdmin/pages/tenants/RegisterHospital.jsx` | `POST /tenants` |
| Accountant, Register Hospital | `Platform Admin/panels/accountant/pages/RegisterHospital.jsx` | `POST /platform/registrations/{lead_id}/register` |

`lead_id` is the numeric id from `GET /platform/registrations?status=agreed`. It is not the demo request id shown in the browser.

## Allowed subscription values

Send these strings exactly.

| Field | Allowed values | Form state today |
|---|---|---|
| `plan` | `Starter`, `Professional`, `Enterprise` | `values.plan` |
| `billing_cycle` | `Monthly`, `Annual` | `values.billingCycle` |
| `trial_period` | `None`, `14 days`, `30 days`, `60 days` | `values.trialPeriod` |
| `tenant_status` | `Active`, `Trial`, `Suspended` | `values.tenantStatus` |

`plan` and `billing_cycle` are required. If `trial_period` is omitted it is stored as `None`. If `tenant_status` is omitted it is stored as `Active`.

The API calculates the rest. Do not send price, renewal date, or subscription status.

| What you send | What is stored |
|---|---|
| `tenant_status` `Active` and `trial_period` `None` | `subscription_status` `Active`, hospital can log in |
| `tenant_status` `Trial`, or any trial period other than `None` | `subscription_status` `Trial`, hospital can log in |
| `tenant_status` `Suspended` | `subscription_status` `Suspended`, `is_active` false. Hospital login returns `403` `Hospital is inactive` |

Renewal date:

- Trial, period `14 days`, `30 days`, or `60 days`: that many days from today.
- Status `Trial` and period `None`: 14 days from today.
- `Monthly`: one month from today.
- `Annual`: twelve months from today.
- `Suspended`: uses the billing cycle, not the trial length.

Dates are `YYYY-MM-DD` in Asia/Kolkata.

The price shown in the summary box stays on the frontend. Keep using `priceFor` in `Platform Admin/shared/utils/hospitals.js`. The API does not return amount, user limit, or storage limit.

## 1. Platform admin — `POST /tenants`

Status `201`.

Map the form in `RegisterHospital.jsx` like this:

| Form state | JSON field |
|---|---|
| `values.name` | `name` |
| `values.code` | `code` |
| `values.type` | `hospital_type` |
| `values.email` | `email` |
| `values.phone` | `phone` |
| `values.address` | `address` |
| `values.city` | `city` |
| `values.state` | `state` |
| `values.postalCode` | `pincode` |
| `values.adminName` | `admin_full_name` |
| `values.adminEmail` | `admin_email` |
| `values.adminPhone` | `admin_phone` |
| `values.adminPassword` | `admin_password` |
| `values.plan` | `plan` |
| `values.billingCycle` | `billing_cycle` |
| `values.trialPeriod` | `trial_period` |
| `values.tenantStatus` | `tenant_status` |

```json
{
  "name": "City General",
  "code": "CITYGEN",
  "hospital_type": "General",
  "email": "contact@citygen.com",
  "phone": "9123456780",
  "address": "FC Road",
  "city": "Pune",
  "state": "Maharashtra",
  "pincode": "411004",
  "admin_full_name": "Neha Patil",
  "admin_email": "neha@citygen.com",
  "admin_phone": "9123400000",
  "admin_password": "Neha@1234",
  "plan": "Professional",
  "billing_cycle": "Monthly",
  "trial_period": "None",
  "tenant_status": "Active"
}
```

`hospital_type` is one of: `Multi-specialty`, `General`, `Specialty`, `Children's`, `Diagnostic`, `Teaching`.

The code is stored in uppercase. Password must be at least 8 characters.

Response:

```json
{
  "tenant_id": 12,
  "name": "City General",
  "code": "CITYGEN",
  "hospital_type": "General",
  "admin_user_id": 40,
  "admin_email": "neha@citygen.com",
  "plan": "Professional",
  "billing_cycle": "Monthly",
  "trial_period": "None",
  "tenant_status": "Active",
  "subscription_status": "Active",
  "is_active": true,
  "subscription_started_on": "2026-10-15",
  "subscription_renews_on": "2026-11-15"
}
```

`tenant_id` is a number. It is not a `TNT-` id. After `201`, open the hospital using this id and show `subscription_status`, `subscription_started_on`, and `subscription_renews_on` from the response.

In `finish()`, send this body instead of calling `addHospital`.

## 2. Accountant — `POST /platform/registrations/{lead_id}/register`

Status `201`.

The lead already has the hospital name, type, emails, phones, city, state, and administrator name. Send only what the accountant form still collects, including the subscription section. If the accountant changes the plan on the form, send the new plan. That value is what is stored on the hospital.

```json
{
  "code": "CITYGEN",
  "address": "FC Road",
  "pincode": "411004",
  "admin_password": "Neha@1234",
  "plan": "Professional",
  "billing_cycle": "Monthly",
  "trial_period": "None",
  "tenant_status": "Active"
}
```

`code` is 3–12 letters, numbers, or hyphens. The API uppercases it.

Response is the lead, after it is marked registered:

```json
{
  "id": 8,
  "hospital_name": "City General",
  "hospital_type": "General",
  "city": "Pune",
  "state": "Maharashtra",
  "hospital_email": "contact@citygen.com",
  "contact_person": "Neha Patil",
  "designation": null,
  "contact_phone": "9123456780",
  "contact_email": "neha@citygen.com",
  "plan": "Professional",
  "billing_cycle": "Monthly",
  "source": "Phone enquiry",
  "agreed_at": "2026-10-14T16:10:00+05:30",
  "agreed_by_name": "Asha Rao",
  "handover_note": null,
  "status": "Registered",
  "hospital_id": 12,
  "hospital_code": "CITYGEN",
  "registered_at": "2026-10-15T16:05:00+05:30",
  "registered_by_name": "Accounts User"
}
```

Use `hospital_id` and `hospital_code` from this response. `plan` and `billing_cycle` here are the values still stored on the lead. Trial period, tenant status, and renewal dates are not in this response. Keep the values the form submitted for those, and use `hospital_id` as the created hospital.

The lead must be `Agreed`, must have a contact email, and must have a state. This call is only for a platform user (`tenant_id` null).

To load the queue before the form:

`GET /platform/registrations?status=agreed`

`GET /platform/registrations/{lead_id}`

Registered rows: `GET /platform/registrations?status=registered`

## Errors

| Status | `detail` | When |
|---|---|---|
| `401` | `Could not validate credentials` | Missing or expired token |
| `403` | `Permission denied` | User lacks `hospitals:create` |
| `403` | `Hospital registration is only available to platform staff` | Accountant call made by a hospital user |
| `404` | `Registration not found` | Lead is missing, or it is not Agreed or Registered |
| `409` | `Tenant code already registered` | `code` is already used |
| `409` | `Hospital email already registered` | Hospital email is already used |
| `409` | `Administrator email already registered` | Admin email is already used |
| `409` | `This hospital is already registered.` | Lead was already registered |
| `422` | `Contact email is required on the lead before it can be registered.` | Agreed lead has no contact email |
| `422` | `State is required on the lead before it can be registered.` | Agreed lead has no state |
| `422` | validation list | Bad email, unknown plan, short password, bad tenant code on the accountant call |

A field error looks like this. Show `msg` on that field.

```json
{
  "detail": [
    {
      "loc": ["body", "plan"],
      "msg": "Value error, Choose a subscription plan."
    }
  ]
}
```

A conflict looks like this. Show `detail` in the toast.

```json
{ "detail": "Tenant code already registered" }
```
