# Environment variables

Runtime backend settings use the `MEETINGHQ_` prefix. Permanent first-run bootstrap
settings intentionally use the exact `INITIAL_*` names below. Never commit `.env` or real
production credentials.

| Variable | Required in production | Default / example | Purpose |
| --- | --- | --- | --- |
| `MEETINGHQ_ENVIRONMENT` | Yes | `local` | Runtime name; non-local environments emit JSON logs |
| `MEETINGHQ_LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `MEETINGHQ_API_HOST` | No | `0.0.0.0` | API bind host |
| `MEETINGHQ_API_PORT` | No | `8000` | API bind port |
| `MEETINGHQ_RUN_MIGRATIONS` | Deployment-specific | `true` locally | Container entrypoint migration switch. Set `false` on API/worker workloads after a dedicated migration Job succeeds. |
| `MEETINGHQ_API_CORS_ORIGINS` | Yes | JSON array | Explicit trusted browser origins |
| `MEETINGHQ_TRUSTED_HOSTS` | Yes | JSON array | Accepted HTTP Host values; wildcards are rejected for staging/production |
| `MEETINGHQ_WEB_APP_URL` | Yes | absolute origin | Browser origin used for password, invitation, and verification links |
| `MEETINGHQ_DATABASE_URL` | Yes | PostgreSQL async URL | SQLAlchemy `postgresql+asyncpg` connection URL |
| `MEETINGHQ_DATABASE_POOL_SIZE` | No | `10` | Persistent PostgreSQL pool connections per API process |
| `MEETINGHQ_DATABASE_MAX_OVERFLOW` | No | `20` | Bounded burst connections above the base pool |
| `MEETINGHQ_DATABASE_POOL_TIMEOUT_SECONDS` | No | `30` | Maximum wait for an available connection |
| `MEETINGHQ_DATABASE_POOL_RECYCLE_SECONDS` | No | `1800` | Recycle aging connections before infrastructure timeouts |
| `MEETINGHQ_REDIS_URL` | Yes | Redis URL | Cache and coordination connection |
| `MEETINGHQ_JWT_SECRET` | Yes | local-only value | HMAC signing secret, minimum 32 characters |
| `MEETINGHQ_JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `MEETINGHQ_JWT_ACCESS_TOKEN_TTL_MINUTES` | No | `15` | Future access-token lifetime |
| `MEETINGHQ_REFRESH_TOKEN_TTL_DAYS` | No | `30` | Rotating refresh-session lifetime |
| `MEETINGHQ_JWT_ISSUER` | Yes | `meetinghq` | Expected JWT issuer |
| `MEETINGHQ_JWT_AUDIENCE` | Yes | `meetinghq-api` | Expected JWT audience |
| `MEETINGHQ_REFRESH_COOKIE_NAME` | No | `meetinghq_refresh` | HttpOnly refresh cookie name |
| `MEETINGHQ_CSRF_COOKIE_NAME` | No | `meetinghq_csrf` | Double-submit CSRF cookie name |
| `MEETINGHQ_SECURE_COOKIES` | Yes | `false` locally | Must be `true` behind production HTTPS |
| `MEETINGHQ_PASSWORD_RESET_TTL_MINUTES` | No | `30` | Password reset token lifetime |
| `MEETINGHQ_EMAIL_VERIFICATION_TTL_HOURS` | No | `24` | Verification token lifetime |
| `MEETINGHQ_LOGIN_MAX_FAILURES` | No | `5` | Failures before temporary lock |
| `MEETINGHQ_LOGIN_LOCK_MINUTES` | No | `15` | Temporary account lock duration |
| `MEETINGHQ_AUTH_RATE_LIMIT_REQUESTS` | No | `10` | Authentication requests per fixed window |
| `MEETINGHQ_AUTH_RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate-limit window |
| `MEETINGHQ_AUTH_RATE_LIMIT_FAIL_CLOSED` | Yes | `false` locally | Must be `true` in staging/production so Redis loss cannot bypass authentication throttling |
| `MEETINGHQ_DELIVERY_MAX_ATTEMPTS` | No | `5` | Durable outbound delivery attempt limit |
| `MEETINGHQ_DELIVERY_RETRY_BASE_SECONDS` | No | `60` | Base delay for exponential durable delivery retries |
| `INITIAL_SUPER_ADMIN_EMAIL` | Empty installation | none | Initial verified Super Admin email |
| `INITIAL_SUPER_ADMIN_PASSWORD` | Empty installation | none | Initial administrator password; rotate after login |
| `INITIAL_SUPER_ADMIN_FIRST_NAME` | Empty installation | none | Initial administrator first name |
| `INITIAL_SUPER_ADMIN_LAST_NAME` | Empty installation | blank allowed | Initial administrator last name |
| `INITIAL_ORGANIZATION_NAME` | Empty installation | none | Permanent first organization name |
| `INITIAL_WORKSPACE_NAME` | Empty installation | none | Permanent default workspace name |
| `VITE_API_URL` | Yes | `http://localhost:8000/api/v1` | API base URL compiled into the web bundle |
| `POSTGRES_DB` | Compose only | `meetinghq` | Development database name |
| `POSTGRES_USER` | Compose only | `meetinghq` | Development database user |
| `POSTGRES_PASSWORD` | Compose only | local-only value | Development database password |
| `MEETINGHQ_POSTGRES_PUBLISHED_PORT` | Compose only | `5432` | Host port; select an isolated value when another stack is running |
| `MEETINGHQ_REDIS_PUBLISHED_PORT` | Compose only | `6379` | Host port; select an isolated value when another stack is running |
| `MEETINGHQ_API_PUBLISHED_PORT` | Compose only | `8000` | API host port |
| `MEETINGHQ_WEB_PUBLISHED_PORT` | Compose only | `5173` | Web host port |
| `MEETINGHQ_STORAGE_PROVIDER` | Yes | `local` | Storage adapter selection |
| `MEETINGHQ_LOCAL_STORAGE_PATH` | Local storage only | `./storage` | Root for opaque local objects |
| `MEETINGHQ_PUBLIC_STORAGE_URL` | Local storage only | `/api/v1/storage` | Stable object URL prefix |
| `MEETINGHQ_INVITATION_TTL_DAYS` | No | `7` | Invitation validity window |
| `MEETINGHQ_EMBEDDED_REMINDER_WORKER` | Yes | `true` locally | Run reminders inside the API. Set `false` when production uses the dedicated `python -m meetinghq_api.worker` job. |

Production secrets belong in the deployment platform's secret manager. Because Vite
variables are embedded in public browser assets, never put secrets in `VITE_*`.

Tenant SMTP host, security mode, credentials, sender identity, retry policy, and enabled
state are administered through **Administration → Integration Center → Email → SMTP** and
stored encrypted in PostgreSQL. `MEETINGHQ_SMTP_*` values are only the installation-level
fallback for flows that cannot yet resolve a tenant; they are not the routine provider
configuration interface.

The Compose PostgreSQL service fixes both the container and session timezone to UTC. For
an externally managed PostgreSQL deployment, configure the `meetinghq` database with
`ALTER DATABASE meetinghq SET timezone TO 'UTC'`; application-facing timestamp columns use
`TIMESTAMP WITH TIME ZONE`, while each user's IANA timezone is retained for display and
scheduling semantics.

The bootstrap variables are read only when the organization table is empty. Once any
organization exists, startup does not recreate or modify installation records.
