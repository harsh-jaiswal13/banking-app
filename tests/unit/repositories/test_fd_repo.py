"""
Tests for FixedDepositRepository (app/repositories/fixed_deposit.py)

FixedDepositRepository adds 7 custom methods on top of BaseRepository:
    get_by_user()              — all FDs for a user, newest-first
    get_active_by_user()       — only ACTIVE FDs for a user
    get_by_user_with_status()  — all FDs optionally filtered by status, newest-first
    fd_number_exists()         — boolean check for FD number uniqueness
    get_by_fd_number()         — find an FD by its unique fd_number
    get_active_fds_count()     — count of ACTIVE FDs for a user
    get_total_fd_amount()      — sum of principal_amount for ACTIVE FDs

We do NOT re-test create/get/update/delete here — those are covered
in test_base_repo.py. We only test what FixedDepositRepository adds.

Note on ordering tests: PostgreSQL's func.now() resolves to the transaction
start time, so rows inserted in the same session share an identical
created_at. The ordering test bypasses db_session and manages its own
committed sessions via the engine fixture to guarantee distinct timestamps.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError

from app.repositories.fixed_deposit import FixedDepositRepository
from app.repositories.account import AccountRepository
from app.repositories.user import UserRepository
from app.models.fixed_deposit import FDStatus
from app.models.savings_account import AccountStatus, AccountType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_data(email="fdowner@example.com", phone="5000000000"):
    return {
        "email": email,
        "phone": phone,
        "full_name": "FD Owner",
        "password_hash": "hashed_pw",
    }


def account_data(user_id: int, account_number: str = "FDACC000000001"):
    return {
        "user_id": user_id,
        "account_number": account_number,
        "balance": Decimal("100000.00"),
        "account_type": AccountType.REGULAR,
        "status": AccountStatus.ACTIVE,
        "interest_rate": Decimal("4.00"),
    }


def fd_data(
    user_id: int,
    savings_account_id: int,
    fd_number: str = "FD0000000000001",
    principal_amount: str = "10000.00",
    interest_rate: str = "7.00",
    tenure_months: int = 12,
    maturity_amount: str = "10700.00",
    maturity_date: date = None,
    status: FDStatus = FDStatus.ACTIVE,
):
    return {
        "user_id": user_id,
        "savings_account_id": savings_account_id,
        "fd_number": fd_number,
        "principal_amount": Decimal(principal_amount),
        "interest_rate": Decimal(interest_rate),
        "tenure_months": tenure_months,
        "maturity_amount": Decimal(maturity_amount),
        "maturity_date": maturity_date or (date.today() + timedelta(days=365)),
        "status": status,
    }


async def make_user(db_session, email="fdowner@example.com", phone="5000000000"):
    return await UserRepository(db_session).create(user_data(email=email, phone=phone))


async def make_account(db_session, user_id: int, account_number: str = "FDACC000000001"):
    return await AccountRepository(db_session).create(account_data(user_id, account_number))


# ---------------------------------------------------------------------------
# get_by_user()
# ---------------------------------------------------------------------------

class TestGetByUser:

    @pytest.mark.asyncio
    async def test_returns_all_fds_for_user(self, db_session):
        """Must return every FD belonging to the given user."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FD0000000000001"))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FD0000000000002"))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FD0000000000003"))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 3
        numbers = {fd.fd_number for fd in results}
        assert numbers == {"FD0000000000001", "FD0000000000002", "FD0000000000003"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_fds(self, db_session):
        """User with no FDs → empty list, not None or an exception."""
        user = await make_user(db_session)
        repo = FixedDepositRepository(db_session)

        results = await repo.get_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_fds(self, db_session):
        """FDs belonging to a different user must not appear."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        account_a = await make_account(db_session, user_a.user_id, "FDACCA0000001")
        account_b = await make_account(db_session, user_b.user_id, "FDACCB0000001")
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user_a.user_id, account_a.account_id, fd_number="FDUSERA000001"))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDUSERB000001"))

        results = await repo.get_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].fd_number == "FDUSERA000001"

    @pytest.mark.asyncio
    async def test_returns_fds_of_all_statuses(self, db_session):
        """get_by_user() must not filter by status — it returns everything."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACTIVE000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMATURED00001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLOSED000001", status=FDStatus.CLOSED))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 3
        statuses = {fd.status for fd in results}
        assert statuses == set(FDStatus)

    @pytest.mark.asyncio
    async def test_results_are_ordered_newest_first(self, engine):
        """
        get_by_user() orders by created_at DESC.
        We bypass db_session and use committed sessions directly against
        the engine to guarantee distinct server-side created_at timestamps.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

        async with SessionFactory() as session1:
            user = await UserRepository(session1).create(
                user_data(email="fdorder@example.com", phone="5000000001")
            )
            account = await AccountRepository(session1).create(
                account_data(user.user_id, "FDORDERACC0001")
            )
            fd1 = await FixedDepositRepository(session1).create(
                fd_data(user.user_id, account.account_id, fd_number="FDOLD0000000001")
            )
            await session1.commit()

        async with SessionFactory() as session2:
            fd2 = await FixedDepositRepository(session2).create(
                fd_data(user.user_id, account.account_id, fd_number="FDNEW0000000001")
            )
            await session2.commit()

        async with SessionFactory() as session3:
            results = await FixedDepositRepository(session3).get_by_user(user.user_id)

        returned_ids = [fd.fd_id for fd in results]
        assert returned_ids.index(fd2.fd_id) < returned_ids.index(fd1.fd_id), \
            "Newer FD (later timestamp) must appear first in DESC order"


# ---------------------------------------------------------------------------
# get_active_by_user()
# ---------------------------------------------------------------------------

class TestGetActiveByUser:

    @pytest.mark.asyncio
    async def test_returns_only_active_fds(self, db_session):
        """Must return only FDs with status == ACTIVE."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000002", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", status=FDStatus.CLOSED))

        results = await repo.get_active_by_user(user.user_id)

        assert len(results) == 2
        assert all(fd.status == FDStatus.ACTIVE for fd in results)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_active_fds(self, db_session):
        """User with only non-active FDs → empty list."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", status=FDStatus.CLOSED))

        results = await repo.get_active_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_active_fds(self, db_session):
        """Active FDs from a different user must not appear."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        account_a = await make_account(db_session, user_a.user_id, "FDACCA0000001")
        account_b = await make_account(db_session, user_b.user_id, "FDACCB0000001")
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user_a.user_id, account_a.account_id, fd_number="FDACTA000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDACTB000001", status=FDStatus.ACTIVE))

        results = await repo.get_active_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].fd_number == "FDACTA000001"

    @pytest.mark.asyncio
    async def test_returns_empty_for_user_with_no_fds(self, db_session):
        """User that has never had an FD → empty list."""
        user = await make_user(db_session)
        repo = FixedDepositRepository(db_session)

        results = await repo.get_active_by_user(user.user_id)

        assert results == []


# ---------------------------------------------------------------------------
# get_by_user_with_status()
# ---------------------------------------------------------------------------

class TestGetByUserWithStatus:

    @pytest.mark.asyncio
    async def test_returns_all_fds_when_no_status_filter(self, db_session):
        """Called with status=None must return all FDs regardless of status."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", status=FDStatus.CLOSED))

        results = await repo.get_by_user_with_status(user.user_id)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_filters_by_active_status(self, db_session):
        """Passing status=ACTIVE must return only ACTIVE FDs."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))

        results = await repo.get_by_user_with_status(user.user_id, status=FDStatus.ACTIVE)

        assert len(results) == 1
        assert results[0].status == FDStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_filters_by_matured_status(self, db_session):
        """Passing status=MATURED must return only MATURED FDs."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000002", status=FDStatus.MATURED))

        results = await repo.get_by_user_with_status(user.user_id, status=FDStatus.MATURED)

        assert len(results) == 2
        assert all(fd.status == FDStatus.MATURED for fd in results)

    @pytest.mark.asyncio
    async def test_filters_by_closed_status(self, db_session):
        """Passing status=CLOSED must return only CLOSED FDs."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", status=FDStatus.CLOSED))

        results = await repo.get_by_user_with_status(user.user_id, status=FDStatus.CLOSED)

        assert len(results) == 1
        assert results[0].status == FDStatus.CLOSED

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_match_for_status(self, db_session):
        """Status filter with no matching FDs → empty list."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))

        results = await repo.get_by_user_with_status(user.user_id, status=FDStatus.CLOSED)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_fds(self, db_session):
        """Status-filtered results must still be scoped to the given user."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        account_a = await make_account(db_session, user_a.user_id, "FDACCA0000001")
        account_b = await make_account(db_session, user_b.user_id, "FDACCB0000001")
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user_a.user_id, account_a.account_id, fd_number="FDACTA000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDACTB000001", status=FDStatus.ACTIVE))

        results = await repo.get_by_user_with_status(user_a.user_id, status=FDStatus.ACTIVE)

        assert len(results) == 1
        assert results[0].fd_number == "FDACTA000001"


# ---------------------------------------------------------------------------
# fd_number_exists()
# ---------------------------------------------------------------------------

class TestFdNumberExists:

    @pytest.mark.asyncio
    async def test_returns_true_for_existing_fd_number(self, db_session):
        """FD number already in DB → True."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDEXISTS000001"))

        result = await repo.fd_number_exists("FDEXISTS000001")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_fd_number(self, db_session):
        """FD number not in DB → False."""
        repo = FixedDepositRepository(db_session)

        result = await repo.fd_number_exists("FDGHOST0000001")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_different_fd_number(self, db_session):
        """Creating one FD must not affect existence checks for other numbers."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDALICE000001"))

        result = await repo.fd_number_exists("FDBOB00000001")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_after_fd_deleted(self, db_session):
        """After deletion, the FD number must be considered available."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        fd = await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDDEL0000001"))

        assert await repo.fd_number_exists("FDDEL0000001") is True

        await repo.delete(fd.fd_id)

        assert await repo.fd_number_exists("FDDEL0000001") is False

    @pytest.mark.asyncio
    async def test_returns_true_immediately_after_creation(self, db_session):
        """fd_number_exists() must return True right after create() — no cache lag."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDINSTANT00001"))

        result = await repo.fd_number_exists("FDINSTANT00001")

        assert result is True


# ---------------------------------------------------------------------------
# get_by_fd_number()
# ---------------------------------------------------------------------------

class TestGetByFdNumber:

    @pytest.mark.asyncio
    async def test_returns_correct_fd(self, db_session):
        """Must return the FD whose fd_number matches exactly."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        created = await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDLOOKUP000001"))

        result = await repo.get_by_fd_number("FDLOOKUP000001")

        assert result is not None
        assert result.fd_number == "FDLOOKUP000001"
        assert result.fd_id == created.fd_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_fd_number(self, db_session):
        """FD number not in DB → None, not an exception."""
        repo = FixedDepositRepository(db_session)

        result = await repo.get_by_fd_number("FDNOBODY000001")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_fd_among_multiple(self, db_session):
        """Must not return the wrong FD when multiple exist."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDAAA0000001"))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDBBB0000001"))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCCC0000001"))

        result = await repo.get_by_fd_number("FDBBB0000001")

        assert result is not None
        assert result.fd_number == "FDBBB0000001"

    @pytest.mark.asyncio
    async def test_match_is_exact(self, db_session):
        """Partial or differently-cased numbers must not match."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDEXACT000001"))

        assert await repo.get_by_fd_number("fdexact000001") is None
        assert await repo.get_by_fd_number("FDEXACT00000") is None


# ---------------------------------------------------------------------------
# get_active_fds_count()
# ---------------------------------------------------------------------------

class TestGetActiveFdsCount:

    @pytest.mark.asyncio
    async def test_returns_correct_count_of_active_fds(self, db_session):
        """Must return the exact number of ACTIVE FDs for the user."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000002", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))

        count = await repo.get_active_fds_count(user.user_id)

        assert count == 2

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_active_fds(self, db_session):
        """User with no ACTIVE FDs → 0, not None or an exception."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", status=FDStatus.CLOSED))

        count = await repo.get_active_fds_count(user.user_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_user_with_no_fds(self, db_session):
        """User with no FDs at all → 0."""
        user = await make_user(db_session)
        repo = FixedDepositRepository(db_session)

        count = await repo.get_active_fds_count(user.user_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_does_not_count_other_users_active_fds(self, db_session):
        """Active FDs from other users must not be included in the count."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        account_a = await make_account(db_session, user_a.user_id, "FDACCA0000001")
        account_b = await make_account(db_session, user_b.user_id, "FDACCB0000001")
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user_a.user_id, account_a.account_id, fd_number="FDACTA000001"))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDACTB000001"))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDACTB000002"))

        count = await repo.get_active_fds_count(user_a.user_id)

        assert count == 1

    @pytest.mark.asyncio
    async def test_count_decrements_after_status_change(self, db_session):
        """Count must reflect current DB state after an FD's status changes."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        fd = await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", status=FDStatus.ACTIVE))
        assert await repo.get_active_fds_count(user.user_id) == 1

        await repo.update(fd, {"status": FDStatus.CLOSED})
        assert await repo.get_active_fds_count(user.user_id) == 0


# ---------------------------------------------------------------------------
# get_total_fd_amount()
# ---------------------------------------------------------------------------

class TestGetTotalFdAmount:

    @pytest.mark.asyncio
    async def test_returns_sum_of_active_principal_amounts(self, db_session):
        """Must return the total principal of all ACTIVE FDs."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", principal_amount="10000.00"))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000002", principal_amount="25000.00"))

        total = await repo.get_total_fd_amount(user.user_id)

        assert total == pytest.approx(35000.00)

    @pytest.mark.asyncio
    async def test_excludes_non_active_fds_from_sum(self, db_session):
        """MATURED and CLOSED FDs must not be included in the total."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", principal_amount="10000.00", status=FDStatus.ACTIVE))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDMAT0000001", principal_amount="50000.00", status=FDStatus.MATURED))
        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDCLS0000001", principal_amount="20000.00", status=FDStatus.CLOSED))

        total = await repo.get_total_fd_amount(user.user_id)

        assert total == pytest.approx(10000.00)

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_active_fds(self, db_session):
        """User with no ACTIVE FDs → 0.0, not None or an exception."""
        user = await make_user(db_session)
        repo = FixedDepositRepository(db_session)

        total = await repo.get_total_fd_amount(user.user_id)

        assert total == 0.0

    @pytest.mark.asyncio
    async def test_returns_zero_for_user_with_no_fds(self, db_session):
        """User with no FDs at all → 0.0."""
        user = await make_user(db_session)
        repo = FixedDepositRepository(db_session)

        total = await repo.get_total_fd_amount(user.user_id)

        assert total == 0.0

    @pytest.mark.asyncio
    async def test_does_not_include_other_users_fds_in_sum(self, db_session):
        """Active FDs from other users must not be included in the total."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        account_a = await make_account(db_session, user_a.user_id, "FDACCA0000001")
        account_b = await make_account(db_session, user_b.user_id, "FDACCB0000001")
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user_a.user_id, account_a.account_id, fd_number="FDACTA000001", principal_amount="15000.00"))
        await repo.create(fd_data(user_b.user_id, account_b.account_id, fd_number="FDACTB000001", principal_amount="99000.00"))

        total = await repo.get_total_fd_amount(user_a.user_id)

        assert total == pytest.approx(15000.00)

    @pytest.mark.asyncio
    async def test_total_updates_after_fd_closed(self, db_session):
        """Total must reflect current DB state after an FD is closed."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        fd = await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDACT0000001", principal_amount="20000.00"))
        assert await repo.get_total_fd_amount(user.user_id) == pytest.approx(20000.00)

        await repo.update(fd, {"status": FDStatus.CLOSED})
        assert await repo.get_total_fd_amount(user.user_id) == 0.0


# ---------------------------------------------------------------------------
# Uniqueness constraint
# ---------------------------------------------------------------------------

class TestUniquenessConstraints:

    @pytest.mark.asyncio
    async def test_two_fds_cannot_share_fd_number(self, db_session):
        """
        Attempting to create two FDs with the same fd_number must fail
        at the DB level (UNIQUE constraint), not silently succeed.
        """
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = FixedDepositRepository(db_session)

        await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDDUP0000001"))

        with pytest.raises(IntegrityError):
            await repo.create(fd_data(user.user_id, account.account_id, fd_number="FDDUP0000001"))