# Local development

## Docker workflow

1. Copy `.env.example` to `.env`.
2. Replace `MEETINGHQ_JWT_SECRET` with a random local value of at least 32 characters.
3. Run `docker compose up --build`.
4. Confirm `/api/v1/health` returns `{"status":"ok"}` and open the web application.

The API container applies Alembic migrations automatically. Set both Super Admin
variables before the first start if a platform administrator should be seeded.

Compose persists PostgreSQL and Redis data in named volumes. To stop containers while
preserving data, run `docker compose down`. Removing volumes is destructive and should
only be done deliberately with `docker compose down --volumes`.

## Native backend workflow

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "apps/api[dev]"
cp .env.example .env
uvicorn meetinghq_api.main:app --reload
```

On PowerShell, activate with `.venv\Scripts\Activate.ps1`. When PostgreSQL and Redis run
on the host, change their hostnames in `.env` from `postgres` and `redis` to `localhost`.

Run backend checks:

```bash
ruff check apps/api
ruff format --check apps/api
mypy --config-file apps/api/pyproject.toml
pytest apps/api
```

Create a migration after introducing models:

```bash
cd apps/api
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Migration files must be reviewed; autogeneration is not a substitute for understanding
the emitted DDL.

For a fresh database, configure the `INITIAL_*` variables from `.env.example`. API startup
automatically creates the first organization, workspace, owner membership, and Super
Admin after migrations. This permanent initializer is idempotent; it does nothing once
any organization exists.

## Native frontend workflow

```bash
cd apps/web
npm install
npm run dev
```

Run frontend checks:

```bash
npm run lint
npm run format:check
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
```

## Adding a backend feature

Add code inside the owning `meetinghq_api.modules.<feature>` package. A mature module
may grow `domain`, `application`, `infrastructure`, and `presentation` subpackages when
real code justifies them. Register its router in `api/v1/router.py` at the composition
boundary; do not import another feature's internal persistence models.

## Adding a frontend feature

Place page logic, API hooks, schemas, and feature-specific components under
`src/features/<feature>`. Promote a component to `src/components` only when it is part
of the application shell or has multiple real consumers.
