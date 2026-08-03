import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_tag_as_editor(client: AsyncClient, editor_auth_headers):
    response = await client.post("/api/v1/tags", json={"name": "django"}, headers=editor_auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "django"
    assert body["slug"] == "django"


async def test_create_tag_as_regular_user_forbidden(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/tags", json={"name": "nope"}, headers=auth_headers)
    assert response.status_code == 403


async def test_duplicate_tag_rejected(client: AsyncClient, editor_auth_headers):
    await client.post("/api/v1/tags", json={"name": "duplicate-tag"}, headers=editor_auth_headers)
    response = await client.post("/api/v1/tags", json={"name": "duplicate-tag"}, headers=editor_auth_headers)
    assert response.status_code == 409


async def test_list_tags(client: AsyncClient, editor_auth_headers):
    await client.post("/api/v1/tags", json={"name": "listed-tag"}, headers=editor_auth_headers)
    response = await client.get("/api/v1/tags")
    assert response.status_code == 200
    names = [t["name"] for t in response.json()["items"]]
    assert "listed-tag" in names


async def test_delete_tag(client: AsyncClient, editor_auth_headers):
    create_resp = await client.post("/api/v1/tags", json={"name": "temp-tag"}, headers=editor_auth_headers)
    tag_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/tags/{tag_id}", headers=editor_auth_headers)
    assert response.status_code == 200


async def test_delete_nonexistent_tag(client: AsyncClient, editor_auth_headers):
    import uuid

    response = await client.delete(f"/api/v1/tags/{uuid.uuid4()}", headers=editor_auth_headers)
    assert response.status_code == 404
