"""
Unit Tests for StockService (app/services/stock.py)

Run with:
    pytest tests/unit/test_stock_service.py -v
    pytest tests/unit/test_stock_service.py::TestBuyStock -v
    pytest tests/unit/test_stock_service.py -v --cov=app/services/stock

WHAT'S NEW vs account tests:
    1. StockService has FOUR dependencies — all need mocking
    2. account_service is a service mocked inside another service (nested mock)
    3. Fee math needs exact Decimal assertions
    4. Average price recalculation logic needs its own tests
    5. sell_stock deletes a holding when quantity hits zero
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.stock import StockService
from app.models.stock import StockTransactionType, StockTransactionStatus
from app.core.exceptions import (
    AccountNotFoundException,
    InsufficientBalanceException,
    BankingException,
)


# ---------------------------------------------------------------------------
# Helpers — Fake objects
# ---------------------------------------------------------------------------

def make_fake_account(account_id=1, user_id=1, balance=Decimal("10000.00")):
    account = MagicMock()
    account.account_id = account_id
    account.user_id = user_id
    account.balance = balance
    return account


def make_fake_holding(
    holding_id=1,
    user_id=1,
    stock_symbol="AAPL",
    quantity=10,
    average_price=Decimal("170.00"),
):
    holding = MagicMock()
    holding.holding_id = holding_id
    holding.user_id = user_id
    holding.stock_symbol = stock_symbol
    holding.quantity = quantity
    holding.average_price = average_price
    return holding


def make_fake_stock_transaction(
    transaction_id=201,
    transaction_number="STK123456",
    stock_symbol="AAPL",
    transaction_type=StockTransactionType.BUY,
    quantity=5,
    price=Decimal("175.50"),
):
    txn = MagicMock()
    txn.transaction_id = transaction_id
    txn.transaction_number = transaction_number
    txn.stock_symbol = stock_symbol
    # transaction_type: assign real enum — .value is already set by the enum itself
    txn.transaction_type = transaction_type
    txn.quantity = quantity
    txn.price = price
    txn.total_amount = price * quantity
    txn.transaction_fee = txn.total_amount * Decimal("0.001")
    # status: assign real enum — do NOT set .value after, enums are read-only
    txn.status = StockTransactionStatus.COMPLETED
    txn.created_at = "2024-01-01T10:00:00"
    return txn


def make_mock_repos(account=None, holding=None, transactions=None, total=0):
    """
    Build all 3 repository mocks at once.
    Returns (holding_repo, stock_txn_repo, account_repo)
    """
    holding_repo = MagicMock()
    holding_repo.get_by_user_and_symbol = AsyncMock(return_value=holding)
    holding_repo.get_by_user = AsyncMock(return_value=[holding] if holding else [])
    holding_repo.create = AsyncMock(return_value=holding)
    holding_repo.update = AsyncMock(return_value=holding)
    holding_repo.delete = AsyncMock(return_value=None)

    stock_txn_repo = MagicMock()
    stock_txn_repo.create = AsyncMock(return_value=make_fake_stock_transaction())
    stock_txn_repo.get_by_user = AsyncMock(return_value=transactions or [])
    stock_txn_repo.count = AsyncMock(return_value=total)

    account_repo = MagicMock()
    account_repo.get = AsyncMock(return_value=account)

    return holding_repo, stock_txn_repo, account_repo


def make_mock_account_service():
    """
    account_service is a SERVICE used inside StockService.
    We mock it just like a repo — replacing async methods with AsyncMock.
    
    WHY: buy_stock calls account_service.withdraw()
         sell_stock calls account_service.deposit()
    We don't want those to actually run — they have their own tests.
    We just want to verify they were called with the right arguments.
    """
    svc = MagicMock()
    svc.withdraw = AsyncMock(return_value={"balance_after": 8000.0})
    svc.deposit = AsyncMock(return_value={"balance_after": 12000.0})
    return svc


def make_service(account=None, holding=None, transactions=None, total=0):
    """One-liner to build StockService with all 4 dependencies mocked."""
    holding_repo, stock_txn_repo, account_repo = make_mock_repos(
        account=account, holding=holding, transactions=transactions, total=total
    )
    account_service = make_mock_account_service()
    service = StockService(
        holding_repo=holding_repo,
        stock_transaction_repo=stock_txn_repo,
        account_repo=account_repo,
        account_service=account_service,
    )
    return service, holding_repo, stock_txn_repo, account_repo, account_service


# ---------------------------------------------------------------------------
# CHECKPOINT A — get_mock_price() and get_all_prices()
# These are pure sync methods — no async, no DB — simplest tests in the file
# ---------------------------------------------------------------------------

class TestGetMockPrice:

    def test_returns_correct_price_for_known_symbol(self):
        """AAPL → 175.50 (matches MOCK_STOCK_PRICES dict)"""
        service, *_ = make_service()
        price = service.get_mock_price("AAPL")
        assert price == Decimal("175.50")

    def test_symbol_lookup_is_case_insensitive(self):
        """'aapl', 'Aapl', 'AAPL' should all work"""
        service, *_ = make_service()
        assert service.get_mock_price("aapl") == service.get_mock_price("AAPL")
        assert service.get_mock_price("Msft") == service.get_mock_price("MSFT")

    def test_raises_for_unknown_symbol(self):
        """Unknown ticker → BankingException with status_code 404"""
        service, *_ = make_service()
        with pytest.raises(BankingException) as exc_info:
            service.get_mock_price("FAKE")
        assert exc_info.value.status_code == 404

    def test_get_all_prices_returns_all_8_stocks(self):
        """All 8 stocks in MOCK_STOCK_PRICES must appear in the list"""
        service, *_ = make_service()
        prices = service.get_all_prices()
        assert len(prices) == 8

    def test_get_all_prices_each_item_has_required_fields(self):
        """Each item must have symbol, name, price"""
        service, *_ = make_service()
        prices = service.get_all_prices()
        for item in prices:
            assert "symbol" in item
            assert "name" in item
            assert "price" in item

    def test_get_all_prices_returns_floats_not_decimals(self):
        """price field must be float (JSON serializable), not Decimal"""
        service, *_ = make_service()
        prices = service.get_all_prices()
        for item in prices:
            assert isinstance(item["price"], float)


# ---------------------------------------------------------------------------
# CHECKPOINT B — buy_stock()
#
# Most complex method — validate → check balance → withdraw → update holding
# → record transaction
# Pay attention to fee math and average price recalculation
# ---------------------------------------------------------------------------

class TestBuyStock:

    @pytest.mark.asyncio
    async def test_buy_stock_success_returns_transaction_dict(self):
        """Happy path: sufficient balance, valid symbol → transaction info returned"""
        account = make_fake_account(balance=Decimal("10000.00"))
        service, *_ = make_service(account=account)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            result = await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=5
            )

        assert result["stock_symbol"] == "AAPL"
        assert result["quantity"] == 5
        assert result["transaction_type"] == "BUY"
        assert "transaction_fee" in result
        assert "total_with_fee" in result

    @pytest.mark.asyncio
    async def test_buy_stock_fee_calculation_is_correct(self):
        """
        Fee = 0.1% of total_amount
        AAPL price = 175.50, quantity = 10
        total_amount    = 175.50 * 10  = 1755.00
        transaction_fee = 1755.00 * 0.001 = 1.755
        total_with_fee  = 1755.00 + 1.755 = 1756.755
        """
        account = make_fake_account(balance=Decimal("10000.00"))
        service, *_ = make_service(account=account)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            result = await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=10
            )

        assert result["total_amount"] == pytest.approx(1755.00)
        assert result["transaction_fee"] == pytest.approx(1.755)
        assert result["total_with_fee"] == pytest.approx(1756.755)

    @pytest.mark.asyncio
    async def test_buy_stock_withdraws_total_with_fee_from_account(self):
        """
        account_service.withdraw() must be called with total_amount + fee,
        NOT just total_amount. Fee must never be skipped.
        """
        account = make_fake_account(balance=Decimal("10000.00"))
        service, _, _, _, account_service = make_service(account=account)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=10
            )

        # Verify withdraw was called
        account_service.withdraw.assert_called_once()
        call_kwargs = account_service.withdraw.call_args.kwargs
        # total_with_fee = 1756.755
        assert call_kwargs["amount"] == pytest.approx(Decimal("1756.755"), rel=Decimal("0.001"))
        assert call_kwargs["account_id"] == 1
        assert call_kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_buy_stock_creates_new_holding_if_none_exists(self):
        """First time buying a stock → holding_repo.create() called"""
        account = make_fake_account(balance=Decimal("10000.00"))
        # holding=None means user doesn't own this stock yet
        service, holding_repo, *_ = make_service(account=account, holding=None)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=5
            )

        holding_repo.create.assert_called_once()
        created_data = holding_repo.create.call_args[0][0]
        assert created_data["stock_symbol"] == "AAPL"
        assert created_data["quantity"] == 5

    @pytest.mark.asyncio
    async def test_buy_stock_updates_existing_holding_average_price(self):
        """
        User already owns 10 AAPL at avg 170.00.
        They buy 10 more at current price 175.50.

        New average price = (10 * 170 + 10 * 175.50) / 20
                          = (1700 + 1755) / 20
                          = 3455 / 20
                          = 172.75
        """
        account = make_fake_account(balance=Decimal("20000.00"))
        existing_holding = make_fake_holding(quantity=10, average_price=Decimal("170.00"))
        service, holding_repo, *_ = make_service(account=account, holding=existing_holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=10
            )

        # holding_repo.update must be called (not create)
        holding_repo.update.assert_called_once()
        holding_repo.create.assert_not_called()

        updated_data = holding_repo.update.call_args[0][1]  # second positional arg
        assert updated_data["quantity"] == 20
        assert float(updated_data["average_price"]) == pytest.approx(172.75)

    @pytest.mark.asyncio
    async def test_buy_stock_raises_if_quantity_zero(self):
        """quantity=0 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.buy_stock(user_id=1, account_id=1, stock_symbol="AAPL", quantity=0)

    @pytest.mark.asyncio
    async def test_buy_stock_raises_if_quantity_negative(self):
        """quantity=-5 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.buy_stock(user_id=1, account_id=1, stock_symbol="AAPL", quantity=-5)

    @pytest.mark.asyncio
    async def test_buy_stock_raises_if_account_not_found(self):
        """No account in DB → AccountNotFoundException"""
        service, *_ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.buy_stock(user_id=1, account_id=999, stock_symbol="AAPL", quantity=5)

    @pytest.mark.asyncio
    async def test_buy_stock_raises_if_wrong_account_owner(self):
        """Account belongs to user 2, user 1 tries to buy → AccountNotFoundException"""
        account = make_fake_account(user_id=2)
        service, *_ = make_service(account=account)

        with pytest.raises(AccountNotFoundException):
            await service.buy_stock(user_id=1, account_id=1, stock_symbol="AAPL", quantity=5)

    @pytest.mark.asyncio
    async def test_buy_stock_raises_if_insufficient_balance(self):
        """
        Account balance too low to cover total_with_fee → InsufficientBalanceException
        AAPL * 100 shares = 17550 + fee ≈ 17567 > balance of 1000
        """
        account = make_fake_account(balance=Decimal("1000.00"))
        service, *_ = make_service(account=account)

        with pytest.raises(InsufficientBalanceException):
            await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="AAPL", quantity=100
            )

    @pytest.mark.asyncio
    async def test_buy_stock_symbol_uppercased_internally(self):
        """Lowercase 'aapl' passed in → stored and returned as 'AAPL'"""
        account = make_fake_account(balance=Decimal("10000.00"))
        service, *_ = make_service(account=account)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            result = await service.buy_stock(
                user_id=1, account_id=1, stock_symbol="aapl", quantity=1
            )

        assert result["stock_symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# CHECKPOINT C — sell_stock()
#
# New checks vs buy:
#   - User must own the stock
#   - User must have enough quantity to sell
#   - Holding deleted when quantity hits exactly zero
#   - Credits account (deposit) instead of debiting (withdraw)
#   - Net amount = total_amount - fee (opposite of buy)
# ---------------------------------------------------------------------------

class TestSellStock:

    @pytest.mark.asyncio
    async def test_sell_stock_success_returns_transaction_dict(self):
        """Happy path: user owns stock, sells some → returns transaction info"""
        account = make_fake_account()
        holding = make_fake_holding(quantity=10)
        service, *_ = make_service(account=account, holding=holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            result = await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )

        assert result["stock_symbol"] == "AAPL"
        assert result["quantity"] == 5
        assert result["transaction_type"] == "SELL"
        assert "net_amount" in result

    @pytest.mark.asyncio
    async def test_sell_stock_net_amount_calculation_is_correct(self):
        """
        Net amount = total_amount - fee (seller pays fee, gets less)
        price=180, quantity=5
        total_amount    = 180 * 5  = 900.00
        transaction_fee = 900 * 0.001 = 0.90
        net_amount      = 900 - 0.90  = 899.10
        """
        account = make_fake_account()
        holding = make_fake_holding(quantity=10)
        service, *_ = make_service(account=account, holding=holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            result = await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )

        assert result["total_amount"] == pytest.approx(900.00)
        assert result["transaction_fee"] == pytest.approx(0.90)
        assert result["net_amount"] == pytest.approx(899.10)

    @pytest.mark.asyncio
    async def test_sell_stock_deposits_net_amount_to_account(self):
        """
        account_service.deposit() must be called with net_amount (after fee),
        not total_amount. Seller gets net, not gross.
        """
        account = make_fake_account()
        holding = make_fake_holding(quantity=10)
        service, _, _, _, account_service = make_service(account=account, holding=holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )

        account_service.deposit.assert_called_once()
        call_kwargs = account_service.deposit.call_args.kwargs
        assert call_kwargs["amount"] == pytest.approx(Decimal("899.10"), rel=Decimal("0.001"))

    @pytest.mark.asyncio
    async def test_sell_stock_deletes_holding_when_quantity_reaches_zero(self):
        """
        Selling ALL shares (quantity == holding.quantity) →
        holding_repo.delete() called, not update()
        """
        account = make_fake_account()
        holding = make_fake_holding(quantity=5)  # user has exactly 5
        service, holding_repo, *_ = make_service(account=account, holding=holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")  # sell all 5
            )

        holding_repo.delete.assert_called_once_with(holding.holding_id)
        holding_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_stock_updates_holding_when_quantity_remains(self):
        """
        Selling SOME shares → holding_repo.update() with reduced quantity,
        holding_repo.delete() must NOT be called
        """
        account = make_fake_account()
        holding = make_fake_holding(quantity=10)
        service, holding_repo, *_ = make_service(account=account, holding=holding)

        with patch("app.services.stock.generate_stock_transaction_number", return_value="STK001"):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=3, price=Decimal("180.00")
            )

        holding_repo.update.assert_called_once()
        holding_repo.delete.assert_not_called()

        updated_data = holding_repo.update.call_args[0][1]
        assert updated_data["quantity"] == 7  # 10 - 3

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_user_does_not_own_stock(self):
        """No holding for this symbol → BankingException"""
        account = make_fake_account()
        service, *_ = make_service(account=account, holding=None)  # no holding

        with pytest.raises(BankingException) as exc_info:
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_insufficient_quantity(self):
        """User has 5 shares, tries to sell 10 → BankingException"""
        account = make_fake_account()
        holding = make_fake_holding(quantity=5)
        service, *_ = make_service(account=account, holding=holding)

        with pytest.raises(BankingException) as exc_info:
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=10, price=Decimal("180.00")
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_quantity_zero(self):
        """quantity=0 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=0, price=Decimal("180.00")
            )

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_price_is_zero(self):
        """price=0 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("0")
            )

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_account_not_found(self):
        """No account → AccountNotFoundException"""
        service, *_ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.sell_stock(
                user_id=1, account_id=999, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )

    @pytest.mark.asyncio
    async def test_sell_stock_raises_if_wrong_owner(self):
        """Account belongs to user 2 → AccountNotFoundException"""
        account = make_fake_account(user_id=2)
        service, *_ = make_service(account=account)

        with pytest.raises(AccountNotFoundException):
            await service.sell_stock(
                user_id=1, account_id=1, stock_symbol="AAPL",
                quantity=5, price=Decimal("180.00")
            )


# ---------------------------------------------------------------------------
# CHECKPOINT D — get_portfolio()
#
# Pure calculation method — no writes to DB, just reads + math.
# Focus: profit/loss calculation, percentage, empty portfolio edge case.
# ---------------------------------------------------------------------------

class TestGetPortfolio:

    @pytest.mark.asyncio
    async def test_portfolio_with_no_holdings_returns_zeros(self):
        """User with no stocks → all values zero, empty holdings list"""
        service, holding_repo, *_ = make_service()
        holding_repo.get_by_user = AsyncMock(return_value=[])

        result = await service.get_portfolio(user_id=1)

        assert result["total_invested"] == 0.0
        assert result["current_value"] == 0.0
        assert result["total_profit_loss"] == 0.0
        assert result["total_profit_loss_percentage"] == 0.0
        assert result["holdings"] == []

    @pytest.mark.asyncio
    async def test_portfolio_calculates_profit_correctly(self):
        """
        Bought 10 AAPL at avg 170.00 (invested = 1700)
        Current AAPL price = 175.50 (current = 1755)
        profit_loss = 1755 - 1700 = 55.00
        profit_loss_percentage = 55/1700 * 100 ≈ 3.235%
        """
        holding = make_fake_holding(quantity=10, average_price=Decimal("170.00"))
        holding.stock_symbol = "AAPL"
        service, holding_repo, *_ = make_service()
        holding_repo.get_by_user = AsyncMock(return_value=[holding])

        result = await service.get_portfolio(user_id=1)

        assert result["total_invested"] == pytest.approx(1700.00)
        assert result["current_value"] == pytest.approx(1755.00)
        assert result["total_profit_loss"] == pytest.approx(55.00)
        assert result["total_profit_loss_percentage"] == pytest.approx(3.235, rel=0.01)

    @pytest.mark.asyncio
    async def test_portfolio_calculates_loss_correctly(self):
        """
        Bought 10 MSFT at avg 400.00 (invested = 4000)
        Current MSFT price = 380.75 (current = 3807.50)
        profit_loss = 3807.50 - 4000 = -192.50 (a loss)
        """
        holding = make_fake_holding(
            stock_symbol="MSFT", quantity=10, average_price=Decimal("400.00")
        )
        holding.stock_symbol = "MSFT"
        service, holding_repo, *_ = make_service()
        holding_repo.get_by_user = AsyncMock(return_value=[holding])

        result = await service.get_portfolio(user_id=1)

        assert result["total_profit_loss"] == pytest.approx(-192.50)
        assert result["holdings"][0]["profit_loss"] < 0  # confirms it's a loss

    @pytest.mark.asyncio
    async def test_portfolio_each_holding_has_required_fields(self):
        """Every holding in the response must have these fields"""
        holding = make_fake_holding(quantity=5, average_price=Decimal("170.00"))
        holding.stock_symbol = "AAPL"
        service, holding_repo, *_ = make_service()
        holding_repo.get_by_user = AsyncMock(return_value=[holding])

        result = await service.get_portfolio(user_id=1)

        required = {
            "holding_id", "stock_symbol", "quantity", "average_price",
            "current_price", "invested_value", "current_value",
            "profit_loss", "profit_loss_percentage"
        }
        assert required.issubset(result["holdings"][0].keys())

    @pytest.mark.asyncio
    async def test_portfolio_aggregates_multiple_holdings(self):
        """Two holdings → totals are sum of both"""
        aapl_holding = make_fake_holding(
            holding_id=1, stock_symbol="AAPL",
            quantity=10, average_price=Decimal("170.00")
        )
        aapl_holding.stock_symbol = "AAPL"

        msft_holding = make_fake_holding(
            holding_id=2, stock_symbol="MSFT",
            quantity=5, average_price=Decimal("375.00")
        )
        msft_holding.stock_symbol = "MSFT"

        service, holding_repo, *_ = make_service()
        holding_repo.get_by_user = AsyncMock(return_value=[aapl_holding, msft_holding])

        result = await service.get_portfolio(user_id=1)

        # aapl invested = 1700, msft invested = 1875 → total = 3575
        assert result["total_invested"] == pytest.approx(3575.00)
        assert len(result["holdings"]) == 2


# ---------------------------------------------------------------------------
# CHECKPOINT E — get_stock_transactions() with pagination
# ---------------------------------------------------------------------------

class TestGetStockTransactions:

    @pytest.mark.asyncio
    async def test_returns_list_and_total(self):
        """Returns tuple (transactions, total)"""
        fake_txns = [make_fake_stock_transaction(), make_fake_stock_transaction(transaction_id=202)]
        service, _, stock_txn_repo, *_ = make_service(transactions=fake_txns, total=2)

        result_list, total = await service.get_stock_transactions(user_id=1)

        assert len(result_list) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_pagination_skip_is_calculated_correctly(self):
        """Page 3, page_size=5 → skip = (3-1) * 5 = 10"""
        service, _, stock_txn_repo, *_ = make_service()

        await service.get_stock_transactions(user_id=1, page=3, page_size=5)

        stock_txn_repo.get_by_user.assert_called_once_with(1, skip=10, limit=5)

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty_list(self):
        """No transactions → empty list, total 0"""
        service, *_ = make_service(transactions=[], total=0)

        result_list, total = await service.get_stock_transactions(user_id=1)

        assert result_list == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_each_transaction_has_required_fields(self):
        """Every item in the list must have these keys"""
        fake_txns = [make_fake_stock_transaction()]
        service, _, stock_txn_repo, *_ = make_service(transactions=fake_txns, total=1)

        result_list, _ = await service.get_stock_transactions(user_id=1)

        required = {
            "transaction_id", "transaction_number", "stock_symbol",
            "transaction_type", "quantity", "price",
            "total_amount", "transaction_fee", "status", "timestamp"
        }
        assert required.issubset(result_list[0].keys())