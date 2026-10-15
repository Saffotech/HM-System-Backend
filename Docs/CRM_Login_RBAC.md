# CRM login (frontend)

Base URL: `http://127.0.0.1:8000`

Send the token on every call after login:

`Authorization: Bearer <access_token>`

CRM is a platform user. `role` is `crm`, `tenant_id` is `null`, and `permissions` includes `leads:manage`. A hospital user must not open this portal.

Test account: `crm@saffocare.example` / `Demo1234`

## Login

`POST /auth/login`

```json
{ "email": "crm@saffocare.example", "password": "Demo1234" }
```

Use from the response:

| Field | Use |
|---|---|
| `access_token` | Send on later calls |
| `refresh_token` | Get a new access token |
| `role` | Must be `crm` |
| `permissions` | Must include `leads:manage` |
| `user_id` | Signed-in user |
| `first_name` | Display name (full name is on `/auth/me`) |
| `tenant_id` | `null` for CRM |

`401` wrong email or password. `403` account deactivated.

## After login

| Call | Purpose |
|---|---|
| `GET /auth/me` | Name, email, role, permissions |
| `POST /auth/refresh` | Body: `{ "refresh_token": "..." }` |
| `POST /auth/logout` | Bearer token required |

## CRM calls

All of these need the bearer token and `leads:manage`.

| Call | Purpose |
|---|---|
| `GET /crm/leads` | Her leads, plus unclaimed New leads. Includes activity history. |
| `GET /crm/leads/{id}` | One lead |
| `POST /crm/leads` | Add lead |
| `POST /crm/leads/{id}/claim` | Claim an unclaimed New lead |
| `POST /crm/leads/{id}/contacts` | Log a contact |
| `POST /crm/leads/{id}/follow-up` | Set or move a follow-up |
| `POST /crm/leads/{id}/notes` | Add a note |
| `PATCH /crm/leads/{id}` | Edit lead details |
| `POST /crm/leads/{id}/agree` | Send to Accounts (`Contacted` only) |
| `POST /crm/leads/{id}/close` | Mark not interested |
| `POST /crm/leads/{id}/reopen` | Reopen a closed lead |

`401` means sign in again. `403` means this user does not have `leads:manage`.
