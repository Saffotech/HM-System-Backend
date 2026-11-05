# Legal and Finance — frontend calls

Use the existing platform client. Send `Authorization: Bearer <access_token>`. Do not use the demo data in `hms-legal-finance-react`. That folder is only a layout reference.

Base path: `/platform/legal/cases`

A 401 means sign in again. A 403 means this role cannot call that API. A 422 means the body or the approval rules failed. Show the `detail` text. Do not treat 403 or 422 as an empty list.

## Who calls what

| Screen | Role | Calls |
|---|---|---|
| Legal and Finance queue, documents, checklist, price, escalation, decision | `legal_finance` | All calls below except payment confirmation |
| Accounts queue and payment | `accountant` | `GET /platform/registrations?status=agreed` and `POST /platform/legal/cases/{id}/payment-confirmation` |
| Register the hospital | `accountant` | The existing register endpoint, only after the case is approved and the advance is recorded |

CRM does not call these routes. CRM only marks the lead Agreed. The backend opens the case.

## Load the queue

`GET /platform/legal/cases`

`GET /platform/legal/cases/{id}`

The case object includes `lead_id`, `hospital_name`, `city`, `plan`, `status`, `discount`, `escalation`, `documents`, `checklist`, `finance`, `decision`, `advance_received`, and `ready_to_register`.

`ready_to_register` is true only when the status is Approved and `advance_received` is true. The Legal and Finance screen does not register the hospital.

## Documents

Upload with `multipart/form-data`, not JSON.

`POST /platform/legal/cases/{id}/documents`

| Field | Value |
|---|---|
| `category` | Hospital Registration, Entity Registration, Authorized Representative, Tax / GST Details, Hospital License, or Service Agreement |
| `file` | PDF, JPG, PNG, or WEBP, up to 5 MB |

Download: `GET /platform/legal/cases/{id}/documents/{document_id}`

`POST /platform/legal/cases/{id}/documents/{document_id}/verify`

`POST /platform/legal/cases/{id}/documents/{document_id}/request-changes`

No body on verify, request-changes, or download.

## Checklist

`PATCH /platform/legal/cases/{id}/checklist`

```json
{
  "items": [
    { "id": 1, "status": "Verified", "note": "Registration matches the lead." }
  ]
}
```

`status` is `Pending`, `Verified`, `Issue Found`, or `Not applicable`. Send the checklist item id from the case, not a made-up index.

## Finance terms

`PATCH /platform/legal/cases/{id}/finance`

Amounts are whole rupees. `discount` is required. The other fields can be omitted and then use the defaults shown here.

```json
{
  "discount": 18,
  "standard_price": 0,
  "years": 1,
  "implementation_fee": 0,
  "training_fee": 0,
  "tax_percent": 0,
  "advance_percent": 0,
  "credit_days": 0,
  "frequency": "Annual",
  "modules": null,
  "gstin": null,
  "po_required": "No",
  "invoice_email": null
}
```

`frequency` is `Annual`, `Half-yearly`, `Quarterly`, or `Monthly`. `po_required` is `Yes` or `No`.

If `discount` is over 10, the response `escalation` becomes `Not requested`. Show a “Request Finance Head approval” button only in that state.

## Escalation

`POST /platform/legal/cases/{id}/escalation/request`

No body. This sets `escalation` to `Pending`.

`POST /platform/legal/cases/{id}/escalation`

```json
{ "status": "Approved" }
```

`status` is `Approved` or `Rejected`. Call this only after the request, when `escalation` is `Pending`. Calling it earlier returns 409.

## Decision

`POST /platform/legal/cases/{id}/decision`

```json
{
  "status": "Approved",
  "reason": "Papers and price are complete."
}
```

`status` is `Approved`, `Conditionally Approved`, `Changes Requested`, or `Rejected`. `reason` is always required.

For Conditionally Approved, also send:

```json
{
  "status": "Conditionally Approved",
  "reason": "Approve after the licence arrives.",
  "condition": "Upload the hospital licence.",
  "condition_owner": "Accounts Team"
}
```

`condition_owner` is `Accounts Team` or `Sales Owner`. Both `condition` and `condition_owner` are required for this status.

Approved and Conditionally Approved return 422 until all of these are true:

- at least four documents
- every document is Verified
- every checklist item is Verified or Not applicable
- if the discount is over 10, `escalation` is Approved

Do not mark the payment as received on this screen. The response `advance_received` stays false.

## Resubmit

`POST /platform/legal/cases/{id}/resubmit`

No body. Use it only when the case status is Changes Requested. The status becomes In Review.

## Accounts

`GET /platform/registrations?status=agreed`

This list includes a lead only after the legal case is Approved. Do not build this list from `GET /platform/legal/cases`. That call is for the legal role.

`POST /platform/legal/cases/{id}/payment-confirmation`

No body. Accountant only. Call it after the case is Approved. A second call returns 409.

Then use the existing hospital register endpoint. It returns 409 if the case is not Approved or the advance has not been recorded.

## What not to do

- Do not send Society or School cases. This backend is hospital only.
- Do not hide a button and treat that as permission. The API returns 403 for the wrong role.
- Do not fill the price with the sample amounts from the prototype. Leave the fields at 0 until the user enters the real price.
- Do not call the decision API from the CRM screen.
