import pytest
from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.asyncio


async def test_get_public_profile_by_username(client: AsyncClient, regular_user):
    response = await client.get(f"/api/v1/users/{regular_user.username}")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == regular_user.username
    assert "email" not in body  # public profile must not leak email


async def test_get_public_profile_not_found(client: AsyncClient):
    response = await client.get("/api/v1/users/does-not-exist")
    assert response.status_code == 404


async def test_update_own_profile(client: AsyncClient, auth_headers):
    response = await client.patch(
        "/api/v1/users/me", json={"full_name": "Updated Name", "bio": "New bio"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Updated Name"
    assert body["bio"] == "New bio"


async def test_update_profile_requires_auth(client: AsyncClient):
    response = await client.patch("/api/v1/users/me", json={"full_name": "Nope"})
    assert response.status_code == 401


async def test_change_email_success(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/users/me/change-email",
        json={"new_email": "changed@example.com", "current_password": TEST_PASSWORD},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "changed@example.com"
    assert body["is_email_verified"] is False


async def test_change_email_wrong_password(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/users/me/change-email",
        json={"new_email": "changed@example.com", "current_password": "WrongPass1"},
        headers=auth_headers,
    )
    assert response.status_code == 401


async def test_change_email_already_taken(client: AsyncClient, auth_headers, other_user):
    response = await client.post(
        "/api/v1/users/me/change-email",
        json={"new_email": other_user.email, "current_password": TEST_PASSWORD},
        headers=auth_headers,
    )
    assert response.status_code == 409


async def test_change_password_success(client: AsyncClient, auth_headers, regular_user):
    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "AnotherPass1"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": "AnotherPass1"}
    )
    assert login_resp.status_code == 200


async def test_change_password_wrong_current(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "WrongOne1", "new_password": "AnotherPass1"},
        headers=auth_headers,
    )
    assert response.status_code == 401


async def test_soft_delete_account(client: AsyncClient, auth_headers, regular_user):
    response = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": TEST_PASSWORD}
    )
    assert login_resp.status_code == 401


async def test_admin_can_change_role(client: AsyncClient, admin_auth_headers, regular_user):
    response = await client.patch(
        f"/api/v1/users/{regular_user.id}/role", json={"role": "editor"}, headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


async def test_non_admin_cannot_change_role(client: AsyncClient, auth_headers, other_user):
    response = await client.patch(
        f"/api/v1/users/{other_user.id}/role", json={"role": "admin"}, headers=auth_headers
    )
    assert response.status_code == 403
