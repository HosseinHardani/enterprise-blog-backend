# Project Structure

```
blog_api/
├── .env.example                    Local dev environment template
├── .env.test                       Test-run environment overrides (loaded by pytest-dotenv)
├── .github/workflows/ci.yml        CI: lint, migration-drift check, tests, Docker build
├── .gitignore
├── .pre-commit-config.yaml         Git hooks: trailing-whitespace, black, isort, ruff, mypy
├── Dockerfile                      Multi-stage build (builder + slim runtime, non-root user)
├── docker-compose.yml              postgres, redis, smtp4dev, api, celery_worker
├── README.md                       Project overview and quick start
├── pyproject.toml                  Black/isort/ruff/mypy/pytest configuration
├── requirements.txt                Runtime dependencies
├── requirements-dev.txt            Runtime + test/lint/type-check dependencies
├── alembic.ini                     Alembic configuration
├── alembic/
│   ├── env.py                      Migration environment (runs against DATABASE_URL_SYNC)
│   ├── script.py.mako              Template for new migration files
│   ├── EXAMPLES.md                 Reference patterns for future migrations
│   └── versions/0001_initial.py    Initial schema — matches every ORM model exactly
├── docs/
│   ├── INSTALLATION.md             Local + Docker setup walkthrough
│   ├── DOCKER.md                   Service topology, volumes, networking, production notes
│   ├── API_GUIDE.md                Endpoint reference with example requests
│   ├── ENVIRONMENT.md              Every environment variable, explained
│   ├── DEPLOYMENT.md               Production rollout checklist
│   └── TROUBLESHOOTING.md          Common setup/runtime issues and fixes
├── app/
│   ├── main.py                     FastAPI app assembly: middleware, routers, exception handlers
│   ├── core/
│   │   ├── config.py                pydantic-settings Settings, loaded from .env
│   │   ├── security.py              Password hashing, JWT creation/decoding
│   │   └── logging.py               JSON structured logging configuration
│   ├── database/
│   │   ├── session.py               Async engine, session factory, get_db dependency
│   │   └── base.py                  Declarative base + UUID PK / timestamp / soft-delete mixins
│   ├── models/                      SQLAlchemy 2.0 ORM models (one file per aggregate)
│   │   ├── user.py                  User, UserRole enum
│   │   ├── post.py                  Post, PostStatus enum, post_tags association table
│   │   ├── comment.py                Comment (self-referential replies)
│   │   ├── category.py               Category
│   │   ├── tag.py                    Tag
│   │   ├── bookmark.py               Bookmark
│   │   ├── like.py                   PostLike
│   │   └── refresh_token.py         RefreshToken
│   ├── schemas/                     Pydantic v2 request/response models, mirroring models/
│   ├── repositories/                Data-access layer — one class per aggregate, only layer with SQL
│   │   └── base.py                  Generic BaseRepository[ModelType] with common CRUD
│   ├── services/                    Business logic layer — authorization, orchestration
│   │   └── email_service.py         SMTP sending + email template builders
│   ├── routers/v1/                  HTTP layer, versioned under /api/v1
│   │   └── api.py                   Aggregates all v1 routers into one APIRouter
│   ├── dependencies/
│   │   ├── auth.py                  get_current_user, require_roles(...), token blacklist check
│   │   ├── pagination.py            pagination_params query-param dependency
│   │   └── redis_client.py          Shared async Redis client
│   ├── middleware/
│   │   ├── logging_middleware.py    Request-ID assignment + structured access logging
│   │   └── rate_limit.py            Redis-backed fixed-window rate limiter (fails open)
│   ├── exceptions/
│   │   ├── custom.py                 Typed AppException hierarchy
│   │   └── handlers.py               Global exception handlers -> consistent JSON error shape
│   ├── utils/
│   │   ├── slug.py                   Slug generation (plain + uniqueness-suffixed)
│   │   └── pagination.py            PageParams dataclass (offset/limit from page/page_size)
│   └── tasks/
│       ├── celery_app.py            Celery application + configuration
│       └── email_tasks.py           Background verification/reset/notification email tasks
└── tests/
    ├── conftest.py                 SQLite test DB, fake Redis, async client, user fixtures
    ├── test_auth.py                Registration, login, logout, refresh rotation, verify, reset
    ├── test_users.py               Profile, email/password change, soft delete, role management
    ├── test_posts.py               CRUD, search, filter, sort, pagination, view count, likes
    ├── test_comments.py            CRUD, threaded replies, permissions
    ├── test_categories.py          CRUD, permissions
    ├── test_tags.py                CRUD, permissions
    ├── test_bookmarks.py           Add/remove/list, duplicate/not-found handling
    ├── test_permissions.py         Cross-cutting RBAC matrix, auth-required coverage
    ├── test_validation.py          Pydantic/request validation edge cases
    ├── test_middleware.py          Request-ID, security headers, rate limiting
    ├── test_utils.py               Slug generation, pagination helper unit tests
    └── test_integration.py         Full cross-resource lifecycle and pagination-consistency flows
```

## Layer responsibilities

| Layer | Depends on | Never does |
|---|---|---|
| Router | Service, Schema | Write SQL, contain business rules |
| Service | Repository, other Services | Import FastAPI types, know about HTTP |
| Repository | Model, `AsyncSession` | Contain business rules or authorization checks |
| Model | SQLAlchemy only | Import schemas, services, or routers |
| Schema | Model (for `from_attributes`), other Schemas | Contain business logic |

Data flows one direction: `Router → Service → Repository → Model`. A file in a lower layer never
imports from a higher one.
