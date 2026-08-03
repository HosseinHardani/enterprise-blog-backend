# Installation Guide

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (recommended path)
- PostgreSQL 16 and Redis 7, if running without Docker

## Option A: Docker Compose (recommended)

```bash
git clone <repository-url>
cd blog_api
cp .env.example .env
```

Generate a real secret key and put it in `.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Start the stack:

```bash
docker compose up --build
```

This brings up `postgres`, `redis`, `smtp4dev`, `api`, and `celery_worker`. The `api` container runs
`alembic upgrade head` automatically before starting Gunicorn, so the database schema is always current
on boot.

Verify it's running:

```bash
curl http://localhost:8000/health
```

- API docs: http://localhost:8000/docs
- Caught dev emails: http://localhost:5000 (smtp4dev web UI)

## Option B: Local Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env` so `DATABASE_URL`, `DATABASE_URL_SYNC`, and `REDIS_URL` point at your local PostgreSQL/Redis
instances, then:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Optionally, in a second terminal, start a Celery worker so background emails actually get dispatched:

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

## Verifying the installation

```bash
curl http://localhost:8000/health
# {"status": "ok", "environment": "development"}
```

Register a test user:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "username": "testuser", "password": "TestPass123"}'
```

## Running the test suite

The test suite needs no external services — it runs against an in-memory SQLite database and a fake
in-process Redis client.

```bash
pip install -r requirements-dev.txt
pytest
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if anything above doesn't work as expected.
