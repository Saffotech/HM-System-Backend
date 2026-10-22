# Platform APIs for the frontend

Base URL: `http://127.0.0.1:8000`

After login, send `Authorization: Bearer <access_token>` on every call.

`401` means sign in again. `403` means this role cannot call that API.

## Super Admin — create CRM or accountant staff

`POST /platform/staff`

Only a logged-in `platform_admin` can call this. CRM, accountant, and hospital roles receive 403. The role must be `crm` or `accountant`. The account is created with `tenant_id` null.

```json
{
  "first_name": "Meera",
  "last_name": "Iyer",
  "email": "meera@example.com",
  "password": "Secret123",
  "role": "crm"
}
```

`201` returns `user_id`, `first_name`, `last_name`, `email`, `role`, `tenant_id`, and `is_active`. It does not return the password. `409` means that email is already registered. `422` means the role is not `crm` or `accountant`.

## Login

`POST /auth/login`

```json
{ "email": "...", "password": "..." }
```

Keep `access_token`, `refresh_token`, `role`, `permissions`, `user_id`, `tenant_id`, and `hospital`.

| Role | tenant_id | Permission | Portal |
|---|---|---|---|
| `crm` | null | `leads:manage` | CRM |
| `accountant` | null | `registrations:create`, `invoices:manage` | Accounts |
| `admin`, `doctor`, `nurse`, and the other hospital roles | a hospital id | that role's permissions | That hospital only |

Hospital staff do not send `tenant_id` on later calls. The API uses the token and returns only that hospital.

`GET /auth/me` reloads the same user. `POST /auth/refresh` body is `{ "refresh_token": "..." }`. `POST /auth/logout` ends the session.

CRM test account: `crm@saffocare.example` / `Demo1234`

Accounts test account: `accounts@saffocare.example` / `Demo1234`

## CRM — permission `leads:manage`

| Call | When |
|---|---|
| `GET /crm/leads` | Dashboard, My Leads, follow-ups, conversions, performance |
| `GET /crm/leads/{id}` | Open one lead |
| `POST /crm/leads` | Add lead. `shared: true` leaves it unclaimed |
| `POST /crm/leads/{id}/claim` | Claim a New enquiry |
| `POST /crm/leads/{id}/contacts` | Log a call, email, WhatsApp, meeting, or visit |
| `POST /crm/leads/{id}/follow-up` | Set or move the follow-up |
| `POST /crm/leads/{id}/notes` | Add a note |
| `PATCH /crm/leads/{id}` | Edit contact and plan details |
| `POST /crm/leads/{id}/agree` | Status is `Contacted`. Sends the lead to Accounts |
| `POST /crm/leads/{id}/close` | Mark not interested |
| `POST /crm/leads/{id}/reopen` | Reopen a closed lead |

## Accounts — register a hospital

Permission `registrations:create`.

| Call | When |
|---|---|
| `GET /platform/registrations?status=agreed` | To register |
| `GET /platform/registrations?status=registered` | Already registered. Includes `hospital_code` |
| `GET /platform/registrations/{id}` | View one request and prefill the form |
| `POST /platform/registrations/{id}/register` | Create the hospital from that lead |

Register body: `code`, `address`, `pincode`, `admin_password`, `plan`, `billing_cycle`. Optional: `trial_period`, `tenant_status`.

Name, type, city, and contact come from the lead. Do not call `POST /tenants` from Accounts. That route needs `hospitals:create`.

A trial or suspended hospital does not get an invoice. An active hospital gets the first invoice in the same request.

## Accounts — invoices

Permission `invoices:manage`.

| Call | When |
|---|---|
| `GET /platform/invoices` | All invoices. Query `status` is `All`, `Pending`, `Overdue`, `Paid`, or `Failed`. Query `due` is `All`, `today`, or `month`. Query `tenant_id` is one hospital |
| `POST /platform/invoices/{id}/payments` | Record the full amount and mark it paid |

Payment body:

```json
{ "amount": 4999, "method": "Bank transfer", "reference": "UTR123", "paid_at": "2026-10-17", "notes": "" }
```

Methods: `Bank transfer`, `UPI`, `Card`, `Cheque`. `reference` is required except for `Card`.

Prices: Starter 4999, Professional 8999, Enterprise 14999 per month. Annual is that price times 10. Due date is 14 days after the invoice date.
