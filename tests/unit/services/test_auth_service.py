"""
Unit tests for AuthService (app/services/auth.py)

Run with:  pytest tests/unit/test_auth_service.py -v

How mocking works here:
  - AuthService depends on UserRepository (talks to DB)
  - We replace UserRepository with a MagicMock so NO real DB is needed
  - AsyncMock is used for async methods (methods with `await`)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.auth import AuthService
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    UnauthorizedException,
)


# ---------------------------------------------------------------------------
# Helpers — reusable fake objects
# ---------------------------------------------------------------------------

def make_fake_user(
    user_id=1,
    email="john@example.com",
    full_name="John Doe",
    phone="9876543210",
    password_hash="hashed_password_123",
    kyc_status="pending",
):
    """Returns a fake user object that mimics your SQLAlchemy User model."""
    user = MagicMock()
    user.user_id = user_id
    user.email = email
    user.full_name = full_name
    user.phone = phone
    user.password_hash = password_hash
    user.kyc_status.value = kyc_status  # .value because your code does kyc_status.value
    user.created_at = "2024-01-01T00:00:00"
    return user


def make_mock_repo(user=None):
    """
    Returns a fake UserRepository with all async methods pre-configured.
    Pass a user object to simulate a found user, or leave as None for not found.
    """
    repo = MagicMock()
    repo.email_exists = AsyncMock(return_value=False)
    repo.phone_exists = AsyncMock(return_value=False)
    repo.get_by_email = AsyncMock(return_value=user)
    repo.get = AsyncMock(return_value=user)
    repo.create = AsyncMock(return_value=user)
    return repo


# ---------------------------------------------------------------------------
# CHECKPOINT A — register()
# ---------------------------------------------------------------------------

class TestRegister:
    """Tests for AuthService.register()"""

    @pytest.mark.asyncio
    async def test_register_success_returns_tokens_and_user(self):
        """Happy path: new email + phone → should return tokens + user info"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)

        service = AuthService(user_repo=repo)

        with patch("app.services.auth.get_password_hash", return_value="hashed_pw"), \
             patch("app.services.auth.create_access_token", return_value="access_tok"), \
             patch("app.services.auth.create_refresh_token", return_value="refresh_tok"):

            result = await service.register(
                email="john@example.com",
                password="SecurePass123",
                full_name="John Doe",
                phone="9876543210",
            )

        # Tokens must be present
        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"
        assert result["token_type"] == "bearer"

        # User info must be present
        assert result["user"]["email"] == "john@example.com"
        assert result["user"]["user_id"] == 1

    @pytest.mark.asyncio
    async def test_register_raises_if_email_already_exists(self):
        """Duplicate email → UserAlreadyExistsException"""
        repo = make_mock_repo()
        repo.email_exists = AsyncMock(return_value=True)   # ← email taken

        service = AuthService(user_repo=repo)

        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await service.register("taken@example.com", "pass", "Name", "1234567890")

        assert "Email" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_raises_if_phone_already_exists(self):
        """Duplicate phone → UserAlreadyExistsException"""
        repo = make_mock_repo()
        repo.email_exists = AsyncMock(return_value=False)
        repo.phone_exists = AsyncMock(return_value=True)   # ← phone taken

        service = AuthService(user_repo=repo)

        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await service.register("new@example.com", "pass", "Name", "9876543210")

        assert "Phone" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_hashes_password_before_storing(self):
        """Password must NEVER be stored as plain text"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)
        service = AuthService(user_repo=repo)

        with patch("app.services.auth.get_password_hash", return_value="hashed_pw") as mock_hash, \
             patch("app.services.auth.create_access_token", return_value="tok"), \
             patch("app.services.auth.create_refresh_token", return_value="tok"):

            await service.register("j@example.com", "PlainPassword", "J", "1111111111")

        # get_password_hash must have been called with the plain password
        mock_hash.assert_called_once_with("PlainPassword")

        # The data sent to repo.create must have the hashed version, not plain
        call_kwargs = repo.create.call_args[0][0]  # first positional arg (the dict)
        assert call_kwargs["password_hash"] == "hashed_pw"
        assert "PlainPassword" not in str(call_kwargs)


# ---------------------------------------------------------------------------
# CHECKPOINT B — login()
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for AuthService.login()"""

    @pytest.mark.asyncio
    async def test_login_success_returns_tokens_and_user(self):
        """Correct email + password → tokens + user info"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)
        service = AuthService(user_repo=repo)

        with patch("app.services.auth.verify_password", return_value=True), \
             patch("app.services.auth.create_access_token", return_value="access_tok"), \
             patch("app.services.auth.create_refresh_token", return_value="refresh_tok"):

            result = await service.login("john@example.com", "CorrectPass")

        assert result["access_token"] == "access_tok"
        assert result["user"]["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_login_raises_if_user_not_found(self):
        """Email doesn't exist → InvalidCredentialsException"""
        repo = make_mock_repo(user=None)   # ← no user found
        service = AuthService(user_repo=repo)

        with pytest.raises(InvalidCredentialsException):
            await service.login("ghost@example.com", "anypass")

    @pytest.mark.asyncio
    async def test_login_raises_if_password_wrong(self):
        """Email exists but wrong password → InvalidCredentialsException"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)
        service = AuthService(user_repo=repo)

        with patch("app.services.auth.verify_password", return_value=False):   # ← wrong pw
            with pytest.raises(InvalidCredentialsException):
                await service.login("john@example.com", "WrongPass")

    @pytest.mark.asyncio
    async def test_login_does_not_expose_password_hash_in_response(self):
        """password_hash must never appear in login response"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)
        service = AuthService(user_repo=repo)

        with patch("app.services.auth.verify_password", return_value=True), \
             patch("app.services.auth.create_access_token", return_value="tok"), \
             patch("app.services.auth.create_refresh_token", return_value="tok"):

            result = await service.login("john@example.com", "pass")

        assert "password_hash" not in str(result)
        assert "password" not in result["user"]


# # ---------------------------------------------------------------------------
# # CHECKPOINT C — refresh_token()
# # ---------------------------------------------------------------------------

# class TestRefreshToken:
#     """Tests for AuthService.refresh_token()"""

#     @pytest.mark.asyncio
#     async def test_valid_refresh_token_returns_new_tokens(self):
#         """Valid refresh token → new access + refresh tokens"""
#         fake_user = make_fake_user()
#         repo = make_mock_repo(user=fake_user)
#         service = AuthService(user_repo=repo)

#         valid_payload = {"type": "refresh", "sub": "1", "email": "john@example.com"}

#         with patch("app.services.auth.decode_token", return_value=valid_payload), \
#              patch("app.services.auth.create_access_token", return_value="new_access"), \
#              patch("app.services.auth.create_refresh_token", return_value="new_refresh"):

#             result = await service.refresh_token("some_refresh_token")

#         assert result["access_token"] == "new_access"
#         assert result["refresh_token"] == "new_refresh"

#     @pytest.mark.asyncio
#     async def test_refresh_token_raises_if_token_invalid(self):
#         """Garbage token (decode returns None) → UnauthorizedException"""
#         repo = make_mock_repo()
#         service = AuthService(user_repo=repo)

#         with patch("app.services.auth.decode_token", return_value=None):
#             with pytest.raises(UnauthorizedException):
#                 await service.refresh_token("garbage_token")

#     @pytest.mark.asyncio
#     async def test_refresh_token_raises_if_wrong_token_type(self):
#         """Access token used as refresh token → UnauthorizedException"""
#         repo = make_mock_repo()
#         service = AuthService(user_repo=repo)

#         # type is "access", not "refresh"
#         wrong_type_payload = {"type": "access", "sub": "1", "email": "john@example.com"}

#         with patch("app.services.auth.decode_token", return_value=wrong_type_payload):
#             with pytest.raises(UnauthorizedException):
#                 await service.refresh_token("access_token_used_as_refresh")

#     @pytest.mark.asyncio
#     async def test_refresh_token_raises_if_user_deleted(self):
#         """Token is valid but user was deleted from DB → UnauthorizedException"""
#         repo = make_mock_repo(user=None)   # ← user no longer exists
#         service = AuthService(user_repo=repo)

#         valid_payload = {"type": "refresh", "sub": "1", "email": "john@example.com"}

#         with patch("app.services.auth.decode_token", return_value=valid_payload):
#             with pytest.raises(UnauthorizedException):
#                 await service.refresh_token("valid_token_deleted_user")


# # ---------------------------------------------------------------------------
# # CHECKPOINT D — get_current_user()
# # ---------------------------------------------------------------------------

# class TestGetCurrentUser:
    """Tests for AuthService.get_current_user()"""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_info(self):
        """Valid token → user dict with id, email, full_name"""
        fake_user = make_fake_user()
        repo = make_mock_repo(user=fake_user)
        service = AuthService(user_repo=repo)

        valid_payload = {"sub": "1", "email": "john@example.com"}

        with patch("app.services.auth.decode_token", return_value=valid_payload):
            result = await service.get_current_user("valid_token")

        assert result["user_id"] == 1
        assert result["email"] == "john@example.com"
        assert result["full_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        """decode_token returns None → UnauthorizedException"""
        repo = make_mock_repo()
        service = AuthService(user_repo=repo)

        with patch("app.services.auth.decode_token", return_value=None):
            with pytest.raises(UnauthorizedException):
                await service.get_current_user("bad_token")

    @pytest.mark.asyncio
    async def test_missing_sub_in_payload_raises(self):
        """Token payload missing 'sub' field → UnauthorizedException"""
        repo = make_mock_repo()
        service = AuthService(user_repo=repo)

        payload_without_sub = {"email": "john@example.com"}  # no "sub"

        with patch("app.services.auth.decode_token", return_value=payload_without_sub):
            with pytest.raises(UnauthorizedException):
                await service.get_current_user("incomplete_token")