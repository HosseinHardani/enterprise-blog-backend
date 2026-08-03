# Troubleshooting Guide

## `docker compose up` fails at the `api` service with a database connection error

The `api` service's healthcheck-based `depends_on` should prevent this, but if you see connection
refused errors, confirm Postgres actually finished initializing:

```bash
docker compose logs postgres
docker compose ps
```

`postgres` must show as `healthy` before `api` will start. If it's stuck `starting`, check that no
other process on your host is already bound to port `5432`.

## `alembic upgrade head` fails with "relation already exists"

This usually means the database already has tables from a previous run that Alembic doesn't know
about (e.g. you previously created tables manually or via a different migration history). Either:

```bash
docker compose down -v   # destroys the postgres_data volume — only for local/dev databases
docker compose up --build
```

or manually align the `alembic_version` table with `alembic stamp head` if the schema is already
correct and you just need Alembic to recognize it.

## Login succeeds but every subsequent request returns 401

Check that:

1. You're sending the access token as `Authorization: Bearer <token>`, not as a cookie — only the
   refresh token uses a cookie.
2. The access token hasn't expired (`ACCESS_TOKEN_EXPIRE_MINUTES`, 15 minutes by default). Use
   `POST /auth/refresh` to get a new one.
3. You haven't already called `/auth/logout` with that token — logout blacklists it immediately in
   Redis for the remainder of its lifetime.

## `POST /auth/refresh` returns 401 even though I just logged in

The refresh cookie is scoped to path `/api/v1/auth` (`REFRESH_TOKEN_COOKIE_NAME` in
`app/routers/v1/auth.py::_set_refresh_cookie`). If you're testing with a raw HTTP client or a custom
frontend, make sure it's actually storing and resending cookies scoped to that path. Also remember
refresh tokens are single-use: calling `/auth/refresh` twice with the same (already-rotated) token
returns 401 by design (reuse detection).

## Verification/reset emails never arrive

- If running via Docker Compose, open the smtp4dev web UI at `http://localhost:5000` — it catches
  every outbound email instead of delivering it, by design, for local development.
- If running outside Docker, confirm a Celery worker is actually running
  (`celery -A app.tasks.celery_app worker --loglevel=info`). If no worker is reachable, `AuthService`
  falls back to sending synchronously — check the API process's own logs for SMTP connection errors
  in that case.
- Confirm `SMTP_HOST`/`SMTP_PORT` actually point at a reachable SMTP endpoint for your environment
  (see [ENVIRONMENT.md](ENVIRONMENT.md)).

## `429 Too Many Requests` during local testing

`RATE_LIMIT_PER_MINUTE` (default 60) is enforced per client IP by `app/middleware/rate_limit.py`. If
you're load-testing or scripting many requests locally, raise it in `.env` or wait 60 seconds for the
fixed window to reset.

## Tests fail with a database/Redis connection error

The test suite is designed to need no external services — `tests/conftest.py` overrides `get_db` with
an in-memory SQLite engine and `get_redis`/`get_redis_pool` with an in-process fake. If you're seeing
real connection errors during `pytest`, confirm you're running it from the project root (so
`tests/conftest.py` and `.env.test` are discovered) and that `pytest-dotenv` is installed
(`pip install -r requirements-dev.txt`).

## `mypy` reports errors under `alembic/` or `tests/`

Both are excluded in `pyproject.toml`'s `[tool.mypy]` section (`exclude = ["alembic/", "tests/"]`).
If you're still seeing errors there, confirm you're invoking `mypy app` (as CI does) rather than
`mypy .`.

## Docker build is slow / image is large

The `Dockerfile` uses a multi-stage build specifically to keep the runtime image slim — confirm
you're not accidentally building an intermediate stage in isolation
(`docker build --target builder` would include compilers). A plain `docker build .` or
`docker compose build` always produces the final `runtime` stage.

## `curl: (7) Failed to connect` when checking `/health` from the host

If you changed the `api` service's published port in `docker-compose.yml`, update your local `curl`
command to match. The default published port is `8000:8000`.
