# Environment Variables

All settings are defined in `app/core/config.py` (`pydantic-settings`, loaded from `.env`). Unknown
extra variables in `.env` are ignored (`extra="ignore"`), which is why `POSTGRES_USER`/
`POSTGRES_PASSWORD`/`POSTGRES_DB` can live in the same file even though only `docker-compose.yml`
consumes them directly (Postgres's own container reads them, not the FastAPI app).

## App

| Variable | Default | Notes |
|---|---|---|
| `PROJECT_NAME` | `Blog REST API` | Shown in OpenAPI docs |
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production` — controls HSTS header and cookie `Secure` flag |
| `DEBUG` | `true` | Also controls log verbosity |
| `API_V1_PREFIX` | `/api/v1` | |

## Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Used by the running app (async) |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://...` | Used only by Alembic |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Extra connections allowed beyond pool size |
| `DB_ECHO` | `false` | Log every SQL statement (noisy — dev only) |

## Security / JWT

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | placeholder | **Must** be overridden with a strong random value outside local dev |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | |
| `REFRESH_TOKEN_COOKIE_NAME` | `refresh_token` | |

## CORS

| Variable | Default | Notes |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Comma-separated list |

## Redis / Rate limiting

| Variable | Default | Notes |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Token blacklist + rate limiting + general cache |
| `REDIS_CACHE_TTL_SECONDS` | `300` | |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-client-IP requests/minute before a `429` |

## Celery

| Variable | Default | Notes |
|---|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Separate logical DB from the main Redis cache |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | |

## SMTP / Email

| Variable | Default | Notes |
|---|---|---|
| `SMTP_HOST` | `localhost` | `smtp4dev` inside Docker Compose |
| `SMTP_PORT` | `2525` locally / `25` in Docker | |
| `SMTP_USER` / `SMTP_PASSWORD` | empty | Leave blank for smtp4dev (no auth) |
| `SMTP_FROM_EMAIL` | `no-reply@blogapi.local` | |
| `SMTP_TLS` | `false` | |
| `FRONTEND_URL` | `http://localhost:3000` | Used to build verification/reset links |

## Pagination

| Variable | Default | Notes |
|---|---|---|
| `DEFAULT_PAGE_SIZE` | `20` | |
| `MAX_PAGE_SIZE` | `100` | |

## File uploads

| Variable | Default | Notes |
|---|---|---|
| `UPLOAD_DIR` | `uploads/profile_images` | Relative to the app's working directory; mounted as a named volume in Docker |
| `MAX_UPLOAD_SIZE_MB` | `5` | |

## Files

- `.env.example` — template for local development (copy to `.env`)
- `.env.test` — loaded automatically by `pytest-dotenv` during test runs; the test suite overrides
  the DB/Redis dependencies directly in `tests/conftest.py`, so these values only need to be valid
  enough for `Settings()` to construct without error
