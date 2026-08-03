# Docker Guide

## Services

| Service | Image | Purpose | Exposed ports |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Primary database | `5432` |
| `redis` | `redis:7-alpine` | Token blacklist, rate limiting, Celery broker/backend | `6379` |
| `smtp4dev` | `rnwood/smtp4dev:v3` | Development-only SMTP catcher with a web UI | `5000` (UI), `2525` (SMTP) |
| `api` | built from `Dockerfile` | FastAPI application, served by Gunicorn + Uvicorn workers | `8000` |
| `celery_worker` | built from `Dockerfile` | Background email tasks | none (internal) |

All services share the `blog_network` bridge network and resolve each other by service name
(`postgres`, `redis`, `smtp4dev`) rather than `localhost`.

## Image build

`Dockerfile` uses a two-stage build:

1. **Builder stage** (`python:3.12-slim`): installs build tooling (`build-essential`, `libpq-dev`),
   creates a virtualenv at `/opt/venv`, and installs `requirements.txt` into it.
2. **Runtime stage** (`python:3.12-slim`): copies only the built virtualenv and application code,
   installs just the runtime shared libraries (`libpq5`, `curl`), creates a non-root `appuser`, and
   runs the app as that user. This keeps the final image free of compilers and dev headers.

The image ships a `HEALTHCHECK` hitting `GET /health`, which Docker Compose also mirrors explicitly
on the `api` service for clearer `docker compose ps` output.

## Startup sequence

`docker compose up` respects the following dependency graph via `depends_on` + healthcheck conditions:

```
postgres (healthy) ─┐
redis (healthy)     ─┼─▶ api           (runs `alembic upgrade head` before serving)
smtp4dev (started)  ─┘

postgres (healthy) ─┐
redis (healthy)     ─┼─▶ celery_worker
smtp4dev (started)  ─┘
```

`smtp4dev` has no built-in healthcheck, so it uses `condition: service_started` rather than
`service_healthy`.

## Volumes

| Volume | Mounted at | Purpose |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` (postgres) | Database persistence across restarts |
| `redis_data` | `/data` (redis) | Redis persistence (AOF/RDB, if enabled) |
| `uploads_data` | `/app/uploads` (api, celery_worker) | User-uploaded profile images, shared between both containers |

## Environment variables in Docker

The `api` and `celery_worker` services load `.env` via `env_file`, then override the
service-discovery-dependent variables (`DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `SMTP_HOST`, `SMTP_PORT`) directly in `environment:` so
they always point at the in-network service names regardless of what's in `.env` (which is meant for
running the app outside Docker). Everything else — `SECRET_KEY`, token lifetimes, CORS origins, rate
limits — comes straight from `.env`.

## Common operations

```bash
docker compose up --build              # build and start everything
docker compose up -d                    # start in the background
docker compose logs -f api              # tail API logs
docker compose exec api alembic upgrade head   # run migrations manually
docker compose exec postgres psql -U blog_user -d blog_db   # open a psql shell
docker compose down                     # stop and remove containers (keeps volumes)
docker compose down -v                  # stop and remove containers AND volumes (destructive)
```

## Production notes

- Replace the bundled `postgres`/`redis` containers with managed services (RDS/Cloud SQL,
  ElastiCache/Memorystore) rather than running stateful services in the same Compose file as the app.
- Drop `smtp4dev` entirely outside development — point `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/
  `SMTP_PASSWORD` at a real transactional email provider.
- Don't publish `5432`/`6379` to the host in production; only the `api` service needs an externally
  reachable port, and that should sit behind a reverse proxy/load balancer terminating TLS.
- Mount `uploads_data` on durable, shared storage (or migrate to S3/GCS-compatible object storage) if
  running more than one `api` replica.
