# CRM & Performance — frontend

Base URL: `http://127.0.0.1:8000`

Send `Authorization: Bearer <access_token>`. The signed-in role must be `platform_admin`.

`401` means sign in again. `403` means this role cannot call that API.

The page is Platform Admin → CRM & Performance. Do not call `GET /crm/leads` for this page. That route returns only the signed-in CRM user's leads plus unclaimed New leads, so the employee tables stay empty for the platform admin. Do not change `GET /crm/leads`.

## Calls

| Screen block | Call | Change |
|---|---|---|
| Company-wide leads (New, Contacted, Agreed, Registered, Not interested, Total) | `GET /platform/crm/analytics` | Already used. Leave it. It ignores the filters and is the all-time count. |
| Plan filter | `GET /platform/plans` | Already used. Leave it. |
| Employee cards, leaderboard, trend, follow-ups, revenue, employee detail | `GET /platform/crm/performance` | New. Replace `GET /crm/leads` and the empty invoice list in `useCrmPerformance`. |
| Hospital subscription status on a registered lead | `GET /tenants` | Keep. Match `lead.hospital_id` to `tenant_id`. |

Do not call `GET /platform/invoices` or `GET /platform/revenue` on this page. Invoices for this screen are inside `paid_invoices`.

## `GET /platform/crm/performance`

One response, three lists.

`employees`: CRM accounts.

```json
[{ "id": 5, "name": "Meera Iyer" }]
```

`leads`: every lead. Same fields as a CRM lead summary, plus `assignee_name`. Each lead includes `activities`.

`paid_invoices`: paid subscription invoices for hospitals linked from those leads. Pending invoices are not in this list.

```json
[{
  "tenant_id": 12,
  "amount": 4999,
  "payment_amount": 4999,
  "invoice_date": "2026-10-01",
  "status": "Paid"
}]
```

## What to change on the page

File: `panels/superAdmin/pages/tenants/crmPerformance/useCrmPerformance.js`

1. Load `GET /platform/crm/performance` instead of `listLeads()`.
2. Pass those leads into `buildCrmPerformance` as `onboarding`.
3. Set each lead's owner from `assignee_name`. The current `mapLead` sets `assignedTo` only when the lead is assigned to the signed-in user. On this page that user is the platform admin, so `assignedTo` becomes empty and the leaderboard says no employees match. Use `assignee_name` as `assignedTo`.
4. Set each activity `by` from `actor_name`.
5. Pass `employees` into `buildCrmPerformance` as `crmUsers`, with `portal: "crm"` and `role: "CRM"`. That puts a CRM user on the leaderboard even when they have no lead in the selected month.
6. Pass `paid_invoices` as `invoices`. Give each invoice `tenantId`, `status: "Paid"`, `amount`, `paymentAmount`, and `invoiceDate`. The existing `prepareLeads` links a registered lead to those invoices through `hospital_id` / `tenant_id` and sums the paid amount into revenue.
7. Keep `GET /tenants` and the date, employee, status, plan, and source filters. They already run inside `buildCrmPerformance`. The new API does not take those filters.

`GET /platform/crm/analytics` stays on the company-wide strip. Refresh on that strip reloads only that call.
