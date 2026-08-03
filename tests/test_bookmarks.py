import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_post(client: AsyncClient, headers: dict, title: str = "Bookmarkable Post") -> dict:
    response = await client.post(
        "/api/v1/posts", json={"title": title, "content": "Body", "status": "published"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_add_bookmark(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.post(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)
    assert response.status_code == 201, response.text
    assert response.json()["post"]["id"] == post["id"]


async def test_add_bookmark_requires_auth(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.post(f"/api/v1/bookmarks/{post['id']}")
    assert response.status_code == 401


async def test_duplicate_bookmark_rejected(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    await client.post(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)
    response = await client.post(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)
    assert response.status_code == 409


async def test_bookmark_nonexistent_post(client: AsyncClient, auth_headers):
    import uuid

    response = await client.post(f"/api/v1/bookmarks/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


async def test_list_bookmarks(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    await client.post(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)

    response = await client.get("/api/v1/bookmarks", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["post"]["id"] == post["id"]


async def test_remove_bookmark(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    await client.post(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)

    response = await client.delete(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)
    assert response.status_code == 200

    list_resp = await client.get("/api/v1/bookmarks", headers=auth_headers)
    assert list_resp.json()["total"] == 0


async def test_remove_nonexistent_bookmark(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.delete(f"/api/v1/bookmarks/{post['id']}", headers=auth_headers)
    assert response.status_code == 404
