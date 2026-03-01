"""
Tests for StockHoldingRepository and StockTransactionRepository
(app/repositories/stock.py)

StockHoldingRepository adds 2 custom methods on top of BaseRepository:
    get_by_user_and_symbol()  — find a specific holding by user + symbol
    get_by_user()             — list all holdings with quantity > 0 for a user

StockTransactionRepository adds 1 custom method on top of BaseRepository:
    get_by_user()             — paginated, newest-first transactions for a user

We do NOT re-test create/get/update/delete here — those are covered
in test_base_repo.py. We only test what each repository adds.
"""

import pytest
from decimal import Decimal

from app.repositories.stock import StockHoldingRepository, StockTransactionRepository
from app.repositories.user import UserRepository
from app.models.stock import StockTransactionType, StockTransactionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_data(email="stockuser@example.com", phone="8000000000"):
    return {
        "email": email,
        "phone": phone,
        "full_name": "Stock User",
        "password_hash": "hashed_pw",
    }


def holding_data(
    user_id: int,
    stock_symbol: str = "AAPL",
    quantity: int = 10,
    average_price: str = "150.00",
):
    return {
        "user_id": user_id,
        "stock_symbol": stock_symbol,
        "quantity": quantity,
        "average_price": Decimal(average_price),
    }


def stock_tx_data(
    user_id: int,
    transaction_number: str = "STX000000000001",
    stock_symbol: str = "AAPL",
    transaction_type: StockTransactionType = StockTransactionType.BUY,
    quantity: int = 10,
    price: str = "150.00",
    total_amount: str = "1500.00",
    transaction_fee: str = "10.00",
    status: StockTransactionStatus = StockTransactionStatus.COMPLETED,
):
    return {
        "user_id": user_id,
        "transaction_number": transaction_number,
        "stock_symbol": stock_symbol,
        "transaction_type": transaction_type,
        "quantity": quantity,
        "price": Decimal(price),
        "total_amount": Decimal(total_amount),
        "transaction_fee": Decimal(transaction_fee),
        "status": status,
    }


async def make_user(db_session, email="stockowner@example.com", phone="8000000000"):
    """Create and return a user to act as FK parent."""
    repo = UserRepository(db_session)
    return await repo.create(user_data(email=email, phone=phone))


# ===========================================================================
# StockHoldingRepository
# ===========================================================================

class TestGetByUserAndSymbol:

    @pytest.mark.asyncio
    async def test_returns_correct_holding(self, db_session):
        """Must return the holding that matches both user_id and stock_symbol."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        created = await repo.create(holding_data(user.user_id, stock_symbol="AAPL"))

        result = await repo.get_by_user_and_symbol(user.user_id, "AAPL")

        assert result is not None
        assert result.stock_symbol == "AAPL"
        assert result.holding_id == created.holding_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_symbol(self, db_session):
        """Symbol not held by the user → None, not an exception."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)

        result = await repo.get_by_user_and_symbol(user.user_id, "TSLA")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_user(self, db_session):
        """
        The same symbol held by a different user must not be returned.
        Both user_id AND symbol must match.
        """
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        repo = StockHoldingRepository(db_session)

        await repo.create(holding_data(user_a.user_id, stock_symbol="GOOG"))

        result = await repo.get_by_user_and_symbol(user_b.user_id, "GOOG")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_symbol_among_multiple(self, db_session):
        """Must return the right holding when a user holds several symbols."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        await repo.create(holding_data(user.user_id, stock_symbol="AAPL"))
        await repo.create(holding_data(user.user_id, stock_symbol="MSFT"))
        await repo.create(holding_data(user.user_id, stock_symbol="TSLA"))

        result = await repo.get_by_user_and_symbol(user.user_id, "MSFT")

        assert result is not None
        assert result.stock_symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_symbol_match_is_exact(self, db_session):
        """Partial or differently-cased symbols must not match."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        await repo.create(holding_data(user.user_id, stock_symbol="AAPL"))

        assert await repo.get_by_user_and_symbol(user.user_id, "aapl") is None
        assert await repo.get_by_user_and_symbol(user.user_id, "AAP") is None


class TestStockHoldingGetByUser:

    @pytest.mark.asyncio
    async def test_returns_all_holdings_with_positive_quantity(self, db_session):
        """Must return every holding where quantity > 0."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        await repo.create(holding_data(user.user_id, stock_symbol="AAPL", quantity=5))
        await repo.create(holding_data(user.user_id, stock_symbol="MSFT", quantity=10))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 2
        symbols = {h.stock_symbol for h in results}
        assert symbols == {"AAPL", "MSFT"}

    @pytest.mark.asyncio
    async def test_excludes_zero_quantity_holdings(self, db_session):
        """
        Holdings with quantity == 0 represent fully sold positions.
        get_by_user() must filter them out — they are not active holdings.
        """
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        await repo.create(holding_data(user.user_id, stock_symbol="AAPL", quantity=10))
        await repo.create(holding_data(user.user_id, stock_symbol="MSFT", quantity=0))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 1
        assert results[0].stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_holdings(self, db_session):
        """User with no holdings → empty list, not None or an exception."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)

        results = await repo.get_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_holdings(self, db_session):
        """Holdings belonging to a different user must not appear."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        repo = StockHoldingRepository(db_session)

        await repo.create(holding_data(user_a.user_id, stock_symbol="AAPL", quantity=5))
        await repo.create(holding_data(user_b.user_id, stock_symbol="TSLA", quantity=3))

        results = await repo.get_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_holdings_are_zero(self, db_session):
        """If every holding for a user has quantity == 0, return empty list."""
        user = await make_user(db_session)
        repo = StockHoldingRepository(db_session)
        await repo.create(holding_data(user.user_id, stock_symbol="AAPL", quantity=0))
        await repo.create(holding_data(user.user_id, stock_symbol="MSFT", quantity=0))

        results = await repo.get_by_user(user.user_id)

        assert results == []


# ===========================================================================
# StockTransactionRepository
# ===========================================================================

class TestStockTransactionGetByUser:

    @pytest.mark.asyncio
    async def test_returns_transactions_for_user(self, db_session):
        """Must return all transactions that belong to the given user."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)
        await repo.create(stock_tx_data(user.user_id, transaction_number="STX000000000001"))
        await repo.create(stock_tx_data(user.user_id, transaction_number="STX000000000002"))
        await repo.create(stock_tx_data(user.user_id, transaction_number="STX000000000003"))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 3
        tx_numbers = {t.transaction_number for t in results}
        assert tx_numbers == {"STX000000000001", "STX000000000002", "STX000000000003"}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_transactions(self, db_session):
        """User with no stock transactions → empty list."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        results = await repo.get_by_user(user.user_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_transactions(self, db_session):
        """Transactions belonging to a different user must not appear."""
        user_a = await make_user(db_session, email="a@example.com", phone="1111111111")
        user_b = await make_user(db_session, email="b@example.com", phone="2222222222")
        repo = StockTransactionRepository(db_session)

        await repo.create(stock_tx_data(user_a.user_id, transaction_number="STXA00000000001"))
        await repo.create(stock_tx_data(user_b.user_id, transaction_number="STXB00000000001"))

        results = await repo.get_by_user(user_a.user_id)

        assert len(results) == 1
        assert results[0].transaction_number == "STXA00000000001"

    @pytest.mark.asyncio
    async def test_default_limit_is_20(self, db_session):
        """With no explicit limit, at most 20 results must be returned."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        for i in range(25):
            await repo.create(stock_tx_data(user.user_id, transaction_number=f"STX{i:025d}"))

        results = await repo.get_by_user(user.user_id)

        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, db_session):
        """Explicit limit must cap the number of returned records."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        for i in range(10):
            await repo.create(stock_tx_data(user.user_id, transaction_number=f"STX{i:025d}"))

        results = await repo.get_by_user(user.user_id, limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_skip_offsets_results(self, db_session):
        """skip must offset into the result set, not duplicate or drop records."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        for i in range(10):
            await repo.create(stock_tx_data(user.user_id, transaction_number=f"STX{i:025d}"))

        page_1 = await repo.get_by_user(user.user_id, skip=0, limit=5)
        page_2 = await repo.get_by_user(user.user_id, skip=5, limit=5)

        ids_1 = {t.transaction_id for t in page_1}
        ids_2 = {t.transaction_id for t in page_2}

        assert len(ids_1) == 5
        assert len(ids_2) == 5
        assert ids_1.isdisjoint(ids_2), "Pages must not overlap"

    @pytest.mark.asyncio
    async def test_results_are_ordered_newest_first(self, engine):
        """
        get_by_user() orders by created_at DESC.

        PostgreSQL's func.now() returns the transaction start time, so two
        rows in the same open transaction share an identical created_at and
        DESC ordering between them is non-deterministic.

        We sidestep the conftest db_session entirely and manage two explicit
        committed transactions ourselves:
          - session1: creates the user + tx1, then commits (seals created_at)
          - session2: creates tx2 in a new transaction (later created_at)
        Both sessions are bound directly to the engine so commits are real.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

        # --- session1: user + first transaction, committed ------------------
        async with SessionFactory() as session1:
            user_repo = UserRepository(session1)
            user = await user_repo.create(
                user_data(email="ordering@example.com", phone="7000000001")
            )
            repo1 = StockTransactionRepository(session1)
            tx1 = await repo1.create(
                stock_tx_data(user.user_id, transaction_number="STXOLD0000001")
            )
            await session1.commit()

        # --- session2: second transaction — new DB transaction = later now() -
        async with SessionFactory() as session2:
            repo2 = StockTransactionRepository(session2)
            tx2 = await repo2.create(
                stock_tx_data(user.user_id, transaction_number="STXNEW0000001")
            )
            await session2.commit()

        # --- session3: read back and assert order ---------------------------
        async with SessionFactory() as session3:
            repo3 = StockTransactionRepository(session3)
            results = await repo3.get_by_user(user.user_id)

        returned_ids = [t.transaction_id for t in results]
        assert returned_ids.index(tx2.transaction_id) < returned_ids.index(tx1.transaction_id), \
            "Newer transaction (later timestamp) must appear first in DESC order"

    @pytest.mark.asyncio
    async def test_returns_all_transaction_types(self, db_session):
        """get_by_user() must not filter by transaction type."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        await repo.create(stock_tx_data(
            user.user_id, transaction_number="STXBUY0000001",
            transaction_type=StockTransactionType.BUY,
        ))
        await repo.create(stock_tx_data(
            user.user_id, transaction_number="STXSEL0000001",
            transaction_type=StockTransactionType.SELL,
        ))

        results = await repo.get_by_user(user.user_id)

        types = {t.transaction_type for t in results}
        assert StockTransactionType.BUY in types
        assert StockTransactionType.SELL in types

    @pytest.mark.asyncio
    async def test_returns_all_statuses(self, db_session):
        """get_by_user() must not filter by transaction status."""
        user = await make_user(db_session)
        repo = StockTransactionRepository(db_session)

        await repo.create(stock_tx_data(
            user.user_id, transaction_number="STXCMP0000001",
            status=StockTransactionStatus.COMPLETED,
        ))
        await repo.create(stock_tx_data(
            user.user_id, transaction_number="STXPND0000001",
            status=StockTransactionStatus.PENDING,
        ))
        await repo.create(stock_tx_data(
            user.user_id, transaction_number="STXFLD0000001",
            status=StockTransactionStatus.FAILED,
        ))

        results = await repo.get_by_user(user.user_id)

        statuses = {t.status for t in results}
        assert statuses == {
            StockTransactionStatus.COMPLETED,
            StockTransactionStatus.PENDING,
            StockTransactionStatus.FAILED,
        }