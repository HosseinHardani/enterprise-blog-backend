import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_request_id_header_present(client: AsyncClient):
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


async def test_request_id_is_unique_per_request(client: AsyncClient):
    first = await client.get("/health")
    second = await client.get("/health")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


async def test_security_headers_present(client: AsyncClient):
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200


async def test_rate_limit_exempt_paths_never_throttled(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    for _ in range(5):
        response = await client.get("/health")
        assert response.status_code == 200


async def test_rate_limit_blocks_after_threshold(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)

    statuses = []
    for _ in range(4):
        response = await client.get("/api/v1/tags")
        statuses.append(response.status_code)

    assert statuses[:2] == [200, 200]
    assert 429 in statuses
    blocked_response = statuses[statuses.index(429)]
    assert blocked_response == 429


async def test_rate_limit_fails_open_when_redis_unavailable(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.middleware.rate_limit.get_redis_pool", lambda: _BrokenRedis())
    response = await client.get("/api/v1/tags")
    assert response.status_code == 200


class _BrokenRedis:
    async def incr(self, *args, **kwargs):
        raise ConnectionError("redis unreachable")

    async def expire(self, *args, **kwargs):
        raise ConnectionError("redis unreachable")
