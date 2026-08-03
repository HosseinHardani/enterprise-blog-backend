import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, create_special_token
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.asyncio


async def test_register_creates_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "StrongPass1",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["username"] == "newuser"
    assert body["is_email_verified"] is False
    assert "hashed_password" not in body


async def test_register_duplicate_email_rejected(client: AsyncClient, regular_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": regular_user.email, "username": "someoneelse", "password": "StrongPass1"},
    )
    assert response.status_code == 409
    assert response.json()["error"] == "already_exists"


async def test_register_duplicate_username_rejected(client: AsyncClient, regular_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "unique@example.com", "username": regular_user.username, "password": "StrongPass1"},
    )
    assert response.status_code == 409


async def test_login_success(client: AsyncClient, regular_user):
    response = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(client: AsyncClient, regular_user):
    response = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": "WrongPassword1"}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "nobody@example.com", "password": "WhoKnows1"}
    )
    assert response.status_code == 401


async def test_get_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_get_me_with_token(client: AsyncClient, auth_headers, regular_user):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == regular_user.email


async def test_refresh_token_rotates(client: AsyncClient, regular_user):
    login_resp = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": TEST_PASSWORD}
    )
    old_refresh_cookie = login_resp.cookies.get("refresh_token")
    assert old_refresh_cookie

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"]
    new_refresh_cookie = refresh_resp.cookies.get("refresh_token")
    assert new_refresh_cookie != old_refresh_cookie

    # Old refresh token must now be rejected (rotation / single-use).
    client.cookies.set("refresh_token", old_refresh_cookie)
    reuse_resp = await client.post("/api/v1/auth/refresh")
    assert reuse_resp.status_code == 401


async def test_refresh_without_cookie_fails(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_blacklists_access_token(client: AsyncClient, regular_user):
    login_resp = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": TEST_PASSWORD}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 401


async def test_verify_email_with_valid_token(client: AsyncClient, regular_user, db_session: AsyncSession):
    from datetime import timedelta

    token, _, _ = create_special_token(
        subject=str(regular_user.id),
        token_type=TokenType.EMAIL_VERIFICATION,
        expires_delta=timedelta(hours=1),
    )
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200

    await db_session.refresh(regular_user)
    assert regular_user.is_email_verified is True


async def test_verify_email_with_invalid_token(client: AsyncClient):
    response = await client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 401


async def test_password_reset_flow(client: AsyncClient, regular_user, db_session: AsyncSession):
    from datetime import timedelta

    token, _, _ = create_special_token(
        subject=str(regular_user.id), token_type=TokenType.PASSWORD_RESET, expires_delta=timedelta(hours=1)
    )
    response = await client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "password": "BrandNewPass1"}
    )
    assert response.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": TEST_PASSWORD}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", data={"username": regular_user.email, "password": "BrandNewPass1"}
    )
    assert new_login.status_code == 200


async def test_password_reset_request_does_not_leak_existence(client: AsyncClient):
    response = await client.post("/api/v1/auth/password-reset/request", json={"email": "ghost@example.com"})
    assert response.status_code == 200
