import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_category(client: AsyncClient, headers: dict, name: str = "Tech") -> str:
    response = await client.post("/api/v1/categories", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_tag(client: AsyncClient, headers: dict, name: str = "python") -> str:
    response = await client.post("/api/v1/tags", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_post(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "title": "My First Post",
        "content": "Some interesting content about FastAPI.",
        "status": "published",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/posts", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_post(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers, title="Hello World")
    assert post["title"] == "Hello World"
    assert post["slug"] == "hello-world"
    assert post["status"] == "published"
    assert post["view_count"] == 0


async def test_create_post_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/posts", json={"title": "No Auth", "content": "x"})
    assert response.status_code == 401


async def test_duplicate_title_gets_unique_slug(client: AsyncClient, auth_headers):
    first = await _create_post(client, auth_headers, title="Same Title")
    second = await _create_post(client, auth_headers, title="Same Title")
    assert first["slug"] != second["slug"]
    assert second["slug"].startswith("same-title-")


async def test_get_post_by_slug_increments_view_count(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response1 = await client.get(f"/api/v1/posts/{post['slug']}")
    assert response1.json()["view_count"] == 1
    response2 = await client.get(f"/api/v1/posts/{post['slug']}")
    assert response2.json()["view_count"] == 2


async def test_get_post_not_found(client: AsyncClient):
    response = await client.get("/api/v1/posts/does-not-exist")
    assert response.status_code == 404


async def test_list_posts_hides_drafts_from_public(client: AsyncClient, auth_headers):
    await _create_post(client, auth_headers, title="Published Post", status="published")
    await _create_post(client, auth_headers, title="Draft Post", status="draft")

    response = await client.get("/api/v1/posts")
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Published Post" in titles
    assert "Draft Post" not in titles


async def test_author_can_update_own_post(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers, title="Original")
    response = await client.patch(
        f"/api/v1/posts/{post['id']}", json={"title": "Updated Title"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


async def test_non_author_cannot_update_post(client: AsyncClient, auth_headers, other_auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.patch(
        f"/api/v1/posts/{post['id']}", json={"title": "Hijacked"}, headers=other_auth_headers
    )
    assert response.status_code == 403


async def test_editor_can_update_any_post(client: AsyncClient, auth_headers, editor_auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.patch(
        f"/api/v1/posts/{post['id']}", json={"title": "Editor Edit"}, headers=editor_auth_headers
    )
    assert response.status_code == 200


async def test_author_can_delete_own_post(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.delete(f"/api/v1/posts/{post['id']}", headers=auth_headers)
    assert response.status_code == 200

    follow_up = await client.get(f"/api/v1/posts/{post['slug']}")
    assert follow_up.status_code == 404


async def test_post_with_category_and_tags(client: AsyncClient, auth_headers, editor_auth_headers):
    category_id = await _create_category(client, editor_auth_headers, "Programming")
    tag_id = await _create_tag(client, editor_auth_headers, "fastapi")

    post = await _create_post(
        client, auth_headers, title="Tagged Post", category_id=category_id, tag_ids=[tag_id]
    )
    assert post["category"]["id"] == category_id
    assert any(tag["id"] == tag_id for tag in post["tags"])


async def test_search_posts_by_title(client: AsyncClient, auth_headers):
    await _create_post(client, auth_headers, title="Unique Searchable Keyword")
    await _create_post(client, auth_headers, title="Something Else Entirely")

    response = await client.get("/api/v1/posts", params={"search": "Searchable"})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Unique Searchable Keyword"


async def test_pagination(client: AsyncClient, auth_headers):
    for i in range(5):
        await _create_post(client, auth_headers, title=f"Paginated Post {i}")

    response = await client.get("/api/v1/posts", params={"page": 1, "page_size": 2})
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5


async def test_toggle_like(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)

    like_resp = await client.post(f"/api/v1/posts/{post['id']}/like", headers=auth_headers)
    assert like_resp.status_code == 200
    assert like_resp.json()["message"] == "Post liked"

    detail = await client.get(f"/api/v1/posts/{post['slug']}", headers=auth_headers)
    assert detail.json()["like_count"] == 1
    assert detail.json()["is_liked"] is True

    unlike_resp = await client.post(f"/api/v1/posts/{post['id']}/like", headers=auth_headers)
    assert unlike_resp.json()["message"] == "Like removed"
