"""
Tests for AccountRepository (app/repositories/account.py)

AccountRepository adds 5 custom query methods on top of BaseRepository:
    get_by_account_number()  — find account by its unique account number
    get_by_user()            — list all accounts belonging to a user
    get_active_by_user()     — list only ACTIVE accounts for a user
    update_balance()         — update the balance of an account
    account_number_exists()  — boolean check for account number uniqueness

We do NOT re-test create/get/update/delete here — those are covered
in test_base_repo.py. We only test what AccountRepository adds.
"""

import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.repositories.account import AccountRepository
from app.repositories.user import UserRepository
from app.models.savings_account import AccountStatus, AccountType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_data(
    email="accountowner@example.com",
    phone="9000000000",
    full_name="Account Owner",
    password_hash="hashed_pw",
):
    return {"email": email, "phone": phone,
            "full_name": full_name, "password_hash": password_hash}


def account_data(
    user_id: int,
    account_number: str = "ACC0000000001",
    balance: str = "1000.00",
    account_type: AccountType = AccountType.REGULAR,
    status: AccountStatus = AccountStatus.ACTIVE,
    interest_rate: str = "4.00",
):
    return {
        "user_id": user_id,
        "account_number": account_number,
        "balance": Decimal(balance),
        "account_type": account_type,
        "status": status,
        "interest_rate": Decimal(interest_rate),
    }


async def make_user(db_session, email="owner@example.com", phone="9000000000"):
    """Create and return a user to act as FK parent for accounts."""
    repo = UserRepository(db_session)
    return await repo.create(user_data(email=email, phone=phone))


# ---------------------------------------------------------------------------
# get_by_account_number()
# ---------------------------------------------------------------------------

class TestGetByAccountNumber:

    @pytest.mark.asyncio
    async def test_returns_correct_account(self, db_session):
        """Must return the account whose account_number matches exactly."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        created = await repo.create(account_data(user.user_id, account_number="ACC1111111111"))

        result = await repo.get_by_account_number("ACC1111111111")

        assert result is not None
        assert result.account_number == "ACC1111111111"
        assert result.account_id == created.account_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_account_number(self, db_session):
        """Account number not in DB → None, not an exception."""
        repo = AccountRepository(db_session)

        result = await repo.get_by_account_number("DOESNOTEXIST")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_account_among_multiple(self, db_session):
        """Must not return the wrong account when multiple accounts exist."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACC0000000001"))
        await repo.create(account_data(user.user_id, account_number="ACC0000000002"))

        result = await repo.get_by_account_number("ACC0000000002")

        assert result is not None
        assert result.account_number == "ACC0000000002"

    @pytest.mark.asyncio
    async def test_is_exact_match(self, db_session):
        """Partial or differently-cased numbers must not match."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACC1234567890"))

        assert await repo.get_by_account_number("acc1234567890") is None
        assert await repo.get_by_account_number("ACC123456789") is None


# ---------------------------------------------------------------------------
# get_by_user()
# ---------------------------------------------------------------------------

class TestGetByUser:

    @pytest.mark.asyncio
    async def test_returns_all_accounts_for_user(self, db_session):
        """Must return every account that belongs to the given user."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACC0000000001"))
        await repo.create(account_data(user.user_id, account_number="ACC0000000002"))
        await repo.create(account_data(user.user_id, account_number="ACC0000000003"))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 3
        numbers = {a.account_number for a in results}
        assert numbers == {"ACC0000000001", "ACC0000000002", "ACC0000000003"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_accounts(self, db_session):
        """User with no accounts → empty list, not None or an exception."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)

        results = await repo.get_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_accounts(self, db_session):
        """Accounts belonging to a different user must not appear in results."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        repo = AccountRepository(db_session)

        await repo.create(account_data(user_a.user_id, account_number="ACCA00000001"))
        await repo.create(account_data(user_b.user_id, account_number="ACCB00000001"))

        results = await repo.get_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].account_number == "ACCA00000001"

    @pytest.mark.asyncio
    async def test_returns_accounts_of_all_statuses(self, db_session):
        """get_by_user() must not filter by status — it returns everything."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)

        await repo.create(account_data(user.user_id, account_number="ACC_ACTIVE", status=AccountStatus.ACTIVE))
        await repo.create(account_data(user.user_id, account_number="ACC_FROZEN", status=AccountStatus.FROZEN))
        await repo.create(account_data(user.user_id, account_number="ACC_CLOSED", status=AccountStatus.CLOSED))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 3


# ---------------------------------------------------------------------------
# get_active_by_user()
# ---------------------------------------------------------------------------

class TestGetActiveByUser:

    @pytest.mark.asyncio
    async def test_returns_only_active_accounts(self, db_session):
        """Must return only accounts with status == ACTIVE."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)

        await repo.create(account_data(user.user_id, account_number="ACC_ACTIVE1", status=AccountStatus.ACTIVE))
        await repo.create(account_data(user.user_id, account_number="ACC_ACTIVE2", status=AccountStatus.ACTIVE))
        await repo.create(account_data(user.user_id, account_number="ACC_FROZEN1", status=AccountStatus.FROZEN))
        await repo.create(account_data(user.user_id, account_number="ACC_CLOSED1", status=AccountStatus.CLOSED))

        results = await repo.get_active_by_user(user.user_id)

        assert len(results) == 2
        assert all(a.status == AccountStatus.ACTIVE for a in results)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_active_accounts(self, db_session):
        """User with only non-active accounts → empty list."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)

        await repo.create(account_data(user.user_id, account_number="ACC_FROZEN", status=AccountStatus.FROZEN))
        await repo.create(account_data(user.user_id, account_number="ACC_CLOSED", status=AccountStatus.CLOSED))

        results = await repo.get_active_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_active_accounts(self, db_session):
        """Active accounts from a different user must not appear."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        repo = AccountRepository(db_session)

        await repo.create(account_data(user_a.user_id, account_number="ACCA_ACTIVE", status=AccountStatus.ACTIVE))
        await repo.create(account_data(user_b.user_id, account_number="ACCB_ACTIVE", status=AccountStatus.ACTIVE))

        results = await repo.get_active_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].account_number == "ACCA_ACTIVE"

    @pytest.mark.asyncio
    async def test_returns_empty_for_user_with_no_accounts(self, db_session):
        """User that has never had an account → empty list."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)

        results = await repo.get_active_by_user(user.user_id)

        assert results == []


# ---------------------------------------------------------------------------
# update_balance()
# ---------------------------------------------------------------------------

class TestUpdateBalance:

    @pytest.mark.asyncio
    async def test_updates_balance_to_new_value(self, db_session):
        """Balance must reflect the new value after update_balance()."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        account = await repo.create(account_data(user.user_id, balance="500.00"))

        updated = await repo.update_balance(account.account_id, Decimal("1500.00"))

        assert updated.balance == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_persists_balance_to_database(self, db_session):
        """A fresh get() after update_balance() must return the new balance."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        account = await repo.create(account_data(user.user_id, balance="500.00"))

        await repo.update_balance(account.account_id, Decimal("9999.99"))
        fetched = await repo.get(account.account_id)

        assert fetched.balance == Decimal("9999.99")

    @pytest.mark.asyncio
    async def test_does_not_alter_other_fields(self, db_session):
        """update_balance() must only change balance, nothing else."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        account = await repo.create(account_data(
            user.user_id,
            account_number="ACCSTABLE0001",
            status=AccountStatus.ACTIVE,
            account_type=AccountType.SALARY,
        ))

        updated = await repo.update_balance(account.account_id, Decimal("42.00"))

        assert updated.account_number == "ACCSTABLE0001"
        assert updated.status == AccountStatus.ACTIVE
        assert updated.account_type == AccountType.SALARY

    @pytest.mark.asyncio
    async def test_accepts_zero_balance(self, db_session):
        """Zero is a valid balance (e.g. after a full withdrawal)."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        account = await repo.create(account_data(user.user_id, balance="100.00"))

        updated = await repo.update_balance(account.account_id, Decimal("0.00"))

        assert updated.balance == Decimal("0.00")


# ---------------------------------------------------------------------------
# account_number_exists()
# ---------------------------------------------------------------------------

class TestAccountNumberExists:

    @pytest.mark.asyncio
    async def test_returns_true_for_existing_account_number(self, db_session):
        """Account number already in DB → True."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACCEXISTS00001"))

        result = await repo.account_number_exists("ACCEXISTS00001")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_account_number(self, db_session):
        """Account number not in DB → False."""
        repo = AccountRepository(db_session)

        result = await repo.account_number_exists("ACCGHOST000001")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_different_account_number(self, db_session):
        """Creating one account must not affect existence checks for other numbers."""
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACCALICE000001"))

        result = await repo.account_number_exists("ACCBOB0000001")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_after_account_deleted(self, db_session):
        """
        After an account is deleted, its number must be considered available.
        account_number_exists() queries live DB state, not a cache.
        """
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        account = await repo.create(account_data(user.user_id, account_number="ACCDELETED0001"))

        assert await repo.account_number_exists("ACCDELETED0001") is True

        await repo.delete(account.account_id)

        assert await repo.account_number_exists("ACCDELETED0001") is False

    @pytest.mark.asyncio
    async def test_returns_true_immediately_after_creation(self, db_session):
        """
        account_number_exists() must return True right after create() —
        no cache lag. Tests that create() commits before the check queries.
        """
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACCINSTANT0001"))

        result = await repo.account_number_exists("ACCINSTANT0001")

        assert result is True


# ---------------------------------------------------------------------------
# Uniqueness constraint
# ---------------------------------------------------------------------------

class TestUniquenessConstraints:

    @pytest.mark.asyncio
    async def test_two_accounts_cannot_share_account_number(self, db_session):
        """
        Attempting to create two accounts with the same account_number must
        fail at the DB level (UNIQUE constraint), not silently succeed.
        """
        user = await make_user(db_session)
        repo = AccountRepository(db_session)
        await repo.create(account_data(user.user_id, account_number="ACCDUP0000001"))

        with pytest.raises(IntegrityError):
            await repo.create(account_data(user.user_id, account_number="ACCDUP0000001"))