# Email and client document workflow

This document describes the backend implementation. The React ``public route is not implemented.

## Packages

- `Email/` sends mail through ZeptoMail using HTTPX, renders Jinja2 templates, and persists `email_jobs`.
- `client_documents/` owns the document master, upload requests, tokens, private files, and public submission.

Both packages use the existing SQLAlchemy `Base`, engine, and JWT stack.

## Recipient policy

Requests use the live lead `contact_email`, then `hospital_email`. If that value differs from the legal case snapshot, the API returns 409 until `confirm_live_recipient` is true. That flag does not accept an arbitrary address. Accounts registration still reads the live lead.

## Snapshots

Each request copies document type name, required flag, file rules, and order. Later master edits do not change that snapshot. New categories reach an existing case only through an additional-document request.

## Tokens

Raw tokens are returned only inside the encrypted email payload. The database stores SHA-256. Opening the link does not consume it. Completion, revocation, expiry, or a recipient change blocks further uploads.

## Email jobs

Statuses: PENDING, PROCESSING, RETRYING, SENT, FAILED, CANCELLED, AMBIGUOUS. SENT means ZeptoMail accepted the message. Ambiguous timeouts are not retried by the normal retry endpoint. Recovery runs only when `EMAIL_RECOVERY_ENABLED=true`.

## Storage

New legal files go to `LEGAL_PRIVATE_UPLOAD_DIR`. `/uploads/legal_documents/*` returns 404. Existing files stay until `python scripts/migrate_legal_uploads.py` is run against a chosen database. That script is not run automatically. Extension and signature checks are not malware scanning.

## Approval behavior

`_approval_blockers` still requires at least four current documents, all of them verified, plus the checklist. Superseded versions are not current and do not increase that count. Document master required flags do not add new Accounts rules.

## Permissions

| Permission | legal_finance | platform_admin |
|---|---|---|
| legal:request_documents | yes | no |
| legal:request_resubmission | yes | no |
| legal:document_requests_view | yes | no |
| legal:document_requests_revoke | yes | no |
| document_types:view | yes | yes |
| document_types:manage | no | yes |
| email_jobs:view | yes | yes |
| email_jobs:retry | yes | yes |

Run `python seed.py` after review so these permissions exist. No production demo user is created.

## Migrations

Heads before this work: `c9d0e1f2a3b4` and `b8d2f0c3e5a7`.

New revisions:

- `d1e2f3a4b5c6` merges those heads
- `e2f3a4b5c6d7` adds document and email tables and legal document columns

Do not run these against production from this change set. After review:

```text
alembic upgrade head
```

Downgrade of `e2f3a4b5c6d7` is a no-op so new history is not dropped accidentally.

## API order for Postman

1. `POST /platform/legal/cases/{case_id}/document-requests` with the legal finance JWT. Optional body: `{"confirm_live_recipient": true}`.
2. Read the mocked email payload in tests. The API does not return the raw token.
3. `GET /public/document-requests` with `Authorization: Bearer <token>`.
4. `POST /public/document-requests/uploads` multipart `item_id` and `file`.
5. `POST /public/document-requests/submit`.
6. Existing `POST /platform/legal/cases/{case_id}/documents/{id}/verify`.

## Frontend contract

The public page will be `/documents/upload?token=...`, outside employee auth. Send the token as a bearer token, render `requirements` dynamically, and do not log the token. Do not store it for a long time.

## Feature flags

`CLIENT_DOCUMENTS_ENABLED` gates the new APIs. Private storage blocking stays on when the flag is false. Email sending fails safely when ZeptoMail or the encryption key is missing.

## Known blockers

- No malware scanner.
- Existing legal files remain on disk until the migration script is reviewed and run.
- BackgroundTasks are not a durable queue. Enable recovery explicitly.
- Integration tests need an isolated `TEST_DATABASE_URL` and were not executed against PostgreSQL in this environment when that variable or driver was unavailable.
- Production must use HTTPS `FRONTEND_URL` when `ENVIRONMENT=production`.
