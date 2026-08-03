import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_unauthenticated_requests_rejected_across_protected_endpoints(client: AsyncClient):
    random_id = uuid.uuid4()
    protected_calls = [
        ("GET", "/api/v1/auth/me"),
        ("PATCH", "/api/v1/users/me"),
        ("DELETE", "/api/v1/users/me"),
        ("POST", "/api/v1/posts"),
        (
            "PATCH",
            f"/api/v1/posts/{random_id}",
        ),
        ("DELETE", f"/api/v1/posts/{random_id}"),
        ("POST", f"/api/v1/posts/{random_id}/like"),
        ("POST", "/api/v1/categories"),
        ("POST", "/api/v1/tags"),
        ("GET", "/api/v1/bookmarks"),
    ]
    for method, path in protected_calls:
        response = await client.request(method, path, json={} if method in ("POST", "PATCH") else None)
        assert response.status_code == 401, f"{method} {path} should require auth, got {response.status_code}"


async def test_regular_user_cannot_manage_taxonomy(client: AsyncClient, auth_headers):
    category_resp = await client.post("/api/v1/categories", json={"name": "Blocked"}, headers=auth_headers)
    assert category_resp.status_code == 403

    tag_resp = await client.post("/api/v1/tags", json={"name": "blocked"}, headers=auth_headers)
    assert tag_resp.status_code == 403


async def test_editor_can_manage_taxonomy_but_not_roles(
    client: AsyncClient, editor_auth_headers, regular_user
):
    category_resp = await client.post(
        "/api/v1/categories", json={"name": "Editor Allowed"}, headers=editor_auth_headers
    )
    assert category_resp.status_code == 201

    role_resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/role", json={"role": "admin"}, headers=editor_auth_headers
    )
    assert role_resp.status_code == 403


async def test_admin_has_full_access(client: AsyncClient, admin_auth_headers, regular_user):
    category_resp = await client.post(
        "/api/v1/categories", json={"name": "Admin Category"}, headers=admin_auth_headers
    )
    assert category_resp.status_code == 201

    role_resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/role", json={"role": "editor"}, headers=admin_auth_headers
    )
    assert role_resp.status_code == 200


async def test_deactivated_account_cannot_authenticate(client: AsyncClient, auth_headers, regular_user):
    delete_resp = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert delete_resp.status_code == 200

    # The old access token should now also be rejected since the user is inactive.
    me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_resp.status_code in (401, 403)


async def test_editor_cannot_delete_others_post_only_editor_or_author_can(
    client: AsyncClient, auth_headers, other_auth_headers
):
    post_resp = await client.post(
        "/api/v1/posts",
        json={"title": "Ownership Test", "content": "Body", "status": "published"},
        headers=auth_headers,
    )
    post_id = post_resp.json()["id"]

    forbidden_resp = await client.delete(f"/api/v1/posts/{post_id}", headers=other_auth_headers)
    assert forbidden_resp.status_code == 403


async def test_regular_user_cannot_list_drafts_via_explicit_status_filter(
    client: AsyncClient, auth_headers, other_auth_headers
):
    draft_resp = await client.post(
        "/api/v1/posts",
        json={"title": "Someone Elses Draft", "content": "Body", "status": "draft"},
        headers=auth_headers,
    )
    assert draft_resp.status_code == 201

    response = await client.get("/api/v1/posts", params={"status": "draft"}, headers=other_auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Someone Elses Draft" not in titles


async def test_anonymous_user_cannot_list_drafts_via_explicit_status_filter(
    client: AsyncClient, auth_headers
):
    draft_resp = await client.post(
        "/api/v1/posts",
        json={"title": "Anonymous Should Not See This", "content": "Body", "status": "draft"},
        headers=auth_headers,
    )
    assert draft_resp.status_code == 201

    response = await client.get("/api/v1/posts", params={"status": "draft"})
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Anonymous Should Not See This" not in titles


async def test_editor_can_list_drafts_via_explicit_status_filter(
    client: AsyncClient, auth_headers, editor_auth_headers
):
    draft_resp = await client.post(
        "/api/v1/posts",
        json={"title": "Editor Visible Draft", "content": "Body", "status": "draft"},
        headers=auth_headers,
    )
    assert draft_resp.status_code == 201

    response = await client.get("/api/v1/posts", params={"status": "draft"}, headers=editor_auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Editor Visible Draft" in titles
