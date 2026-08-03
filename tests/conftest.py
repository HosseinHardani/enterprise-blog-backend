"""
Shared Pytest fixtures.

The test suite runs against an in-memory SQLite database (via aiosqlite) and
an in-process fake Redis client, so it needs no external services. Every
test function gets a fresh database and a fresh fake Redis instance for
full isolation.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.database.base import Base
from app.database.session import get_db
from app.dependencies.redis_client import get_redis
from app.main import app
from app.models.user import User, UserRole

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis, covering only the
    commands actually used by the application (get/set/incr/expire)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self._store[key] = value
        return True

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, 0)) + 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def close(self) -> None:
        self._store.clear()

    async def aclose(self) -> None:
        await self.close()


@pytest_asyncio.fixture
async def fake_redis(monkeypatch) -> AsyncGenerator[FakeRedis, None]:
    redis = FakeRedis()
    # Patch the module-level accessor used by the rate-limit middleware,
    # which imports the function directly rather than going through DI.
    monkeypatch.setattr("app.middleware.rate_limit.get_redis_pool", lambda: redis)
    monkeypatch.setattr("app.dependencies.redis_client.get_redis_pool", lambda: redis)
    yield redis


@pytest_asyncio.fixture
async def db_session(fake_redis) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with session_factory() as session:
        yield session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# --- Common test data -----------------------------------------------------

TEST_PASSWORD = "TestPass123"


async def _create_user(
    db_session: AsyncSession,
    email: str,
    username: str,
    role: UserRole = UserRole.USER,
    password: str = TEST_PASSWORD,
    is_email_verified: bool = True,
) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        is_email_verified=is_email_verified,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str = TEST_PASSWORD) -> str:
    response = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    return await _create_user(db_session, "user@example.com", "regular_user")


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    return await _create_user(db_session, "other@example.com", "other_user")


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession) -> User:
    return await _create_user(db_session, "editor@example.com", "editor_user", role=UserRole.EDITOR)


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _create_user(db_session, "admin@example.com", "admin_user", role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, regular_user: User) -> dict:
    token = await _login(client, regular_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_auth_headers(client: AsyncClient, other_user: User) -> dict:
    token = await _login(client, other_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def editor_auth_headers(client: AsyncClient, editor_user: User) -> dict:
    token = await _login(client, editor_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(client: AsyncClient, admin_user: User) -> dict:
    token = await _login(client, admin_user.email)
    return {"Authorization": f"Bearer {token}"}
