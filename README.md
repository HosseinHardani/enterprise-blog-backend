# Blog REST API

A production-ready Blog REST API built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0** (async), **Redis**,
and **Celery**. Implements JWT authentication with refresh-token rotation, role-based access control, and a
full blogging feature set (posts, comments, categories, tags, likes, bookmarks) behind a clean, layered
architecture.

## Table of contents

- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
  - [Run with Docker (recommended)](#run-with-docker-recommended)
  - [Run locally without Docker](#run-locally-without-docker)
- [Configuration](#configuration)
- [Database migrations](#database-migrations)
- [Background tasks (Celery)](#background-tasks-celery)
- [Testing](#testing)
- [Code quality](#code-quality)
- [API overview](#api-overview)
- [Authentication model](#authentication-model)
- [Project layout](#project-layout)
- [Known limitations](#known-limitations)

## Further documentation

This README is the overview. Deeper guides live in [`docs/`](docs/):

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — step-by-step local and Docker setup
- [`docs/DOCKER.md`](docs/DOCKER.md) — service topology, volumes, networking, production notes
- [`docs/API_GUIDE.md`](docs/API_GUIDE.md) — endpoint reference with example requests
- [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) — every environment variable, explained
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — production rollout checklist
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — common setup/runtime issues

## Architecture

The codebase follows a layered, SOLID-friendly architecture so business logic never depends on
FastAPI or SQLAlchemy specifics directly:

```
Router (HTTP)  →  Service (business logic)  →  Repository (data access)  →  ORM Model
                        ↓
                    Pydantic Schema (validation / serialization)
```

- **Routers** (`app/routers/`) only parse HTTP input, call a service, and shape the HTTP response. No
  business logic lives here.
- **Services** (`app/services/`) own business rules, authorization checks, and orchestration across
  repositories. They raise typed `AppException` subclasses (`app/exceptions/custom.py`) instead of
  HTTP-specific errors.
- **Repositories** (`app/repositories/`) are the only layer that writes SQLAlchemy queries. Each wraps
  one aggregate/model and exposes intention-revealing methods (`get_by_slug`, `list_filtered`, ...).
- **Models** (`app/models/`) are SQLAlchemy 2.0 declarative models using `Mapped[...]` typing throughout.
- **Schemas** (`app/schemas/`) are Pydantic v2 models for request validation and response serialization,
  kept separate from ORM models so the API contract can evolve independently of the database schema.

Cross-cutting concerns (auth, pagination, Redis) are FastAPI dependencies in `app/dependencies/`.
Global error formatting lives in `app/exceptions/handlers.py` so every error response — validation,
business, or unhandled — has the same JSON shape:

```json
{ "error": "not_found", "message": "Post not found", "details": null }
```

## Tech stack

| Concern              | Choice                                          |
|-----------------------|--------------------------------------------------|
| Web framework          | FastAPI                                          |
| Database                | PostgreSQL 16                                    |
| ORM                       | SQLAlchemy 2.0 (async, `asyncpg`)                |
| Migrations              | Alembic (runs against the sync `psycopg2` URL)    |
| Validation                | Pydantic v2                                     |
| Auth                        | JWT (access + refresh), bcrypt password hashing |
| Cache / rate limit / blacklist | Redis                                      |
| Background jobs      | Celery (Redis broker + result backend)           |
| Containerization      | Docker, Docker Compose                          |
| Testing                   | Pytest, pytest-asyncio, SQLite (in-memory) for CI |
| CI                            | GitHub Actions (lint → test → Docker build)    |

## Getting started

### Run with Docker (recommended)

```bash
cp .env.example .env
# Edit .env and set a real SECRET_KEY:
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up --build
```

This starts five containers: `postgres`, `redis`, `smtp4dev` (catches outbound dev emails), `api`
(runs `alembic upgrade head` automatically on boot, then serves via Gunicorn+Uvicorn workers), and
`celery_worker`. The API is available at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`. Verification and password-reset emails sent during local development
land in the smtp4dev web UI at `http://localhost:5000` instead of a real inbox.

### Run locally without Docker

Requires a local PostgreSQL and Redis instance.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # then edit DATABASE_URL / REDIS_URL / SECRET_KEY as needed

alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, start a Celery worker if you want background email delivery to actually run
(otherwise `app/services/auth_service.py` falls back to sending emails synchronously):

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

## Configuration

All configuration is environment-driven (`app/core/config.py`, backed by `pydantic-settings`). Copy
`.env.example` to `.env` and adjust as needed. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async connection string used by the running app (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Sync connection string used only by Alembic (`postgresql+psycopg2://...`) |
| `SECRET_KEY` | JWT signing secret — **must** be overridden in any non-local environment |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `REDIS_URL` | Used for the access-token blacklist, rate limiting, and caching |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Separate logical Redis DBs for Celery |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per client IP before a `429` is returned |
| `SMTP_*` | Outbound email settings for verification/reset emails |

Never commit a real `.env` file — it's excluded via `.gitignore`.

## Database migrations

Alembic is configured in `alembic/env.py` to run against `DATABASE_URL_SYNC` (synchronous psycopg2),
even though the app itself uses the async engine at runtime — this keeps migration execution simple
and avoids async/greenlet complications during DDL.

```bash
alembic upgrade head                              # apply all migrations
alembic downgrade -1                               # roll back one migration
alembic revision --autogenerate -m "add X"         # generate a new migration from model changes
alembic history --verbose
```

The initial migration (`alembic/versions/0001_initial.py`) creates the full schema by hand, matching
every ORM model exactly (tables, enums, indexes, foreign keys, and unique constraints). See
`alembic/EXAMPLES.md` for reference patterns (adding a column, renaming a column without downtime,
grouping a safe schema change) to copy into future migrations.

## Background tasks (Celery)

Verification emails and password-reset emails are dispatched as Celery tasks
(`app/tasks/email_tasks.py`) so the request/response cycle never blocks on SMTP I/O. If no Celery
worker/broker is reachable (e.g. local dev without Redis running), `AuthService` catches the dispatch
failure and falls back to sending the email synchronously, so the auth flow still works either way.

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

## Testing

The test suite (`tests/`) runs against an **in-memory SQLite database** and an **in-process fake Redis
client** (see `tests/conftest.py`), so it needs no external services and runs the same way locally and
in CI.

```bash
pip install -r requirements-dev.txt
pytest                      # runs with coverage (see pyproject.toml for thresholds)
pytest tests/test_posts.py  # run a single file
pytest -k "test_login"      # run tests matching a keyword
```

Coverage is configured to fail the run below 90% (`--cov-fail-under=90` in `pyproject.toml`).
The suite (113 test functions across 11 files) covers: registration/login/logout/refresh/verify/reset
flows, profile management, full CRUD + search/filter/sort/pagination for posts, threaded comments,
categories, tags, bookmarks, a role-based-access-control matrix (user/editor/admin), Pydantic
validation edge cases, middleware behavior (request-id, security headers, rate limiting, fail-open on
Redis outage), slug/pagination utility functions, and cross-resource integration flows spanning
posts/comments/likes/bookmarks/roles end to end.

## Code quality

```bash
ruff check .                                   # lint
black --check --line-length 110 .              # format check
isort --check-only --profile black --line-length 110 .   # import order
mypy app                                       # type check

pre-commit install                             # install git hooks (see .pre-commit-config.yaml)
```

CI (`.github/workflows/ci.yml`) runs lint → Alembic migration-drift check (`alembic upgrade head` +
`alembic check` against a real Postgres service container) → tests → Docker build on every push/PR to
`main`/`develop`.

## API overview

Interactive documentation (Swagger UI) is served at `/docs`, ReDoc at `/redoc`, and the raw OpenAPI
schema at `/openapi.json`. All endpoints are versioned under `/api/v1`.

| Resource | Base path | Notes |
|---|---|---|
| Auth | `/api/v1/auth` | register, login, logout, refresh, verify-email, password reset |
| Users | `/api/v1/users` | public profile, self-service profile/email/password, admin role management |
| Posts | `/api/v1/posts` | CRUD, search, filter (status/category/tag/author), sort, pagination, like |
| Comments | `/api/v1/posts/{post_id}/comments`, `/api/v1/comments/{id}` | threaded replies |
| Categories | `/api/v1/categories` | CRUD (editor/admin only for writes) |
| Tags | `/api/v1/tags` | CRUD (editor/admin only for writes) |
| Bookmarks | `/api/v1/bookmarks` | add/remove/list for the current user |

`GET /health` returns a liveness check (excluded from rate limiting).

## Authentication model

- **Access tokens** are short-lived JWTs (15 min by default), sent as a Bearer token and validated on
  every request. Each carries a `jti`; on logout, that `jti` is written to a Redis blacklist for the
  remainder of its natural lifetime.
- **Refresh tokens** are long-lived JWTs (30 days by default), delivered only via an `HttpOnly`,
  `Secure` (in production), `SameSite=Lax` cookie scoped to `/api/v1/auth`. Their `jti` is persisted in
  the `refresh_tokens` table.
- **Rotation**: every call to `/api/v1/auth/refresh` revokes the presented refresh token and issues a
  new one. Reuse of an already-revoked refresh token revokes the entire token family for that user, as
  a defense against token theft.
- **Roles**: `admin`, `editor`, `user` (see `app/models/user.py::UserRole`). Role checks are enforced via
  the `require_roles(...)` dependency factory in `app/dependencies/auth.py`.

## Project layout

```
app/
├── main.py                 # FastAPI app assembly: middleware, routers, exception handlers
├── core/                   # settings, JWT/password utilities, logging config
├── database/                # async engine/session, declarative base + mixins
├── models/                    # SQLAlchemy 2.0 ORM models
├── schemas/                   # Pydantic request/response models
├── repositories/           # data-access layer (one per aggregate)
├── services/                  # business logic layer
├── routers/v1/                # HTTP layer, versioned under /api/v1
├── dependencies/            # auth guards, pagination, Redis client
├── middleware/               # request logging, rate limiting
├── exceptions/                # typed exceptions + global handlers
├── utils/                      # slug generation, pagination helpers
└── tasks/                       # Celery app + email tasks
alembic/                    # migrations
tests/                          # Pytest suite
docs/                            # installation, Docker, API, environment, deployment, troubleshooting guides
.github/workflows/ci.yml     # CI pipeline
```

## Known limitations

These are intentional trade-offs or scoped-out edge cases, not oversights — worth knowing before
relying on this in production as-is:

- **Deeply nested comment threads**: the comment repository eager-loads one level of replies (a
  top-level comment's direct replies). A reply-to-a-reply (2+ levels deep) is stored correctly by the
  data model but is not eager-loaded by `CommentRepository`, so serializing a 2+-level-deep thread
  would need a follow-up query or a bounded-depth eager-load chain.
- **Authors (and anonymous callers) can't list drafts via the general feed at all**, including their
  own — `GET /api/v1/posts` forces `status=published` for anyone who isn't an editor or admin,
  regardless of which `status` value they request or which `author_id` they filter by. This is
  intentionally strict: a fixed audit item in this project found that the previous implementation
  only applied this restriction when no `status` was explicitly requested, letting a `user`-role or
  anonymous caller see everyone's drafts by passing `?status=draft` directly. Authors can still reach
  their own draft directly via its slug (`GET /api/v1/posts/{slug}`), just not through the general
  listing endpoint.
- **File uploads are stored on local disk** (`UPLOAD_DIR`), not object storage — fine for the Docker
  Compose setup (backed by a named volume) but worth swapping for S3/GCS-compatible storage before a
  multi-instance production deployment.
- **Rate limiting fails open**: if Redis is unreachable, `RateLimitMiddleware` lets requests through
  rather than blocking the API — a deliberate availability-over-strictness trade-off.
