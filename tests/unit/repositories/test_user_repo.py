"""
Tests for UserRepository (app/repositories/user.py)

UserRepository adds 4 custom query methods on top of BaseRepository:
    get_by_email()   — find user by email address
    get_by_phone()   — find user by phone number
    email_exists()   — boolean check for email uniqueness
    phone_exists()   — boolean check for phone uniqueness

We do NOT re-test create/get/update/delete here — those are covered
in test_base_repo.py. We only test what UserRepository adds.

All tests use a real in-memory SQLite DB (via conftest.py).
"""

import pytest
from app.repositories.user import UserRepository


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def user_data(
    email="test@example.com",
    phone="9876543210",
    full_name="Test User",
    password_hash="hashed_pw",
):
    return {"email": email, "phone": phone,
            "full_name": full_name, "password_hash": password_hash}


# ---------------------------------------------------------------------------
# get_by_email()
# ---------------------------------------------------------------------------

class TestGetByEmail:

    @pytest.mark.asyncio
    async def test_returns_correct_user(self, db_session):
        """Must return the user whose email matches exactly"""
        repo = UserRepository(db_session)
        created = await repo.create(user_data(email="john@example.com"))

        result = await repo.get_by_email("john@example.com")

        assert result is not None
        assert result.email == "john@example.com"
        assert result.user_id == created.user_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_email(self, db_session):
        """Email not in DB → None, not an exception"""
        repo = UserRepository(db_session)

        result = await repo.get_by_email("nobody@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_user_among_multiple(self, db_session):
        """Must not return the wrong user when multiple users exist"""
        repo = UserRepository(db_session)
        await repo.create(user_data(email="alice@example.com", phone="1111111111"))
        await repo.create(user_data(email="bob@example.com", phone="2222222222"))

        result = await repo.get_by_email("bob@example.com")

        assert result.email == "bob@example.com"

    @pytest.mark.asyncio
    async def test_is_case_sensitive(self, db_session):
        """
        SQL WHERE email = ? uses exact match.
        "JOHN@example.com" is a different string from "john@example.com".
        """
        repo = UserRepository(db_session)
        await repo.create(user_data(email="john@example.com"))

        result = await repo.get_by_email("JOHN@EXAMPLE.COM")

        assert result is None


# ---------------------------------------------------------------------------
# get_by_phone()
# ---------------------------------------------------------------------------

class TestGetByPhone:

    @pytest.mark.asyncio
    async def test_returns_correct_user(self, db_session):
        """Must return user with matching phone number"""
        repo = UserRepository(db_session)
        created = await repo.create(user_data(phone="9876543210"))

        result = await repo.get_by_phone("9876543210")

        assert result is not None
        assert result.phone == "9876543210"
        assert result.user_id == created.user_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_phone(self, db_session):
        """Phone not in DB → None"""
        repo = UserRepository(db_session)

        result = await repo.get_by_phone("0000000000")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_user_among_multiple(self, db_session):
        """Must return the right user when multiple users have different phones"""
        repo = UserRepository(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))

        result = await repo.get_by_phone("2222222222")

        assert result.phone == "2222222222"
        assert result.email == "b@x.com"


# ---------------------------------------------------------------------------
# email_exists()
# ---------------------------------------------------------------------------

class TestEmailExists:

    @pytest.mark.asyncio
    async def test_returns_true_for_registered_email(self, db_session):
        """Email already in DB → True"""
        repo = UserRepository(db_session)
        await repo.create(user_data(email="taken@example.com"))

        result = await repo.email_exists("taken@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unregistered_email(self, db_session):
        """Email not in DB → False"""
        repo = UserRepository(db_session)

        result = await repo.email_exists("new@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_different_email(self, db_session):
        """Registering one email must not affect existence checks for others"""
        repo = UserRepository(db_session)
        await repo.create(user_data(email="alice@example.com"))

        result = await repo.email_exists("bob@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_after_user_deleted(self, db_session):
        """
        After a user is deleted, their email must be considered available again.
        email_exists() queries live DB state, not a cache.
        """
        repo = UserRepository(db_session)
        user = await repo.create(user_data(email="leaving@example.com"))

        assert await repo.email_exists("leaving@example.com") is True

        await repo.delete(user.user_id)

        assert await repo.email_exists("leaving@example.com") is False

    @pytest.mark.asyncio
    async def test_returns_true_immediately_after_registration(self, db_session):
        """
        email_exists() must return True right after create() — no cache lag.
        Tests that create() commits before email_exists() queries.
        """
        repo = UserRepository(db_session)
        await repo.create(user_data(email="instant@example.com"))

        result = await repo.email_exists("instant@example.com")

        assert result is True


# ---------------------------------------------------------------------------
# phone_exists()
# ---------------------------------------------------------------------------

class TestPhoneExists:

    @pytest.mark.asyncio
    async def test_returns_true_for_registered_phone(self, db_session):
        """Phone already in DB → True"""
        repo = UserRepository(db_session)
        await repo.create(user_data(phone="9876543210"))

        result = await repo.phone_exists("9876543210")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unregistered_phone(self, db_session):
        """Phone not in DB → False"""
        repo = UserRepository(db_session)

        result = await repo.phone_exists("0000000000")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_different_phone(self, db_session):
        """Registering one phone must not affect checks for other numbers"""
        repo = UserRepository(db_session)
        await repo.create(user_data(phone="1111111111"))

        result = await repo.phone_exists("2222222222")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_after_user_deleted(self, db_session):
        """
        After deleting a user, their phone number must be available again.
        This is important for re-registration flows.
        """
        repo = UserRepository(db_session)
        user = await repo.create(user_data(phone="9999999999"))

        assert await repo.phone_exists("9999999999") is True

        await repo.delete(user.user_id)

        assert await repo.phone_exists("9999999999") is False


# ---------------------------------------------------------------------------
# Cross-field uniqueness
# ---------------------------------------------------------------------------

class TestUniquenessConstraints:

    @pytest.mark.asyncio
    async def test_two_users_cannot_share_email(self, db_session):
        """
        Attempting to create two users with the same email must fail
        at the DB level (UNIQUE constraint), not silently succeed.
        """
        from sqlalchemy.exc import IntegrityError

        repo = UserRepository(db_session)
        await repo.create(user_data(email="same@example.com", phone="1111111111"))

        with pytest.raises(IntegrityError):
            await repo.create(user_data(email="same@example.com", phone="2222222222"))

    @pytest.mark.asyncio
    async def test_two_users_cannot_share_phone(self, db_session):
        """
        Attempting to create two users with the same phone must fail
        at the DB level (UNIQUE constraint).
        """
        from sqlalchemy.exc import IntegrityError

        repo = UserRepository(db_session)
        await repo.create(user_data(email="a@example.com", phone="9876543210"))

        with pytest.raises(IntegrityError):
            await repo.create(user_data(email="b@example.com", phone="9876543210"))