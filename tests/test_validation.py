import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# --- Registration validation -----------------------------------------------------


@pytest.mark.parametrize(
    "password",
    [
        "short1A",  # too short (< 8 chars)
        "nouppercase1",  # missing uppercase
        "NOLOWERCASE1",  # missing lowercase
        "NoDigitsHere",  # missing digit
    ],
)
async def test_weak_passwords_rejected(client: AsyncClient, password: str):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weakpass@example.com", "username": "weakpassuser", "password": password},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_invalid_email_format_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "username": "validusername", "password": "StrongPass1"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("username", ["ab", "has spaces", "has-dash", "has.dot", "emoji😀"])
async def test_invalid_usernames_rejected(client: AsyncClient, username: str):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "userfmt@example.com", "username": username, "password": "StrongPass1"},
    )
    assert response.status_code == 422


async def test_missing_required_fields_rejected(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={"email": "incomplete@example.com"})
    assert response.status_code == 422
    body = response.json()
    assert body["details"] is not None
    assert len(body["details"]) > 0


# --- Post validation -----------------------------------------------------


async def test_post_title_too_short_rejected(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/posts", json={"title": "ab", "content": "Valid content"}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_post_missing_content_rejected(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/posts", json={"title": "Valid Title Here"}, headers=auth_headers)
    assert response.status_code == 422


async def test_post_invalid_status_value_rejected(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/posts",
        json={"title": "Valid Title", "content": "Body", "status": "not-a-real-status"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_post_invalid_uuid_path_param_rejected(client: AsyncClient, auth_headers):
    response = await client.patch(
        "/api/v1/posts/not-a-uuid", json={"title": "Whatever Title"}, headers=auth_headers
    )
    assert response.status_code == 422


# --- Comment validation -----------------------------------------------------


async def test_empty_comment_content_rejected(client: AsyncClient, auth_headers):
    post_resp = await client.post(
        "/api/v1/posts",
        json={"title": "Comment Target", "content": "Body", "status": "published"},
        headers=auth_headers,
    )
    post_id = post_resp.json()["id"]
    response = await client.post(
        f"/api/v1/posts/{post_id}/comments", json={"content": ""}, headers=auth_headers
    )
    assert response.status_code == 422


# --- Category validation -----------------------------------------------------


async def test_category_name_too_short_rejected(client: AsyncClient, editor_auth_headers):
    response = await client.post("/api/v1/categories", json={"name": "a"}, headers=editor_auth_headers)
    assert response.status_code == 422


# --- Pagination validation -----------------------------------------------------


async def test_pagination_page_below_one_rejected(client: AsyncClient):
    response = await client.get("/api/v1/posts", params={"page": 0})
    assert response.status_code == 422


async def test_pagination_page_size_exceeds_max_rejected(client: AsyncClient):
    response = await client.get("/api/v1/posts", params={"page_size": 1000})
    assert response.status_code == 422


async def test_invalid_sort_by_value_rejected(client: AsyncClient):
    response = await client.get("/api/v1/posts", params={"sort_by": "not_a_real_column"})
    assert response.status_code == 422


async def test_invalid_sort_order_value_rejected(client: AsyncClient):
    response = await client.get("/api/v1/posts", params={"sort_order": "sideways"})
    assert response.status_code == 422
