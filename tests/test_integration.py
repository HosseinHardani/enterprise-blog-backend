import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_full_content_lifecycle(
    client: AsyncClient, admin_auth_headers, auth_headers, other_auth_headers
):
    category_resp = await client.post(
        "/api/v1/categories", json={"name": "Integration Category"}, headers=admin_auth_headers
    )
    assert category_resp.status_code == 201
    category_id = category_resp.json()["id"]

    tag_resp = await client.post("/api/v1/tags", json={"name": "integration-tag"}, headers=admin_auth_headers)
    assert tag_resp.status_code == 201
    tag_id = tag_resp.json()["id"]

    post_resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "Integration Test Post",
            "content": "Full lifecycle content",
            "status": "published",
            "category_id": category_id,
            "tag_ids": [tag_id],
        },
        headers=auth_headers,
    )
    assert post_resp.status_code == 201
    post = post_resp.json()
    assert post["category"]["id"] == category_id
    assert any(t["id"] == tag_id for t in post["tags"])

    detail_resp = await client.get(f"/api/v1/posts/{post['slug']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["view_count"] == 1

    comment_resp = await client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"content": "Nice integration post"},
        headers=other_auth_headers,
    )
    assert comment_resp.status_code == 201
    comment_id = comment_resp.json()["id"]

    reply_resp = await client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"content": "Thanks!", "parent_id": comment_id},
        headers=auth_headers,
    )
    assert reply_resp.status_code == 201

    like_resp = await client.post(f"/api/v1/posts/{post['id']}/like", headers=other_auth_headers)
    assert like_resp.status_code == 200

    bookmark_resp = await client.post(f"/api/v1/bookmarks/{post['id']}", headers=other_auth_headers)
    assert bookmark_resp.status_code == 201

    enriched = await client.get(f"/api/v1/posts/{post['slug']}", headers=other_auth_headers)
    body = enriched.json()
    assert body["like_count"] == 1
    assert body["comment_count"] == 2
    assert body["is_liked"] is True
    assert body["is_bookmarked"] is True

    comments_list = await client.get(f"/api/v1/posts/{post['id']}/comments")
    assert comments_list.json()["total"] == 1
    assert len(comments_list.json()["items"][0]["replies"]) == 1

    bookmarks_list = await client.get("/api/v1/bookmarks", headers=other_auth_headers)
    assert bookmarks_list.json()["total"] == 1

    delete_resp = await client.delete(f"/api/v1/posts/{post['id']}", headers=auth_headers)
    assert delete_resp.status_code == 200

    gone_resp = await client.get(f"/api/v1/posts/{post['slug']}")
    assert gone_resp.status_code == 404


async def test_role_escalation_lifecycle(client: AsyncClient, admin_auth_headers, regular_user, other_user):
    promote_resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/role", json={"role": "editor"}, headers=admin_auth_headers
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "editor"

    login_resp = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": "TestPass123"}
    )
    token = login_resp.json()["access_token"]
    editor_headers = {"Authorization": f"Bearer {token}"}

    category_resp = await client.post(
        "/api/v1/categories", json={"name": "Post Promotion Category"}, headers=editor_headers
    )
    assert category_resp.status_code == 201


async def test_pagination_consistency_across_pages(client: AsyncClient, auth_headers):
    titles = [f"Consistency Post {i}" for i in range(7)]
    for title in titles:
        response = await client.post(
            "/api/v1/posts",
            json={"title": title, "content": "Body", "status": "published"},
            headers=auth_headers,
        )
        assert response.status_code == 201

    seen_ids = set()
    page = 1
    page_size = 3
    total = None
    while True:
        response = await client.get("/api/v1/posts", params={"page": page, "page_size": page_size})
        body = response.json()
        total = body["total"]
        for item in body["items"]:
            assert item["id"] not in seen_ids
            seen_ids.add(item["id"])
        if page >= body["pages"]:
            break
        page += 1

    assert len(seen_ids) == total
