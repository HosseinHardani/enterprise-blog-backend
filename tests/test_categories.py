import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_category_as_editor(client: AsyncClient, editor_auth_headers):
    response = await client.post(
        "/api/v1/categories",
        json={"name": "Science", "description": "Science posts"},
        headers=editor_auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Science"
    assert body["slug"] == "science"


async def test_create_category_as_regular_user_forbidden(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/categories", json={"name": "Nope"}, headers=auth_headers)
    assert response.status_code == 403


async def test_create_category_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/categories", json={"name": "NoAuth"})
    assert response.status_code == 401


async def test_duplicate_category_name_rejected(client: AsyncClient, editor_auth_headers):
    await client.post("/api/v1/categories", json={"name": "Duplicate"}, headers=editor_auth_headers)
    response = await client.post(
        "/api/v1/categories", json={"name": "Duplicate"}, headers=editor_auth_headers
    )
    assert response.status_code == 409


async def test_list_categories(client: AsyncClient, editor_auth_headers):
    await client.post("/api/v1/categories", json={"name": "Listed Category"}, headers=editor_auth_headers)
    response = await client.get("/api/v1/categories")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()["items"]]
    assert "Listed Category" in names


async def test_get_category_by_id(client: AsyncClient, editor_auth_headers):
    create_resp = await client.post(
        "/api/v1/categories", json={"name": "Fetchable"}, headers=editor_auth_headers
    )
    category_id = create_resp.json()["id"]
    response = await client.get(f"/api/v1/categories/{category_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Fetchable"


async def test_get_category_not_found(client: AsyncClient):
    import uuid

    response = await client.get(f"/api/v1/categories/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_update_category(client: AsyncClient, editor_auth_headers):
    create_resp = await client.post(
        "/api/v1/categories", json={"name": "Old Name"}, headers=editor_auth_headers
    )
    category_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/categories/{category_id}", json={"name": "New Name"}, headers=editor_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["slug"] == "new-name"


async def test_delete_category(client: AsyncClient, editor_auth_headers):
    create_resp = await client.post(
        "/api/v1/categories", json={"name": "To Delete"}, headers=editor_auth_headers
    )
    category_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/categories/{category_id}", headers=editor_auth_headers)
    assert response.status_code == 200

    follow_up = await client.get(f"/api/v1/categories/{category_id}")
    assert follow_up.status_code == 404
