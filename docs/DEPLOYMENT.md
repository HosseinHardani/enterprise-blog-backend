# Deployment Guide

This guide covers taking the project from `docker compose up` on a laptop to a real production
deployment. It's a checklist of what to change, not a fully automated pipeline.

## 1. Secrets

- Generate a unique `SECRET_KEY` per environment: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`.
- Never reuse the `.env.example` defaults for `POSTGRES_PASSWORD` or `SECRET_KEY`.
- Inject secrets via your platform's secret manager (AWS Secrets Manager, GCP Secret Manager, Vault,
  Kubernetes Secrets) rather than baking them into the image or committing a real `.env`.

## 2. Database

- Use a managed PostgreSQL instance (RDS, Cloud SQL, Azure Database for PostgreSQL) instead of the
  `postgres` container from `docker-compose.yml`.
- Set `ENVIRONMENT=production` so the app enables the `Strict-Transport-Security` header and refresh
  cookies are marked `Secure`.
- Run `alembic upgrade head` as a release step (a one-off job/task) rather than baking it into the
  API container's normal startup command, so schema migrations are decoupled from horizontal scaling
  of the API itself.
- Enable automated backups and point-in-time recovery on the managed database.

## 3. Redis

- Use a managed Redis instance (ElastiCache, Memorystore) with the same logical-DB separation used
  locally: DB 0 for the app cache/blacklist/rate-limit, DB 1/2 for Celery broker/backend.
- Enable TLS (`rediss://`) if your provider supports it, and update `REDIS_URL`/`CELERY_BROKER_URL`/
  `CELERY_RESULT_BACKEND` accordingly.

## 4. Application server

- The image already runs Gunicorn with `UvicornWorker`s (`--workers 4` by default in
  `docker-compose.yml`'s override command). Tune worker count to `(2 × CPU cores) + 1` for your
  actual instance size.
- Put a reverse proxy / load balancer (ALB, nginx, Traefik) in front of the API container(s) to
  terminate TLS — the app itself does not handle HTTPS.
- Run multiple `api` replicas behind the load balancer for availability; the app is stateless aside
  from the shared Postgres/Redis/object-storage backends, so horizontal scaling requires no code
  changes.

## 5. Celery workers

- Run `celery_worker` as its own deployable unit (separate service/pod), scaled independently from
  the API based on email/background-task volume.
- Consider adding `celery beat` if periodic tasks are introduced later (none exist today).

## 6. File storage

- Swap local-disk `UPLOAD_DIR` for S3/GCS-compatible object storage before running more than one API
  replica, since local disk isn't shared across instances. This requires implementing a storage
  backend swap in `app/routers/v1/users.py`'s upload handler — out of scope for the current codebase,
  called out as a known limitation in the README.

## 7. Email

- Remove `smtp4dev` entirely — it's development-only.
- Point `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_TLS` at a real provider (SES, SendGrid,
  Postmark, etc.).
- Ensure the Celery worker (which actually sends the emails) has network access to that provider.

## 8. Observability

- The app emits structured JSON logs to stdout (`app/core/logging.py`) — ship them to your log
  aggregator (CloudWatch Logs, Stackdriver, ELK, Datadog) via the container runtime's log driver.
- Each response carries an `X-Request-ID` header (`app/middleware/logging_middleware.py`) for
  correlating a client-reported issue with server logs.
- `GET /health` is suitable for load-balancer and orchestrator liveness checks.
- Add APM/tracing (OpenTelemetry, Datadog APM) as a follow-up — not currently wired in.

## 9. CI/CD

- `.github/workflows/ci.yml` already runs lint → migration-drift check → tests (with coverage) →
  Docker build on every push/PR. Extend the `docker-build` job with a push step (`docker/login-action`
  + `push: true`) and a deploy step for your target platform once you have one.

## 10. Rollout checklist

- [ ] Real `SECRET_KEY` set and stored in a secret manager
- [ ] `ENVIRONMENT=production`
- [ ] Managed Postgres + Redis provisioned, connection strings set
- [ ] `alembic upgrade head` run against the target database
- [ ] Real SMTP provider configured, `smtp4dev` removed
- [ ] TLS terminated in front of the API
- [ ] `CORS_ORIGINS` restricted to real frontend origin(s)
- [ ] Log shipping configured
- [ ] Health checks wired into the load balancer / orchestrator
