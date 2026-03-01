"""
Tests for TransactionRepository (app/repositories/transaction.py)

TransactionRepository adds 2 custom methods on top of BaseRepository:
    get_by_account()            — paginated, newest-first transactions for an account
    get_by_transaction_number() — find a transaction by its unique number

We do NOT re-test create/get/update/delete here — those are covered
in test_base_repo.py. We only test what TransactionRepository adds.

Note on ordering tests: PostgreSQL's func.now() resolves to the transaction
start time, so rows inserted in the same session share an identical
created_at. The ordering test bypasses db_session and manages its own
committed sessions via the engine fixture to guarantee distinct timestamps.
"""

import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.repositories.transaction import TransactionRepository
from app.repositories.account import AccountRepository
from app.repositories.user import UserRepository
from app.models.transaction import TransactionType, TransactionStatus
from app.models.savings_account import AccountStatus, AccountType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_data(email="txowner@example.com", phone="6000000000"):
    return {
        "email": email,
        "phone": phone,
        "full_name": "Tx Owner",
        "password_hash": "hashed_pw",
    }


def account_data(user_id: int, account_number: str = "TXACC000000001"):
    return {
        "user_id": user_id,
        "account_number": account_number,
        "balance": Decimal("5000.00"),
        "account_type": AccountType.REGULAR,
        "status": AccountStatus.ACTIVE,
        "interest_rate": Decimal("4.00"),
    }


def tx_data(
    account_id: int,
    transaction_number: str = "TXN000000000001",
    transaction_type: TransactionType = TransactionType.DEPOSIT,
    amount: str = "500.00",
    balance_after: str = "5500.00",
    status: TransactionStatus = TransactionStatus.SUCCESS,
    description: str = None,
    reference_id: str = None,
):
    return {
        "account_id": account_id,
        "transaction_number": transaction_number,
        "transaction_type": transaction_type,
        "amount": Decimal(amount),
        "balance_after": Decimal(balance_after),
        "status": status,
        "description": description,
        "reference_id": reference_id,
    }


async def make_user(db_session, email="txowner@example.com", phone="6000000000"):
    return await UserRepository(db_session).create(user_data(email=email, phone=phone))


async def make_account(db_session, user_id: int, account_number: str = "TXACC000000001"):
    return await AccountRepository(db_session).create(account_data(user_id, account_number))


# ---------------------------------------------------------------------------
# get_by_account()
# ---------------------------------------------------------------------------

class TestGetByAccount:

    @pytest.mark.asyncio
    async def test_returns_transactions_for_account(self, db_session):
        """Must return all transactions that belong to the given account."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        await repo.create(tx_data(account.account_id, transaction_number="TXN000000000001"))
        await repo.create(tx_data(account.account_id, transaction_number="TXN000000000002"))
        await repo.create(tx_data(account.account_id, transaction_number="TXN000000000003"))

        results = await repo.get_by_account(account.account_id)

        assert len(results) == 3
        numbers = {t.transaction_number for t in results}
        assert numbers == {"TXN000000000001", "TXN000000000002", "TXN000000000003"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_transactions(self, db_session):
        """Account with no transactions → empty list, not None or an exception."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        results = await repo.get_by_account(account.account_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_accounts_transactions(self, db_session):
        """Transactions from a different account must not appear."""
        user = await make_user(db_session)
        account_a = await make_account(db_session, user.user_id, "TXACCA0000001")
        account_b = await make_account(db_session, user.user_id, "TXACCB0000001")
        repo = TransactionRepository(db_session)

        await repo.create(tx_data(account_a.account_id, transaction_number="TXNA00000000001"))
        await repo.create(tx_data(account_b.account_id, transaction_number="TXNB00000000001"))

        results = await repo.get_by_account(account_a.account_id)

        assert len(results) == 1
        assert results[0].transaction_number == "TXNA00000000001"

    @pytest.mark.asyncio
    async def test_default_limit_is_20(self, db_session):
        """With no explicit limit, at most 20 results must be returned."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        for i in range(25):
            await repo.create(tx_data(account.account_id, transaction_number=f"TXN{i:027d}"))

        results = await repo.get_by_account(account.account_id)

        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, db_session):
        """Explicit limit must cap the number of returned records."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        for i in range(10):
            await repo.create(tx_data(account.account_id, transaction_number=f"TXN{i:027d}"))

        results = await repo.get_by_account(account.account_id, limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_skip_offsets_results(self, db_session):
        """skip must offset into the result set without duplicating or dropping records."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        for i in range(10):
            await repo.create(tx_data(account.account_id, transaction_number=f"TXN{i:027d}"))

        page_1 = await repo.get_by_account(account.account_id, skip=0, limit=5)
        page_2 = await repo.get_by_account(account.account_id, skip=5, limit=5)

        ids_1 = {t.transaction_id for t in page_1}
        ids_2 = {t.transaction_id for t in page_2}

        assert len(ids_1) == 5
        assert len(ids_2) == 5
        assert ids_1.isdisjoint(ids_2), "Pages must not overlap"

    @pytest.mark.asyncio
    async def test_returns_all_transaction_types(self, db_session):
        """get_by_account() must not filter by transaction type."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        for i, tx_type in enumerate(TransactionType):
            await repo.create(tx_data(
                account.account_id,
                transaction_number=f"TXNTYPE{i:023d}",
                transaction_type=tx_type,
            ))

        results = await repo.get_by_account(account.account_id)
        returned_types = {t.transaction_type for t in results}

        assert returned_types == set(TransactionType)

    @pytest.mark.asyncio
    async def test_returns_all_statuses(self, db_session):
        """get_by_account() must not filter by transaction status."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        await repo.create(tx_data(account.account_id, transaction_number="TXNSUC0000001", status=TransactionStatus.SUCCESS))
        await repo.create(tx_data(account.account_id, transaction_number="TXNFLD0000001", status=TransactionStatus.FAILED))
        await repo.create(tx_data(account.account_id, transaction_number="TXNPND0000001", status=TransactionStatus.PENDING))
        await repo.create(tx_data(account.account_id, transaction_number="TXNREV0000001", status=TransactionStatus.REVERSED))

        results = await repo.get_by_account(account.account_id)
        statuses = {t.status for t in results}

        assert statuses == set(TransactionStatus)

    @pytest.mark.asyncio
    async def test_results_are_ordered_newest_first(self, engine):
        """
        get_by_account() orders by created_at DESC.

        PostgreSQL's func.now() resolves to the transaction start time, so
        rows inserted in the same open session share an identical created_at.
        We bypass db_session and manage two explicit committed sessions so
        each insert lands in its own DB transaction with a distinct timestamp.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

        # session1: create user, account, and first transaction — then commit
        async with SessionFactory() as session1:
            user = await UserRepository(session1).create(
                user_data(email="txorder@example.com", phone="6000000001")
            )
            account = await AccountRepository(session1).create(
                account_data(user.user_id, "TXORDERACC0001")
            )
            repo1 = TransactionRepository(session1)
            tx1 = await repo1.create(tx_data(account.account_id, transaction_number="TXNOLD0000001"))
            await session1.commit()

        # session2: second transaction — new DB transaction = later created_at
        async with SessionFactory() as session2:
            repo2 = TransactionRepository(session2)
            tx2 = await repo2.create(tx_data(account.account_id, transaction_number="TXNNEW0000001"))
            await session2.commit()

        # session3: read back and assert DESC order
        async with SessionFactory() as session3:
            results = await TransactionRepository(session3).get_by_account(account.account_id)

        returned_ids = [t.transaction_id for t in results]
        assert returned_ids.index(tx2.transaction_id) < returned_ids.index(tx1.transaction_id), \
            "Newer transaction (later timestamp) must appear first in DESC order"


# ---------------------------------------------------------------------------
# get_by_transaction_number()
# ---------------------------------------------------------------------------

class TestGetByTransactionNumber:

    @pytest.mark.asyncio
    async def test_returns_correct_transaction(self, db_session):
        """Must return the transaction whose number matches exactly."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)
        created = await repo.create(tx_data(account.account_id, transaction_number="TXN111111111111"))

        result = await repo.get_by_transaction_number("TXN111111111111")

        assert result is not None
        assert result.transaction_number == "TXN111111111111"
        assert result.transaction_id == created.transaction_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_number(self, db_session):
        """Transaction number not in DB → None, not an exception."""
        repo = TransactionRepository(db_session)

        result = await repo.get_by_transaction_number("TXNDOESNOTEXIST")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_transaction_among_multiple(self, db_session):
        """Must not return the wrong transaction when multiple exist."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        await repo.create(tx_data(account.account_id, transaction_number="TXNAAA0000000001"))
        await repo.create(tx_data(account.account_id, transaction_number="TXNBBB0000000001"))
        await repo.create(tx_data(account.account_id, transaction_number="TXNCCC0000000001"))

        result = await repo.get_by_transaction_number("TXNBBB0000000001")

        assert result is not None
        assert result.transaction_number == "TXNBBB0000000001"

    @pytest.mark.asyncio
    async def test_match_is_exact(self, db_session):
        """Partial or differently-cased numbers must not match."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)
        await repo.create(tx_data(account.account_id, transaction_number="TXN999999999999"))

        assert await repo.get_by_transaction_number("txn999999999999") is None
        assert await repo.get_by_transaction_number("TXN99999999999") is None

    @pytest.mark.asyncio
    async def test_returns_none_after_transaction_deleted(self, db_session):
        """After deletion, the transaction number must no longer be found."""
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)
        tx = await repo.create(tx_data(account.account_id, transaction_number="TXNDEL0000000001"))

        assert await repo.get_by_transaction_number("TXNDEL0000000001") is not None

        await repo.delete(tx.transaction_id)

        assert await repo.get_by_transaction_number("TXNDEL0000000001") is None


# ---------------------------------------------------------------------------
# Uniqueness constraint
# ---------------------------------------------------------------------------

class TestUniquenessConstraints:

    @pytest.mark.asyncio
    async def test_two_transactions_cannot_share_transaction_number(self, db_session):
        """
        Attempting to create two transactions with the same transaction_number
        must fail at the DB level (UNIQUE constraint).
        """
        user = await make_user(db_session)
        account = await make_account(db_session, user.user_id)
        repo = TransactionRepository(db_session)

        await repo.create(tx_data(account.account_id, transaction_number="TXNDUP0000000001"))

        with pytest.raises(IntegrityError):
            await repo.create(tx_data(account.account_id, transaction_number="TXNDUP0000000001"))