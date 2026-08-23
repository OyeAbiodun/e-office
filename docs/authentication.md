# Authentication and identity

## Tenant model

An organization is the tenant root and every account belongs to exactly one
organization. Users, workspaces, roles, refresh credentials, sessions, and audit events
are tied to explicit UUID identifiers. Email is globally unique so login needs only an
email address and password; the backend resolves tenant context from the identity.

First-run bootstrap creates one organization, its default workspace, the six default
roles, and the initial Super Admin in a single database transaction.

## Credential model

- Passwords are validated against a 12–128 character complexity policy and stored using
  Argon2id.
- Access tokens are signed JWTs containing subject, tenant, permissions, issuer,
  audience, token type, issued-at time, and a short expiry.
- Refresh tokens are 256-bit opaque values. Only SHA-256 lookup hashes are persisted.
- Every refresh rotates the credential. Reuse of a consumed token revokes its entire
  token family and associated sessions.
- Browser refresh tokens use an HttpOnly, SameSite cookie. State-changing cookie flows
  require a matching double-submit CSRF header and cookie.
- Password reset and email verification use separately scoped, hashed, expiring,
  single-use tokens.

Access tokens are kept in frontend memory. The frontend restores authentication by
rotating the HttpOnly refresh cookie at startup; it does not persist access tokens in
local storage.

## Default roles

- Super Admin
- Admin
- Meeting Organizer
- Team Manager
- Employee
- Guest

Permissions are declared once in `auth/domain/permissions.py`. Future endpoints use
`require_permission(Permissions.<CAPABILITY>)` at the FastAPI boundary.

## Endpoints

| Method | Path | Authentication |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Public, rate-limited |
| POST | `/api/v1/auth/login` | Public, rate-limited |
| POST | `/api/v1/auth/refresh` | Refresh credential + CSRF for cookies |
| POST | `/api/v1/auth/logout` | Bearer + current refresh cookie |
| GET | `/api/v1/auth/me` | Bearer |
| POST | `/api/v1/auth/change-password` | Bearer |
| POST | `/api/v1/auth/forgot-password` | Public, enumeration-safe |
| POST | `/api/v1/auth/reset-password` | One-time reset token |
| POST | `/api/v1/auth/verify-email` | One-time verification token |
| POST | `/api/v1/auth/resend-verification` | Public, enumeration-safe |
| GET | `/api/v1/auth/sessions` | Bearer |
| DELETE | `/api/v1/auth/sessions/{id}` | Bearer; ownership enforced |
| DELETE | `/api/v1/auth/sessions` | Bearer |

Interactive request/response documentation is available at `/api/docs`.

## Account defense and auditing

Failed passwords increment a persistent counter. The configured threshold produces a
temporary lock; successful login clears the counter. Redis supplies fixed-window hooks
for public authentication endpoints. Redis failure does not make identity unavailable,
but `/ready` reports the degraded dependency for monitoring.

Security-relevant actions append structured audit records. Passwords, raw tokens, and
other credentials are never included in audit metadata or application logs.

Forgot-password and resend-verification responses are identical whether an identity
exists, preventing account enumeration. Identity email uses configured SMTP in
production and a local `.eml` outbox during development.
