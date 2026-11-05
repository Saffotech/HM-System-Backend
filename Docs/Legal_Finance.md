# Legal and Finance — what was built and why

Legal and Finance sits between CRM and Accounts. A hospital lead used to go straight from “Agreed” to hospital registration. That skipped the paper check and the price check. The backend now opens one case for that lead and will not register the hospital until the case is approved and Accounts has recorded the advance.

Society and School are not included. One case is one hospital lead. The React folder `hms-legal-finance-react` was only the picture of the screens. No demo names and no sample rupee amounts are written into the database.

## Phase 1 — the path

CRM marks a lead Agreed. That creates one Legal and Finance case. Legal and Finance approves or rejects the papers and the price. Accounts records that the advance was paid. Accounts can register the hospital only after both are true: the case status is Approved, and the advance flag is set.

Approval does not set the advance flag. Those are different actions by different roles.

## Phase 2 — the role

`seed.py` adds the platform role `legal_finance` with permission `legal:review`. The user has no hospital. Platform Admin can create this user the same way as a CRM or Accountant user. The role cannot register a hospital and cannot record the advance. Those stay on the accountant permission `registrations:create`.

Run `python seed.py` so the role and permission exist in the database. Restart the API after code changes so new tables and columns are created.

## Phase 3 — the tables

| Table | Why it exists |
|---|---|
| `legal_cases` | One row per lead. Holds the copied hospital name, city, plan, discount, case status, escalation, and whether the advance was received. |
| `legal_documents` | Each uploaded file and its review status. |
| `legal_checklist_items` | The seven hospital checks and the reviewer note. |
| `legal_finance_terms` | The price in whole rupees. Starts at 0. |
| `legal_case_decisions` | The current decision, reason, and any condition. |

Status values, copied from the template:

- Case: New from CRM, In Review, Changes Requested, Conditionally Approved, Approved, Rejected.
- Document: Pending Review, Verified, Changes Requested.
- Checklist: Pending, Verified, Issue Found, Not applicable.
- Escalation: Not needed, Not requested, Pending, Approved, Rejected.

`Pending` is the extra escalation value used after someone asks the Finance Head and before the answer is recorded.

Every review change stores who did it and when: checklist `updated_by` / `updated_at`, finance `updated_by` / `updated_at`, escalation `escalation_by` / `escalation_at`, document review `reviewed_by` / `reviewed_at`, the decision `decided_by` / `decided_at`, the upload `uploaded_by`, and the advance `advance_received_by` / `advance_received_at`.

## Phase 4 — open the case from CRM

`agree_lead` calls `open_case_for_agreed_lead`. If that lead already has a case, the same row is returned. The new row copies `lead_id`, hospital name, city, and plan. Discount is 0 because a CRM lead has no discount. The seven checklist rows are created as Pending:

1. Legal entity identity verified
2. Hospital registration documents reviewed
3. Hospital address checked
4. Authorized signatory verified
5. Relevant licenses checked (where applicable)
6. Agreement and data protection terms reviewed
7. Contract signing requirements checked

No document rows are created.

## Phase 5 — the APIs

Prefix: `/platform/legal/cases`. The review calls require `legal:review` and the role `legal_finance`.

| Call | What it does |
|---|---|
| `GET /platform/legal/cases` | List cases |
| `GET /platform/legal/cases/{id}` | One case, with documents, checklist, finance, and decision |
| `POST /platform/legal/cases/{id}/documents` | Upload one file. Category is a form field. PDF, JPG, PNG, or WEBP, up to 5 MB. |
| `GET /platform/legal/cases/{id}/documents/{document_id}` | Download that file |
| `POST .../documents/{document_id}/verify` | Mark the document Verified |
| `POST .../documents/{document_id}/request-changes` | Mark the document Changes Requested |
| `PATCH /platform/legal/cases/{id}/checklist` | Save checklist status and notes |
| `PATCH /platform/legal/cases/{id}/finance` | Save the price terms |
| `POST /platform/legal/cases/{id}/escalation/request` | Ask the Finance Head. Status becomes Pending. |
| `POST /platform/legal/cases/{id}/escalation` | Record the Finance Head answer: Approved or Rejected |
| `POST /platform/legal/cases/{id}/decision` | Approve, conditionally approve, request changes, or reject |

Saving a discount over 10% sets escalation to Not requested. It does not ask the Finance Head. The request call does that. The answer call returns 409 until the escalation is Pending.

Document categories: Hospital Registration, Entity Registration, Authorized Representative, Tax / GST Details, Hospital License, Service Agreement.

## Phase 6 — the decision rules

`POST /platform/legal/cases/{id}/decision` returns 422 for Approved and Conditionally Approved unless all of these are true:

- at least four documents are uploaded
- every document is Verified
- every checklist item is Verified or Not applicable
- if the discount is over 10%, escalation is Approved

Conditionally Approved also needs a condition and an owner: `Accounts Team` or `Sales Owner`. Changes Requested and Rejected need a reason. None of these decisions set `advance_received`.

`POST /platform/legal/cases/{id}/resubmit` moves Changes Requested back to In Review. Any other status returns 409.

## Phase 7 — the Accounts gate

`GET /platform/registrations?status=agreed` returns a lead only when its legal case status is Approved. Before that, Accounts does not see it.

`POST /platform/legal/cases/{id}/payment-confirmation` records the advance. Only the accountant role can call it. The same action is still available at `POST /platform/legal/cases/{id}/advance`. It returns 409 if the case is not Approved or the advance was already recorded.

Hospital registration still uses the existing register endpoint. That endpoint returns 409 until the case is Approved and the advance has been recorded.

## Phase 8 — what the tests check

`tests/test_legal_finance_path.py` checks the rules, not the screen.

- One agreed lead creates one case. Opening it again does not create a second case.
- Approval with three documents returns 422.
- A discount of 18 without Finance Head approval returns 422.
- A complete case can be approved, and the advance stays unpaid.
- CRM calling the decision returns 403.
- Accounts does not see the lead in the agreed queue until the case is Approved.
- Conditional approval without an owner returns 422.
- Resubmit moves Changes Requested back to In Review.
