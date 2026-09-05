# Exotica ServiceTitan Platform — Module 1: Accounting Reconciliation

A production platform that reconciles invoices and payments between ServiceTitan and QuickBooks,
detects discrepancies, uses Claude AI to analyze them, and requires human approval before
write-back to source systems.

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- `uv` (https://github.com/astral-sh/uv)

### Local Development

1. **Clone and install dependencies**
   ```bash
   uv sync
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   ```

3. **Start services (Postgres + Redis)**
   ```bash
   docker compose up -d
   ```

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the API server**
   ```bash
   uv run uvicorn app:app --reload
   ```

   The API is now available at `http://localhost:8000`.

### Health checks
- Liveness: `curl http://localhost:8000/health`
- Readiness: `curl http://localhost:8000/ready`

### Running tests
```bash
uv run pytest --cov --cov-fail-under=85
```

### Type checking
```bash
uv run mypy --strict .
```

### Linting & formatting
```bash
uv run ruff check .
uv run black --check .
uv run black .  # to auto-fix
```

## Architecture

- **core/** — Foundation: config, logging, errors, database, tenant isolation, auth,
  secrets, audit log, idempotency, health checks.
- **integrations/** — Third-party clients (ServiceTitan, QuickBooks) — added in Step 2.
- **modules/** — Domain logic (accounting reconciliation, etc.) — added in Step 3+.
- **app.py** — FastAPI app factory, middleware registration, exception handlers.
- **migrations/** — Alembic schema versions.

## Key Architectural Principles

### Money as Decimal
All monetary values are Python `Decimal` objects, serialized as decimal strings in JSON
per the OpenAPI contract. Never floats.

### Audit everything
Every read/write against ServiceTitan or QuickBooks is recorded in an immutable audit log.
The log is append-only — there is no update or delete path, enforced at the repository and
database levels.

### Tenant isolation
Every query at the repository layer is scoped by `tenant_id`. A tenant-scoped token cannot
read another tenant's data.

### Secrets never in plaintext
OAuth tokens and API keys live in AWS Secrets Manager, referenced by ARN. Local dev uses
env vars. No secret value ever appears in logs, responses, or audit records.

### Idempotency
All mutating endpoints support `Idempotency-Key` headers. Replay with the same key returns
the original response without re-executing the operation.

### Least privilege
API credentials for ServiceTitan and QuickBooks are read-only by default. Write-back is
disabled (`write_back_enabled: false`) and requires explicit configuration.

## OpenAPI Contract

The complete API contract is in `openapi.yaml`. Changes to the contract go through PR review
and are versioned in Git.

## Environment variables

See `.env.example` for all options. Key ones:

- `DATABASE_URL` — PostgreSQL async connection string (`postgresql+asyncpg://...`)
- `REDIS_URL` — Redis connection string
- `JWT_SECRET_ARN` — Secret manager reference for JWT signing/verification
- `SECRETS_PROVIDER` — `env` (local dev) or `aws` (production)
- `ENVIRONMENT` — `local`, `staging`, or `production`
- `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR`

## Running processes

The Dockerfile supports three process types (set via `PROCESS_TYPE` env var):
- `web` — FastAPI server (uvicorn) + webhook receiver
- `worker` — Celery worker for async tasks
- `scheduler` — Celery Beat for per-tenant cron jobs

Step 1 only runs `web`; `worker` and `scheduler` are added in Step 4.

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "descriptive message"
```

Apply migrations:
```bash
alembic upgrade head
```

Downgrade one version:
```bash
alembic downgrade -1
```

## Deployment

See `.github/workflows/ci.yml` for the CI/CD pipeline. The platform is deployed as a single
Docker image supporting multiple process types via environment configuration.

## Contributing

- Write tests first. Minimum 85% coverage on `core/` and new modules.
- Use type hints with `mypy --strict`.
- Format with Black and lint with Ruff before committing.
- Every PR must include updated openapi.yaml if API changes.
- Commits follow conventional commits: `type(scope): subject`.

## Support

For questions or issues, file a GitHub issue or contact the Exotica IT Solutions dev team.
