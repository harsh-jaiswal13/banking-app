"""
Integration tests for Authentication endpoints

Routes covered:
    POST /api/v1/auth/register   — new user registration
    POST /api/v1/auth/login      — login + token issuance
    POST /api/v1/auth/refresh    — access token refresh
    POST /api/v1/auth/logout     — logout / cookie clear
    GET  /api/v1/auth/me         — get current user (protected)
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_payload(**overrides):
    base = {
        "email": "auth_test@example.com",
        "password": "Passw0rd!",
        "full_name": "Auth Test User",
        "phone": "9000000001",
    }
    base.update(overrides)
    return base


# ===========================================================================
# POST /api/v1/auth/register
# ===========================================================================

class TestRegister:

    @pytest.mark.asyncio
    async def test_successful_registration_returns_201(self, client):
        response = await client.post("/api/v1/auth/register", json=user_payload())
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_response_contains_user_data(self, client):
        response = await client.post("/api/v1/auth/register", json=user_payload())
        data = response.json()
        # Response shape: {"data": {"access_token": ..., "user": {...}}, ...}
        outer = data.get("data", data)
        user = outer.get("user", outer)
        assert user["email"] == "auth_test@example.com"
        assert user["full_name"] == "Auth Test User"

    @pytest.mark.asyncio
    async def test_password_not_returned_in_response(self, client):
        response = await client.post("/api/v1/auth/register", json=user_payload())
        text = response.text
        assert "Passw0rd!" not in text
        assert "password_hash" not in text

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_error(self, client):
        await client.post("/api/v1/auth/register", json=user_payload())
        response = await client.post("/api/v1/auth/register", json=user_payload())
        assert response.status_code in (400, 409, 422)

    @pytest.mark.asyncio
    async def test_duplicate_phone_returns_error(self, client):
        await client.post("/api/v1/auth/register", json=user_payload())
        response = await client.post(
            "/api/v1/auth/register",
            json=user_payload(email="other@example.com"),  # different email, same phone
        )
        assert response.status_code in (400, 409, 422)

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "x@example.com", "password": "Passw0rd!"},  # no full_name, no phone
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email_format_returns_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json=user_payload(email="not-an-email"),
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_short_password_returns_422(self, client):
        """Password must be at least 8 characters per schema."""
        response = await client.post(
            "/api/v1/auth/register",
            json=user_payload(password="short"),
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_phone_format_returns_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json=user_payload(phone="not-a-phone"),
        )
        assert response.status_code == 422


# ===========================================================================
# POST /api/v1/auth/login
# ===========================================================================

class TestLogin:

    @pytest.mark.asyncio
    async def test_successful_login_returns_200(self, client, registered_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "Passw0rd!",
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_access_token(self, client, registered_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "Passw0rd!",
        })
        data = response.json()
        body = data.get("data", data)
        assert "access_token" in body
        assert len(body["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, client, registered_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "WrongPassword!",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_email_returns_401(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "Passw0rd!",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_email_returns_422(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "password": "Passw0rd!",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_password_returns_422(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
        })
        assert response.status_code == 422


# ===========================================================================
# GET /api/v1/auth/me
# ===========================================================================

class TestGetCurrentUser:

    @pytest.mark.asyncio
    async def test_returns_200_with_valid_token(self, auth_client):
        response = await auth_client.get("/api/v1/auth/me")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_correct_user_data(self, auth_client):
        response = await auth_client.get("/api/v1/auth/me")
        data = response.json()
        outer = data.get("data", data)
        user = outer.get("user", outer)
        assert user["email"] == "integration@example.com"
        assert user["full_name"] == "Integration User"

    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_401_with_invalid_token(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_password_not_in_response(self, auth_client):
        response = await auth_client.get("/api/v1/auth/me")
        assert "password" not in response.text
        assert "password_hash" not in response.text


# ===========================================================================
# POST /api/v1/auth/refresh
# ===========================================================================

class TestRefreshToken:
    """
    NOTE: There is a bug in app/services/auth.py:
        decode_token(refresh_token)
    should be:
        decode_token(refresh_token, expected_type="refresh")

    decode_token() defaults to expected_type="access", so it rejects a valid
    refresh token with "Invalid token type". Fix that line and these tests pass.
    """

    @pytest.mark.asyncio
    async def test_refresh_with_valid_token_returns_200(self, client, registered_user):
        login = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "Passw0rd!",
        })
        body = login.json().get("data", login.json())
        refresh_token = body.get("refresh_token")
        assert refresh_token, "Login must return a refresh_token"

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_refresh_returns_new_access_token(self, client, registered_user):
        login = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "Passw0rd!",
        })
        body = login.json().get("data", login.json())
        refresh_token = body.get("refresh_token")
        assert refresh_token, "Login must return a refresh_token"

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        new_body = response.json().get("data", response.json())
        assert "access_token" in new_body

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_is_rejected(self, client, registered_user):
        """Passing an access token to /refresh must be rejected — wrong token type."""
        login = await client.post("/api/v1/auth/login", json={
            "email": "integration@example.com",
            "password": "Passw0rd!",
        })
        body = login.json().get("data", login.json())
        access_token = body.get("access_token")

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},  # intentionally wrong token
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_returns_error(self, client):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "this.is.not.valid"},
        )
        assert response.status_code in (401, 422)


# ===========================================================================
# POST /api/v1/auth/logout
# ===========================================================================

class TestLogout:

    @pytest.mark.asyncio
    async def test_logout_returns_200(self, auth_client):
        response = await auth_client.post("/api/v1/auth/logout")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_logout_unauthenticated_still_returns_200(self, client):
        """Logout is idempotent — even without a token it clears cookies gracefully."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200