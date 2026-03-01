"""
Unit Tests for DashboardService (app/services/dashboard.py)

Run with:
    pytest tests/unit/services/test_dashboard_service.py -v

WHAT'S NEW vs previous tests:
    1. DashboardService has FIVE dependencies — most complex setup so far
    2. stock_service is a full service mock (not a repo) — same pattern as before
    3. get_dashboard_summary() aggregates data from ALL repos in one call
       so we need to think about combinations: 0 accounts, 3 accounts, etc.
    4. Transaction loop — service iterates over accounts[:3], fetches 5
       transactions per account. We test the slicing/sorting behavior.
    5. No write operations — this service is READ-ONLY, so no withdraw/deposit
       assertions needed, just shape and math checks.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.dashboard import DashboardService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_account(
    account_id=1,
    account_number="ACC001",
    balance=Decimal("10000.00"),
    account_type="savings",
    status="active",
):
    acc = MagicMock()
    acc.account_id = account_id
    acc.account_number = account_number
    acc.balance = balance
    acc.account_type.value = account_type   # MagicMock attr — safe to set .value
    acc.status.value = status               # MagicMock attr — safe to set .value
    return acc


def make_fake_fd(
    fd_id=1,
    fd_number="FD001",
    principal_amount=Decimal("20000.00"),
    maturity_amount=Decimal("21300.00"),
    maturity_date="2025-06-01",
    interest_rate=Decimal("6.5"),
):
    fd = MagicMock()
    fd.fd_id = fd_id
    fd.fd_number = fd_number
    fd.principal_amount = principal_amount
    fd.maturity_amount = maturity_amount
    fd.maturity_date = maturity_date
    fd.interest_rate = interest_rate
    return fd


def make_fake_transaction(
    transaction_id=1,
    transaction_number="TXN001",
    amount=Decimal("500.00"),
    balance_after=Decimal("9500.00"),
    description="Test transaction",
    created_at="2024-06-01T10:00:00",
    transaction_type="deposit",
):
    txn = MagicMock()
    txn.transaction_id = transaction_id
    txn.transaction_number = transaction_number
    txn.amount = amount
    txn.balance_after = balance_after
    txn.description = description
    txn.created_at = created_at
    txn.transaction_type.value = transaction_type   # MagicMock attr — safe
    return txn


def make_mock_stock_service(portfolio=None):
    """
    stock_service.get_portfolio() is the only method DashboardService calls.
    Default portfolio has zero holdings so we can override per test.
    """
    svc = MagicMock()
    svc.get_portfolio = AsyncMock(return_value=portfolio or {
        "current_value": 0.0,
        "total_profit_loss": 0.0,
        "holdings": [],
    })
    return svc


def make_service(
    accounts=None,
    active_fds_count=0,
    total_fd_amount=0.0,
    active_fds=None,
    transactions_per_account=None,
    portfolio=None,
):
    """
    Build DashboardService with all 5 dependencies mocked.

    transactions_per_account: list of transactions returned for EVERY
    account.get_by_account call (same list reused for simplicity).
    """
    account_repo = MagicMock()
    account_repo.get_by_user = AsyncMock(return_value=accounts or [])

    fd_repo = MagicMock()
    fd_repo.get_active_fds_count = AsyncMock(return_value=active_fds_count)
    fd_repo.get_total_fd_amount = AsyncMock(return_value=total_fd_amount)
    fd_repo.get_active_by_user = AsyncMock(return_value=active_fds or [])

    transaction_repo = MagicMock()
    transaction_repo.get_by_account = AsyncMock(
        return_value=transactions_per_account or []
    )

    holding_repo = MagicMock()   # not used directly — stock_service wraps it

    stock_service = make_mock_stock_service(portfolio=portfolio)

    service = DashboardService(
        account_repo=account_repo,
        fd_repo=fd_repo,
        holding_repo=holding_repo,
        transaction_repo=transaction_repo,
        stock_service=stock_service,
    )
    return service, account_repo, fd_repo, transaction_repo, stock_service


# ---------------------------------------------------------------------------
# CHECKPOINT A — Response shape
# Always verify the top-level keys first before testing values.
# If the shape is wrong, every downstream test is meaningless.
# ---------------------------------------------------------------------------

class TestDashboardResponseShape:

    @pytest.mark.asyncio
    async def test_response_has_all_top_level_keys(self):
        """
        get_dashboard_summary must always return these 5 top-level keys
        regardless of data. Shape should never silently change.
        """
        service, *_ = make_service()
        result = await service.get_dashboard_summary(user_id=1)

        assert "summary" in result
        assert "accounts" in result
        assert "active_fds" in result
        assert "stock_portfolio" in result
        assert "recent_transactions" in result

    @pytest.mark.asyncio
    async def test_summary_block_has_all_required_fields(self):
        """summary sub-dict must have all 6 financial fields"""
        service, *_ = make_service()
        result = await service.get_dashboard_summary(user_id=1)

        required = {
            "total_balance", "total_fds", "total_fd_amount",
            "total_stock_value", "stock_profit_loss", "overall_portfolio_value"
        }
        assert required.issubset(result["summary"].keys())

    @pytest.mark.asyncio
    async def test_stock_portfolio_block_has_required_fields(self):
        """stock_portfolio sub-dict must have these 3 fields"""
        service, *_ = make_service()
        result = await service.get_dashboard_summary(user_id=1)

        required = {"current_value", "total_profit_loss", "holdings_count"}
        assert required.issubset(result["stock_portfolio"].keys())

    @pytest.mark.asyncio
    async def test_each_account_in_summary_has_required_fields(self):
        """Every account in accounts list must have these fields"""
        accounts = [make_fake_account()]
        service, *_ = make_service(accounts=accounts)

        result = await service.get_dashboard_summary(user_id=1)

        required = {"account_id", "account_number", "account_type", "balance", "status"}
        assert required.issubset(result["accounts"][0].keys())

    @pytest.mark.asyncio
    async def test_each_fd_in_summary_has_required_fields(self):
        """Every FD in active_fds list must have these fields"""
        active_fds = [make_fake_fd()]
        service, *_ = make_service(active_fds=active_fds)

        result = await service.get_dashboard_summary(user_id=1)

        required = {
            "fd_id", "fd_number", "principal_amount",
            "maturity_amount", "maturity_date", "interest_rate"
        }
        assert required.issubset(result["active_fds"][0].keys())

    @pytest.mark.asyncio
    async def test_each_transaction_in_summary_has_required_fields(self):
        """Every transaction in recent_transactions must have these fields"""
        accounts = [make_fake_account()]
        txns = [make_fake_transaction()]
        service, *_ = make_service(accounts=accounts, transactions_per_account=txns)

        result = await service.get_dashboard_summary(user_id=1)

        required = {
            "transaction_id", "transaction_number", "account_number",
            "type", "amount", "balance_after", "description", "timestamp"
        }
        assert required.issubset(result["recent_transactions"][0].keys())


# ---------------------------------------------------------------------------
# CHECKPOINT B — summary math
# ---------------------------------------------------------------------------

class TestDashboardSummaryMath:

    @pytest.mark.asyncio
    async def test_total_balance_is_sum_of_all_account_balances(self):
        """
        3 accounts with balances 10000, 5000, 3000
        total_balance = 18000.0
        """
        accounts = [
            make_fake_account(account_id=1, balance=Decimal("10000.00")),
            make_fake_account(account_id=2, balance=Decimal("5000.00")),
            make_fake_account(account_id=3, balance=Decimal("3000.00")),
        ]
        service, *_ = make_service(accounts=accounts)

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_balance"] == pytest.approx(18000.0)

    @pytest.mark.asyncio
    async def test_overall_portfolio_value_is_sum_of_all_assets(self):
        """
        overall = total_balance + total_fd_amount + total_stock_value
        = 10000 + 20000 + 5000 = 35000
        """
        accounts = [make_fake_account(balance=Decimal("10000.00"))]
        portfolio = {"current_value": 5000.0, "total_profit_loss": 500.0, "holdings": [MagicMock()]}
        service, *_ = make_service(
            accounts=accounts,
            total_fd_amount=20000.0,
            portfolio=portfolio,
        )

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["overall_portfolio_value"] == pytest.approx(35000.0)

    @pytest.mark.asyncio
    async def test_stock_values_come_from_stock_service_portfolio(self):
        """
        total_stock_value and stock_profit_loss must reflect
        exactly what stock_service.get_portfolio() returned.
        """
        portfolio = {
            "current_value": 12500.0,
            "total_profit_loss": -300.0,
            "holdings": [MagicMock(), MagicMock()],
        }
        service, *_ = make_service(portfolio=portfolio)

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_stock_value"] == 12500.0
        assert result["summary"]["stock_profit_loss"] == -300.0
        assert result["stock_portfolio"]["holdings_count"] == 2

    @pytest.mark.asyncio
    async def test_total_fds_count_comes_from_fd_repo(self):
        """total_fds must reflect what fd_repo.get_active_fds_count() returned"""
        service, *_ = make_service(active_fds_count=4, total_fd_amount=80000.0)

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_fds"] == 4
        assert result["summary"]["total_fd_amount"] == 80000.0


# ---------------------------------------------------------------------------
# CHECKPOINT C — empty / zero states
# ---------------------------------------------------------------------------

class TestDashboardEmptyStates:

    @pytest.mark.asyncio
    async def test_user_with_no_accounts_returns_zero_balance(self):
        """No accounts → total_balance=0, accounts=[], recent_transactions=[]"""
        service, *_ = make_service(accounts=[])

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_balance"] == 0.0
        assert result["accounts"] == []
        assert result["recent_transactions"] == []

    @pytest.mark.asyncio
    async def test_user_with_no_fds_returns_zero_fd_fields(self):
        """No FDs → total_fds=0, total_fd_amount=0, active_fds=[]"""
        service, *_ = make_service(active_fds_count=0, total_fd_amount=0.0, active_fds=[])

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_fds"] == 0
        assert result["summary"]["total_fd_amount"] == 0.0
        assert result["active_fds"] == []

    @pytest.mark.asyncio
    async def test_user_with_no_stocks_returns_zero_stock_fields(self):
        """No stocks → current_value=0, profit_loss=0, holdings_count=0"""
        portfolio = {"current_value": 0.0, "total_profit_loss": 0.0, "holdings": []}
        service, *_ = make_service(portfolio=portfolio)

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["total_stock_value"] == 0.0
        assert result["summary"]["stock_profit_loss"] == 0.0
        assert result["stock_portfolio"]["holdings_count"] == 0

    @pytest.mark.asyncio
    async def test_overall_portfolio_value_is_zero_when_everything_empty(self):
        """No accounts, no FDs, no stocks → overall_portfolio_value = 0"""
        service, *_ = make_service(
            accounts=[], active_fds_count=0,
            total_fd_amount=0.0,
            portfolio={"current_value": 0.0, "total_profit_loss": 0.0, "holdings": []}
        )

        result = await service.get_dashboard_summary(user_id=1)

        assert result["summary"]["overall_portfolio_value"] == 0.0


# ---------------------------------------------------------------------------
# CHECKPOINT D — transaction fetching logic
# ---------------------------------------------------------------------------

class TestDashboardTransactionLogic:

    @pytest.mark.asyncio
    async def test_transactions_fetched_for_each_account_up_to_3(self):
        """
        Service only fetches transactions for accounts[:3].
        With 4 accounts, transaction_repo.get_by_account must be called 3 times,
        not 4.
        """
        accounts = [make_fake_account(account_id=i) for i in range(1, 5)]  # 4 accounts
        service, _, _, transaction_repo, _ = make_service(accounts=accounts)

        await service.get_dashboard_summary(user_id=1)

        # Called for account 1, 2, 3 only — not account 4
        assert transaction_repo.get_by_account.call_count == 3

    @pytest.mark.asyncio
    async def test_transactions_fetched_with_limit_5_per_account(self):
        """Each account's transactions are fetched with skip=0, limit=5"""
        accounts = [make_fake_account(account_id=1)]
        service, _, _, transaction_repo, _ = make_service(accounts=accounts)

        await service.get_dashboard_summary(user_id=1)

        transaction_repo.get_by_account.assert_called_once_with(1, skip=0, limit=5)

    @pytest.mark.asyncio
    async def test_recent_transactions_capped_at_10(self):
        """
        3 accounts × 5 transactions = 15 raw transactions.
        After slicing, only 10 must be returned.
        """
        accounts = [make_fake_account(account_id=i) for i in range(1, 4)]
        # 5 transactions per account, each with unique timestamp for sorting
        txns = [
            make_fake_transaction(
                transaction_id=i,
                created_at=f"2024-06-{i:02d}T10:00:00"
            )
            for i in range(1, 6)
        ]
        service, *_ = make_service(accounts=accounts, transactions_per_account=txns)

        result = await service.get_dashboard_summary(user_id=1)

        assert len(result["recent_transactions"]) == 10

    @pytest.mark.asyncio
    async def test_recent_transactions_sorted_newest_first(self):
        """
        Transactions must be sorted by timestamp descending (newest first).
        """
        accounts = [make_fake_account(account_id=1)]
        txns = [
            make_fake_transaction(transaction_id=1, created_at="2024-01-01T10:00:00"),
            make_fake_transaction(transaction_id=2, created_at="2024-06-01T10:00:00"),
            make_fake_transaction(transaction_id=3, created_at="2024-03-15T10:00:00"),
        ]
        service, *_ = make_service(accounts=accounts, transactions_per_account=txns)

        result = await service.get_dashboard_summary(user_id=1)
        timestamps = [t["timestamp"] for t in result["recent_transactions"]]

        # Each timestamp must be >= the one after it
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_transactions_include_account_number(self):
        """
        Each transaction in the response must include the account_number
        from the account it came from (joined in Python, not DB).
        """
        accounts = [make_fake_account(account_id=1, account_number="ACC999")]
        txns = [make_fake_transaction()]
        service, *_ = make_service(accounts=accounts, transactions_per_account=txns)

        result = await service.get_dashboard_summary(user_id=1)

        assert result["recent_transactions"][0]["account_number"] == "ACC999"


# ---------------------------------------------------------------------------
# CHECKPOINT E — FD list capped at 5
# ---------------------------------------------------------------------------

class TestDashboardFDLimit:

    @pytest.mark.asyncio
    async def test_active_fds_capped_at_5_for_dashboard(self):
        """
        Even if user has 8 active FDs, dashboard only shows 5.
        This is the active_fds[:5] slice in the service.
        """
        active_fds = [make_fake_fd(fd_id=i, fd_number=f"FD00{i}") for i in range(1, 9)]
        service, *_ = make_service(active_fds=active_fds)

        result = await service.get_dashboard_summary(user_id=1)

        assert len(result["active_fds"]) == 5

    @pytest.mark.asyncio
    async def test_active_fds_fewer_than_5_returns_all(self):
        """If user has 3 FDs, all 3 are shown (no unnecessary truncation)"""
        active_fds = [make_fake_fd(fd_id=i) for i in range(1, 4)]
        service, *_ = make_service(active_fds=active_fds)

        result = await service.get_dashboard_summary(user_id=1)

        assert len(result["active_fds"]) == 3