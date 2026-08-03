import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_post(client: AsyncClient, headers: dict, title: str = "Commentable Post") -> dict:
    response = await client.post(
        "/api/v1/posts", json={"title": title, "content": "Body", "status": "published"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_comment(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Great post!"}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content"] == "Great post!"
    assert body["post_id"] == post["id"]
    assert body["parent_id"] is None


async def test_create_comment_requires_auth(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    response = await client.post(f"/api/v1/posts/{post['id']}/comments", json={"content": "Anon comment"})
    assert response.status_code == 401


async def test_create_comment_on_missing_post(client: AsyncClient, auth_headers):
    import uuid

    response = await client.post(
        f"/api/v1/posts/{uuid.uuid4()}/comments", json={"content": "Ghost comment"}, headers=auth_headers
    )
    assert response.status_code == 404


async def test_reply_to_comment(client: AsyncClient, auth_headers, other_auth_headers):
    post = await _create_post(client, auth_headers)
    parent = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Top level"}, headers=auth_headers
    )
    parent_id = parent.json()["id"]

    reply = await client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"content": "A reply", "parent_id": parent_id},
        headers=other_auth_headers,
    )
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == parent_id


async def test_list_comments_includes_nested_replies(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    parent = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Top level"}, headers=auth_headers
    )
    parent_id = parent.json()["id"]
    await client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"content": "A reply", "parent_id": parent_id},
        headers=auth_headers,
    )

    response = await client.get(f"/api/v1/posts/{post['id']}/comments")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1  # only the top-level comment is listed directly
    assert len(items[0]["replies"]) == 1
    assert items[0]["replies"][0]["content"] == "A reply"


async def test_author_can_edit_own_comment(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    comment = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Original"}, headers=auth_headers
    )
    comment_id = comment.json()["id"]

    response = await client.patch(
        f"/api/v1/comments/{comment_id}", json={"content": "Edited"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Edited"


async def test_non_author_cannot_edit_comment(client: AsyncClient, auth_headers, other_auth_headers):
    post = await _create_post(client, auth_headers)
    comment = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Original"}, headers=auth_headers
    )
    comment_id = comment.json()["id"]

    response = await client.patch(
        f"/api/v1/comments/{comment_id}", json={"content": "Hijacked"}, headers=other_auth_headers
    )
    assert response.status_code == 403


async def test_author_can_delete_own_comment(client: AsyncClient, auth_headers):
    post = await _create_post(client, auth_headers)
    comment = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Delete me"}, headers=auth_headers
    )
    comment_id = comment.json()["id"]

    response = await client.delete(f"/api/v1/comments/{comment_id}", headers=auth_headers)
    assert response.status_code == 200


async def test_editor_can_delete_others_comment(client: AsyncClient, auth_headers, editor_auth_headers):
    post = await _create_post(client, auth_headers)
    comment = await client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"content": "Moderated"}, headers=auth_headers
    )
    comment_id = comment.json()["id"]

    response = await client.delete(f"/api/v1/comments/{comment_id}", headers=editor_auth_headers)
    assert response.status_code == 200
