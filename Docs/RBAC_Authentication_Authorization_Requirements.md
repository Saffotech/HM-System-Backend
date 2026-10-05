# RBAC & Authentication/Authorization Requirements

## 1. Document Purpose

This document defines the requirements and proposed database design for
the **RBAC (Role-Based Access Control), Authentication, and
Authorization system** of the multi-tenant Society Management Tool.

The purpose of this document is to provide a common specification for
developers, backend developers, frontend developers, QA, architects, and
reviewers before implementation.

> **Important:** This is a requirements/design document. Tables, fields,
> relationships, and flows should be finalized after the required
> business rules are investigated and confirmed.

------------------------------------------------------------------------

# 2. RBAC Overview

## 2.1 What is RBAC?

RBAC (Role-Based Access Control) is an access-control model in which
permissions are assigned to roles, and roles are assigned to users.

Instead of directly assigning individual permissions to every user:

``` text
User
  ↓
Role
  ↓
Permissions
```

Example:

``` text
User: Rahul
   ↓
Role: Security
   ↓
Permissions:
    visitor.view
    visitor.create
    visitor.update
```

If the Security role does not contain `resident.delete`, Rahul must not
be allowed to delete a resident.

------------------------------------------------------------------------

## 2.2 Why are we using RBAC?

RBAC is required because the Society Management Tool will have different
types of users with different responsibilities.

The system should:

-   Control access based on roles and permissions.
-   Prevent unauthorized users from accessing protected APIs.
-   Allow authorized administrators to manage roles and permissions.
-   Reuse permissions across multiple users.
-   Support multiple societies/tenants.
-   Keep tenant data isolated.
-   Make authorization easier to maintain as new modules are added.
-   Provide a structured security model for the complete application.

Example:

``` text
Society Admin
    ↓
Can access permitted society-management features

Security
    ↓
Can access permitted visitor/security features

Resident
    ↓
Can access permitted resident features
```

------------------------------------------------------------------------

## 2.3 How RBAC will work in our tool

The high-level authorization flow will be:

``` text
User
  ↓
Login / Authentication
  ↓
Identify User
  ↓
Identify Tenant/Society
  ↓
Identify User Role(s)
  ↓
Load Permissions
  ↓
API Request
  ↓
Check Required Permission
  ↓
Tenant/Data Access Check
  ↓
Allow / Deny
```

For a protected API:

``` text
POST /api/residents
        ↓
Required Permission:
resident.create
        ↓
Does user's role have permission?
        ↓
    YES        NO
     ↓          ↓
   Allow       403
```

------------------------------------------------------------------------

# 3. Features

The following features are part of the initial RBAC and
authentication/authorization scope.

1.  Society Registration
2.  Login
3.  Logout
4.  User Management
5.  Role Management
6.  Permission Management
7.  User-Role Assignment
8.  Role-Permission Assignment
9.  Tenant/Society Management
10. Password Management
11. Account Management
12. Audit Logs

Each feature must be investigated and documented before implementation.

------------------------------------------------------------------------

# 4. Feature Requirements

For every feature, the investigation should answer:

-   **Purpose** --- Why does the feature exist?
-   **Required Fields** --- What data is required?
-   **Business Rules** --- What rules must be followed?
-   **Who Can Perform It** --- Which role/permission can perform it?
-   **Backend Operation** --- What happens in the backend?
-   **Data Flow** --- How does data move between frontend, API, service,
    and database?
-   **Database Impact** --- Which tables are created/read/updated?
-   **Validation** --- What validations are required?
-   **Error Cases** --- What can go wrong?
-   **Security Considerations** --- What must be protected?

------------------------------------------------------------------------

# 5. Society Registration

## 5.1 Purpose

Allow the **Super Admin** to register a new society/tenant on the
platform.

The authority to register a new society belongs to the **Super Admin**.

``` text
Super Admin
     ↓
Register New Society
     ↓
Create Tenant/Society
```

Society Admins and ordinary users must not be allowed to register new
societies.

------------------------------------------------------------------------

## 5.2 Required Fields

### Society Details

-   Society Name
-   Society Code
-   Society Email
-   Society Phone
-   Address
-   City
-   State
-   Pincode
-   Status

### Initial Society Admin Details

-   Admin Name
-   Admin Email
-   Admin Password

The exact fields should be finalized after business requirements are
confirmed.

------------------------------------------------------------------------

## 5.3 Business Rules

Initial proposed rules:

1.  Only Super Admin can register a society.
2.  Society Code must be unique.
3.  Society Email must be unique.
4.  Admin Email must follow the finalized email uniqueness rule.
5.  Email must be validated.
6.  Email normalization should be defined.
7.  Password must follow the password policy.
8.  The initial admin must be associated with the newly created society.
9.  The initial admin must receive the appropriate Society Admin role.
10. Duplicate society registration must be prevented.
11. Society status must be initialized correctly.
12. Registration must be performed transactionally so that partial
    creation does not leave inconsistent data.

------------------------------------------------------------------------

## 5.4 Registration Flow

``` text
Super Admin
     ↓
Open Society Registration
     ↓
Enter Society Details
     ↓
Enter Initial Admin Details
     ↓
Validate Request
     ↓
Check Society Code Uniqueness
     ↓
Check Society Email Uniqueness
     ↓
Check Admin Email Rule
     ↓
Create Tenant/Society
     ↓
Create Admin User
     ↓
Assign Society Admin Role
     ↓
Assign Required Permissions
     ↓
Create Audit Record
     ↓
Registration Complete
```

------------------------------------------------------------------------

# 6. Login

## 6.1 Purpose

Allow a registered user to securely authenticate and receive access to
the system.

------------------------------------------------------------------------

## 6.2 Required Fields

Initial proposed fields:

``` text
Email
Password
```

If one email can belong to multiple societies, the login design must
define how the correct tenant/society is selected.

------------------------------------------------------------------------

## 6.3 Business Rules

1.  User must exist.
2.  Password must be verified against the stored password hash.
3.  User account must be active.
4.  User must belong to a valid tenant.
5.  Authentication token must be generated only after successful
    authentication.
6.  Role and permission information must be resolved according to the
    finalized authorization design.
7.  Failed login attempts and security logging requirements should be
    defined.

------------------------------------------------------------------------

## 6.4 Login Flow

``` text
Email + Password
       ↓
Validate Request
       ↓
Find User
       ↓
Verify Password
       ↓
Check Account Status
       ↓
Identify Tenant
       ↓
Resolve Role(s)
       ↓
Resolve Permissions
       ↓
Generate Authentication Token
       ↓
Return Authentication Response
```

------------------------------------------------------------------------

# 7. Logout

## 7.1 Purpose

Terminate the user's authenticated session according to the selected
token/session strategy.

------------------------------------------------------------------------

## 7.2 Proposed Flow

``` text
Logout Request
      ↓
Validate Authentication
      ↓
Invalidate Refresh Token / Session
      ↓
Create Audit Record
      ↓
Logout Complete
```

If the system uses short-lived stateless access tokens, logout behavior
must distinguish between the access token and refresh/session mechanism.

------------------------------------------------------------------------

# 8. User Management

## 8.1 Purpose

Allow authorized administrators to manage users within their permitted
tenant.

------------------------------------------------------------------------

## 8.2 Features

-   Create user
-   View user
-   Update user
-   Activate user
-   Deactivate user
-   Reset password
-   Assign role
-   Remove role
-   View user status
-   View relevant account information

------------------------------------------------------------------------

## 8.3 Proposed Flow

``` text
Administrator
      ↓
Authenticate
      ↓
Check user.create / user.update / etc.
      ↓
Validate User Data
      ↓
Check Tenant Scope
      ↓
Create / Update User
      ↓
Assign Role if required
      ↓
Create Audit Record
      ↓
Complete
```

------------------------------------------------------------------------

# 9. Role Management

## 9.1 Purpose

Allow authorized administrators to create and manage roles.

------------------------------------------------------------------------

## 9.2 Features

-   Create role
-   View role
-   Update role
-   Activate/deactivate role
-   Delete role where permitted

------------------------------------------------------------------------

## 9.3 Example

``` text
Security
   ↓
visitor.view
visitor.create
visitor.update
```

------------------------------------------------------------------------

## 9.4 Proposed Flow

``` text
Administrator
      ↓
Authenticate
      ↓
Check role.create / role.update / etc.
      ↓
Validate Role
      ↓
Create / Update Role
      ↓
Create Audit Record
```

------------------------------------------------------------------------

# 10. Permission Management

## 10.1 Purpose

Define individual actions that can be performed within application
modules.

------------------------------------------------------------------------

## 10.2 Permission Naming Convention

Recommended format:

``` text
<module>.<action>
```

Examples:

``` text
resident.view
resident.create
resident.update
resident.delete

visitor.view
visitor.create
visitor.update
visitor.delete

billing.view
billing.create
billing.update
billing.delete
```

The final list of modules and permissions must be defined from the
complete application feature list.

------------------------------------------------------------------------

## 10.3 Permission Rules

-   Permission codes should be unique.
-   Permission naming must be consistent.
-   Permissions should represent actions, not UI buttons.
-   Backend APIs must enforce permissions.
-   Removing a permission from a role must remove that access for users
    receiving the permission through that role.

------------------------------------------------------------------------

# 11. User-Role Assignment

## 11.1 Purpose

Connect users with roles.

``` text
User
  ↓
User_Roles
  ↓
Role
```

Example:

``` text
Rahul
  ↓
Security
```

------------------------------------------------------------------------

## 11.2 Business Rules

-   Only authorized administrators can assign roles.
-   The role must be valid.
-   The role must be valid for the user's tenant where tenant-scoped
    roles are used.
-   Duplicate user-role assignments must be prevented.
-   Removing a role must update the user's effective permissions.

------------------------------------------------------------------------

# 12. Role-Permission Assignment

## 12.1 Purpose

Connect roles with permissions.

Example:

``` text
Security
   ↓
visitor.view
visitor.create
visitor.update
```

------------------------------------------------------------------------

## 12.2 Business Rules

-   Only authorized administrators can change role permissions.
-   Permission must exist before assignment.
-   Duplicate role-permission mappings must be prevented.
-   Changes must be auditable.
-   Effective access must reflect the latest role-permission
    configuration.

------------------------------------------------------------------------

# 13. Tenant/Society Management

## 13.1 Purpose

Support multiple societies on the same platform while keeping their data
logically isolated.

``` text
Platform
│
├── Society A
│    ├── Users
│    ├── Residents
│    ├── Visitors
│    └── Billing
│
├── Society B
│    ├── Users
│    ├── Residents
│    ├── Visitors
│    └── Billing
│
└── Society C
     ├── Users
     ├── Residents
     ├── Visitors
     └── Billing
```

------------------------------------------------------------------------

## 13.2 Tenant Rules

-   Every tenant must have a unique identifier.
-   Tenant-specific users must be linked to a tenant.
-   Tenant-specific data must be scoped to the correct tenant.
-   A user must not access another tenant's data.
-   Tenant context must come from trusted authentication/server-side
    information rather than blindly trusting client input.

------------------------------------------------------------------------

# 14. Password Management

## 14.1 Features

-   Change password
-   Forgot password
-   Reset password
-   Password validation
-   Password hashing

------------------------------------------------------------------------

## 14.2 Security Rules

-   Never store plain-text passwords.
-   Store only password hashes.
-   Use a strong password hashing algorithm.
-   Reset tokens must expire.
-   Reset tokens should be single-use.
-   Password reset operations should be auditable where appropriate.

------------------------------------------------------------------------

# 15. Account Management

## 15.1 Account Status

Initial proposed statuses:

``` text
ACTIVE
INACTIVE
SUSPENDED
```

The final status model must be confirmed with business requirements.

------------------------------------------------------------------------

## 15.2 Rules

-   Inactive/suspended accounts must not be allowed to access protected
    resources.
-   Account status changes must be authorized.
-   Important status changes should be audited.

------------------------------------------------------------------------

# 16. Audit Logs

## 16.1 Purpose

Record important security and administrative activities.

Examples:

``` text
User Login
User Logout
User Created
User Updated
User Disabled
Role Created
Role Updated
Permission Assigned
Permission Removed
Password Reset
Society Registered
```

------------------------------------------------------------------------

## 16.2 Proposed Audit Fields

``` text
id
tenant_id
user_id
action
resource
resource_id
details
ip_address
created_at
```

The exact fields should be finalized according to the audit
requirements.

------------------------------------------------------------------------

# 17. RBAC Structure

The core RBAC structure is:

``` text
Tenant / Society
       ↓
     Users
       ↓
   User Roles
       ↓
     Roles
       ↓
Role Permissions
       ↓
   Permissions
```

More technically:

``` text
Tenant
  │
  └── Users
       │
       └── User_Roles
             │
             └── Roles
                   │
                   └── Role_Permissions
                         │
                         └── Permissions
```

------------------------------------------------------------------------

# 18. Database Tables

## 18.1 Initial Core Tables

  ---------------------------------------------------------------------------
  \#                      Table                     Purpose
  ----------------------- ------------------------- -------------------------
  1                       `tenants`                 Stores
                                                    societies/organizations

  2                       `users`                   Stores user accounts

  3                       `roles`                   Stores roles

  4                       `permissions`             Stores available
                                                    permissions

  5                       `user_roles`              Maps users to roles

  6                       `role_permissions`        Maps roles to permissions

  7                       `audit_logs`              Stores security and
                                                    administrative activities

  8                       `refresh_tokens`          Stores refresh-token
                                                    information if refresh
                                                    tokens are used

  9                       `password_reset_tokens`   Handles password-reset
                                                    requests
  ---------------------------------------------------------------------------

Optional:

``` text
user_sessions
```

This can be added if device/session management is required.

------------------------------------------------------------------------

# 19. Table Investigation Requirements

Before finalizing each table, investigate and document:

1.  Table purpose
2.  Required columns
3.  Data types
4.  Primary key
5.  Foreign keys
6.  Nullable/non-nullable fields
7.  Unique constraints
8.  Composite unique constraints
9.  Indexes
10. Default values
11. Status fields
12. Created/updated timestamps
13. Soft-delete requirements
14. Tenant ownership
15. Cascade/restrict behavior
16. Data retention requirements

------------------------------------------------------------------------

# 20. Proposed Table Structures

> These are proposed structures and must be validated against the
> complete business requirements before implementation.

## 20.1 `tenants`

``` text
id              PK
name
code
email
phone
address
city
state
pincode
status
created_at
updated_at
```

Potential constraints:

``` text
id   → Primary Key
code → Unique
email → Unique (if society email is globally unique)
```

------------------------------------------------------------------------

## 20.2 `users`

``` text
id
tenant_id       FK → tenants.id
name
email
password_hash
status
created_at
updated_at
last_login_at
```

The final email uniqueness rule must be confirmed before implementation.

------------------------------------------------------------------------

## 20.3 `roles`

``` text
id
tenant_id       FK → tenants.id
name
description
status
created_at
updated_at
```

The design must decide whether roles are:

-   Global/system roles
-   Tenant-specific roles
-   Or a combination of both

------------------------------------------------------------------------

## 20.4 `permissions`

``` text
id
code
module
action
description
created_at
updated_at
```

Example:

``` text
resident.view
resident.create
resident.update
resident.delete
```

------------------------------------------------------------------------

## 20.5 `user_roles`

``` text
id
user_id         FK → users.id
role_id         FK → roles.id
created_at
```

Recommended unique constraint:

``` text
(user_id, role_id)
```

------------------------------------------------------------------------

## 20.6 `role_permissions`

``` text
id
role_id         FK → roles.id
permission_id   FK → permissions.id
created_at
```

Recommended unique constraint:

``` text
(role_id, permission_id)
```

------------------------------------------------------------------------

## 20.7 `audit_logs`

``` text
id
tenant_id       FK → tenants.id
user_id         FK → users.id
action
resource
resource_id
details
ip_address
created_at
```

------------------------------------------------------------------------

## 20.8 `refresh_tokens`

If refresh-token authentication is selected:

``` text
id
user_id         FK → users.id
token_hash
expires_at
revoked_at
created_at
```

------------------------------------------------------------------------

## 20.9 `password_reset_tokens`

``` text
id
user_id         FK → users.id
token_hash
expires_at
used_at
created_at
```

------------------------------------------------------------------------

# 21. Table Relationships

## 21.1 Tenant to Users

``` text
tenants 1 ───────── N users
```

One tenant can have many users.

------------------------------------------------------------------------

## 21.2 Users to Roles

Conceptually:

``` text
users N ───────── M roles
```

Implemented through:

``` text
user_roles
```

------------------------------------------------------------------------

## 21.3 Roles to Permissions

Conceptually:

``` text
roles N ───────── M permissions
```

Implemented through:

``` text
role_permissions
```

------------------------------------------------------------------------

## 21.4 Authentication Relationships

``` text
users 1 ───────── N refresh_tokens
users 1 ───────── N password_reset_tokens
```

------------------------------------------------------------------------

## 21.5 Audit Relationships

``` text
tenants 1 ───────── N audit_logs
users   1 ───────── N audit_logs
```

------------------------------------------------------------------------

# 22. Data Flow

## 22.1 Society Registration Flow

``` text
Super Admin
     ↓
Society Registration
     ↓
Validate Society Details
     ↓
Check Society Code
     ↓
Check Society Email
     ↓
Validate Initial Admin
     ↓
Check Admin Email
     ↓
Create Tenant
     ↓
Create Admin User
     ↓
Assign Society Admin Role
     ↓
Assign Required Permissions
     ↓
Create Audit Log
     ↓
Registration Complete
```

------------------------------------------------------------------------

## 22.2 Login Flow

``` text
Email + Password
       ↓
Validate Request
       ↓
Find User
       ↓
Verify Password
       ↓
Check Account Status
       ↓
Identify Tenant
       ↓
Resolve Role(s)
       ↓
Resolve Permissions
       ↓
Generate Token
       ↓
Return Authentication Response
```

------------------------------------------------------------------------

## 22.3 User Creation Flow

``` text
Administrator
      ↓
Authenticate
      ↓
Check user.create Permission
      ↓
Validate Request
      ↓
Check Tenant Scope
      ↓
Create User
      ↓
Assign Role
      ↓
Create Audit Log
      ↓
Complete
```

------------------------------------------------------------------------

## 22.4 Role Creation Flow

``` text
Administrator
      ↓
Authenticate
      ↓
Check role.create Permission
      ↓
Validate Role
      ↓
Create Role
      ↓
Create Audit Log
      ↓
Complete
```

------------------------------------------------------------------------

## 22.5 Permission Assignment Flow

``` text
Administrator
      ↓
Authenticate
      ↓
Check Permission
      ↓
Select Role
      ↓
Select Permission
      ↓
Validate Role + Permission
      ↓
Create Role-Permission Mapping
      ↓
Create Audit Log
      ↓
Complete
```

------------------------------------------------------------------------

## 22.6 API Authorization Flow

``` text
API Request
     ↓
Authentication Token
     ↓
Validate Token
     ↓
Identify User
     ↓
Identify Tenant
     ↓
Resolve Role(s)
     ↓
Resolve Permissions
     ↓
Check Required Permission
     ↓
Check Tenant/Data Ownership
     ↓
 ┌─────────────┐
 │             │
ALLOW         DENY
 │             │
 ↓             ↓
Process       403
Request
```

------------------------------------------------------------------------

## 22.7 Logout Flow

``` text
Logout
 ↓
Validate Authentication
 ↓
Invalidate Refresh Token / Session
 ↓
Create Audit Log
 ↓
Logout Complete
```

------------------------------------------------------------------------

# 23. Tenant Isolation

Tenant isolation is a critical requirement for the multi-tenant
architecture.

Example:

``` text
Society A
 ├── User A
 ├── Resident A
 └── Visitor A

Society B
 ├── User B
 ├── Resident B
 └── Visitor B
```

If User A requests a resource:

``` text
User A
  ↓
Tenant A
  ↓
Requested Resource
  ↓
Check Resource Tenant ID
  ↓
Does Resource belong to Tenant A?
  ↓
YES → Continue
NO  → Reject
```

For every tenant-specific operation, the backend should validate:

``` text
1. Does the user have the required permission?
2. Does the requested resource belong to the user's tenant?
```

Both checks are required.

------------------------------------------------------------------------

# 24. Security Requirements

## 24.1 Password Security

-   Passwords must be hashed.
-   Plain-text passwords must never be stored.
-   Use a strong password hashing algorithm.
-   Apply a defined password policy.

## 24.2 Authentication Token Security

-   Tokens must be signed.
-   Token expiration must be defined.
-   Token signature must be validated.
-   Sensitive information should not be stored in tokens.
-   Refresh-token handling must be defined if refresh tokens are used.

## 24.3 Authorization Security

-   Authorization must be enforced on the backend.
-   Frontend button visibility is not a security mechanism.
-   Protected APIs must check required permissions.
-   Users must not be able to grant themselves permissions.

## 24.4 Tenant Security

-   Tenant context must be validated server-side.
-   Client-provided tenant IDs must not be trusted for authorization.
-   Cross-tenant access must be rejected.
-   Tenant-specific records must be correctly scoped.

## 24.5 Account Security

-   Inactive/suspended users must not access protected resources.
-   Account status changes must be authorized.
-   Password reset must be time-limited and single-use.

## 24.6 Audit Security

Important security and administrative operations should be recorded.

------------------------------------------------------------------------

# 25. Email Uniqueness Rule

This requirement must be finalized before implementing the `users`
table.

## Option A --- Globally Unique Email

One email address can belong to only one user across the complete
platform.

``` text
admin@gmail.com → Society A ✅
admin@gmail.com → Society B ❌
```

Database rule:

``` text
users.email → UNIQUE
```

## Option B --- Tenant-Level Unique Email

The same email can exist in different societies but only once within
each society.

``` text
admin@gmail.com → Society A ✅
admin@gmail.com → Society B ✅
```

Database rule:

``` text
(tenant_id, email) → UNIQUE
```

### Decision Required

The project team must explicitly select one rule before database
implementation.

------------------------------------------------------------------------

# 26. Permission Matrix

A permission matrix should be prepared after the final role list and
application modules are confirmed.

Example:

  -----------------------------------------------------------------------------
  Module       Permission    Super Admin      Society     Security     Resident
                                                Admin              
  ------------ ------------ ------------ ------------ ------------ ------------
  Society      register                ✓            ✗            ✗            ✗

  User         view                    ✓            ✓            ✗            ✗

  User         create                  ✓            ✓            ✗            ✗

  Role         create                  ✓            ✓            ✗            ✗

  Permission   assign                  ✓            ✓            ✗            ✗

  Resident     view                    ✓            ✓      Depends      Depends

  Visitor      view                    ✓            ✓            ✓      Depends

  Visitor      create                  ✓            ✓            ✓      Depends
  -----------------------------------------------------------------------------

> This table is illustrative. The final permission matrix must be
> created from the approved business requirements and actual modules.

------------------------------------------------------------------------

# 27. Final Database ER Diagram

The final document must contain a complete visualization of the database
after all tables and relationships have been finalized.

## 27.1 Core RBAC Relationship

``` text
                         ┌────────────────────────┐
                         │        TENANTS         │
                         │────────────────────────│
                         │ PK id                  │
                         │ name                   │
                         │ code                   │
                         │ email                  │
                         │ status                 │
                         └────────────┬───────────┘
                                      │
                                     1:N
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │         USERS          │
                         │────────────────────────│
                         │ PK id                  │
                         │ FK tenant_id           │
                         │ name                   │
                         │ email                  │
                         │ password_hash          │
                         │ status                 │
                         └────────────┬───────────┘
                                      │
                                     N:M
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │       USER_ROLES       │
                         │────────────────────────│
                         │ PK id                  │
                         │ FK user_id             │
                         │ FK role_id             │
                         └────────────┬───────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │         ROLES          │
                         │────────────────────────│
                         │ PK id                  │
                         │ FK tenant_id           │
                         │ name                   │
                         │ description            │
                         │ status                 │
                         └────────────┬───────────┘
                                      │
                                     N:M
                                      │
                                      ▼
                  ┌────────────────────────────────────┐
                  │         ROLE_PERMISSIONS           │
                  │────────────────────────────────────│
                  │ PK id                              │
                  │ FK role_id                         │
                  │ FK permission_id                   │
                  └──────────────────┬─────────────────┘
                                     │
                                     ▼
                         ┌────────────────────────┐
                         │      PERMISSIONS       │
                         │────────────────────────│
                         │ PK id                  │
                         │ code                   │
                         │ module                 │
                         │ action                 │
                         │ description            │
                         └────────────────────────┘
```

------------------------------------------------------------------------

## 27.2 Supporting Authentication Tables

``` text
┌────────────────────────┐
│     REFRESH_TOKENS     │
│────────────────────────│
│ PK id                  │
│ FK user_id             │
│ token_hash             │
│ expires_at             │
│ revoked_at             │
└────────────┬───────────┘
             │
             ▼
           USERS


┌────────────────────────┐
│  PASSWORD_RESET_TOKENS │
│────────────────────────│
│ PK id                  │
│ FK user_id             │
│ token_hash             │
│ expires_at             │
│ used_at                │
└────────────┬───────────┘
             │
             ▼
           USERS
```

------------------------------------------------------------------------

## 27.3 Audit Log Relationships

``` text
             ┌────────────────────┐
             │      TENANTS       │
             └─────────┬──────────┘
                       │
                       │ 1:N
                       ▼
             ┌────────────────────┐
             │     AUDIT_LOGS     │
             │────────────────────│
             │ PK id              │
             │ FK tenant_id       │
             │ FK user_id         │
             │ action             │
             │ resource           │
             │ resource_id        │
             │ details            │
             │ ip_address         │
             │ created_at         │
             └─────────▲──────────┘
                       │
                       │ N:1
                       │
                 ┌─────┴─────┐
                 │   USERS   │
                 └───────────┘
```

------------------------------------------------------------------------

# 28. Complete Database Relationship Overview

``` text
                                ┌─────────────────┐
                                │     TENANTS     │
                                └────────┬────────┘
                                         │
                              ┌──────────┼───────────┐
                              │          │           │
                             1:N        1:N         1:N
                              │          │           │
                              ▼          ▼           ▼
                           USERS       ROLES      AUDIT_LOGS
                              │
                              │
                             N:M
                              │
                              ▼
                         USER_ROLES
                              │
                              ▼
                            ROLES
                              │
                             N:M
                              │
                              ▼
                      ROLE_PERMISSIONS
                              │
                              ▼
                        PERMISSIONS


USERS
  │
  ├──────── 1:N ────────► REFRESH_TOKENS
  │
  └──────── 1:N ────────► PASSWORD_RESET_TOKENS
```

------------------------------------------------------------------------

# 29. Implementation Checklist

Before implementation, verify:

## Requirements

-   [ ] RBAC purpose approved
-   [ ] Super Admin responsibilities approved
-   [ ] Society registration requirements approved
-   [ ] Login requirements approved
-   [ ] Logout requirements approved
-   [ ] User management requirements approved
-   [ ] Role management requirements approved
-   [ ] Permission management requirements approved
-   [ ] Tenant requirements approved
-   [ ] Password requirements approved
-   [ ] Account status requirements approved
-   [ ] Audit requirements approved

## RBAC

-   [ ] Roles finalized
-   [ ] Permissions finalized
-   [ ] Permission naming convention finalized
-   [ ] User-role model finalized
-   [ ] Role-permission model finalized
-   [ ] Permission matrix approved

## Database

-   [ ] Tables finalized
-   [ ] Columns finalized
-   [ ] Primary keys finalized
-   [ ] Foreign keys finalized
-   [ ] Unique constraints finalized
-   [ ] Indexes finalized
-   [ ] Tenant relationships finalized
-   [ ] Cascade/restrict rules finalized
-   [ ] ER diagram updated

## Security

-   [ ] Password hashing strategy finalized
-   [ ] JWT/token strategy finalized
-   [ ] Token expiration finalized
-   [ ] Refresh-token strategy finalized
-   [ ] Password reset strategy finalized
-   [ ] Tenant isolation strategy finalized
-   [ ] Authorization middleware/dependency finalized
-   [ ] Audit strategy finalized

## Final Validation

-   [ ] Registration flow reviewed
-   [ ] Login flow reviewed
-   [ ] Logout flow reviewed
-   [ ] User flow reviewed
-   [ ] Role flow reviewed
-   [ ] Permission flow reviewed
-   [ ] Tenant isolation tested
-   [ ] Unauthorized API access tested
-   [ ] Cross-tenant access tested
-   [ ] Final database ER diagram matches implementation

------------------------------------------------------------------------

# 30. Decisions That Must Be Finalized Before Coding

The following are intentionally left as decisions because they affect
the database and authentication architecture:

1.  Is email globally unique or unique only within a tenant?
2.  Can one user have multiple roles?
3.  Are roles global, tenant-specific, or both?
4.  Are permissions global or tenant-specific?
5.  Is the Super Admin a global platform user?
6.  Can Society Admin create custom roles?
7.  Can Society Admin create/customize permissions?
8.  Which authentication token strategy will be used?
9.  Are refresh tokens required?
10. Are server-side sessions required?
11. What account statuses are required?
12. What password policy is required?
13. What actions must be audited?
14. Which tables require `tenant_id`?
15. What are the exact application modules and permissions?
16. What should happen when a role or permission is deleted/deactivated?
17. What are the required indexes and uniqueness constraints?
18. What is the required behavior for society deactivation?

These decisions should be resolved before the database schema and
production RBAC implementation are considered final.
