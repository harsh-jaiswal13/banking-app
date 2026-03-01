"""
Integration tests for /api/v1/dashboard endpoint.
File: tests/integration/test_dashboard_api.py

The single dashboard route aggregates:
  - Total savings-account balance
  - Active FD count + total FD amount
  - Stock portfolio value + profit/loss
  - Recent transaction list
  - Accounts summary
  - Active FDs summary
  - Stock portfolio summary

Fixtures from conftest.py:
  client          – unauthenticated AsyncClient
  auth_client     – AsyncClient with Authorization header set
  savings_account – REGULAR account (zero balance) for the authenticated user
  funded_account  – REGULAR account pre-loaded with 100,000
"""

import pytest
from httpx import AsyncClient


STOCK_SYMBOL  = "AAPL"
STOCK_QTY     = 10
FD_AMOUNT     = "5000.00"
FD_TENURE     = 12


# ---------------------------------------------------------------------------
# Auth helpers (same pattern used in other integration tests)
# ---------------------------------------------------------------------------

def _clear_auth(client: AsyncClient) -> dict:
    saved: dict = {}
    token = client.headers.get("authorization")
    if token:
        saved["authorization"] = token
        del client.headers["authorization"]
    for name in ("access_token", "refresh_token"):
        value = client.cookies.get(name)
        if value:
            saved[f"cookie_{name}"] = value
            del client.cookies[name]
    return saved


def _restore_auth(client: AsyncClient, saved: dict) -> None:
    if "authorization" in saved:
        client.headers["Authorization"] = saved["authorization"]
    for name in ("access_token", "refresh_token"):
        key = f"cookie_{name}"
        if key in saved:
            client.cookies.set(name, saved[key])


# ===========================================================================
# GET /api/v1/dashboard
# ===========================================================================

class TestGetDashboard:

    # ------------------------------------------------------------------ #
    # Basic structure                                                      #
    # ------------------------------------------------------------------ #

    async def test_dashboard_returns_200(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.status_code == 200

    async def test_dashboard_success_flag(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        body = resp.json()
        assert body.get("success") is True

    async def test_dashboard_message(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.json()["message"] == "Dashboard data retrieved successfully"

    async def test_dashboard_top_level_keys(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        data = resp.json()["data"]
        expected = {"summary", "accounts", "active_fds", "stock_portfolio", "recent_transactions"}
        assert expected.issubset(data.keys())

    # ------------------------------------------------------------------ #
    # Summary sub-object                                                   #
    # ------------------------------------------------------------------ #

    async def test_summary_keys(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        summary = resp.json()["data"]["summary"]
        required = {
            "total_balance",
            "total_fds",
            "total_fd_amount",
            "total_stock_value",
            "stock_profit_loss",
            "overall_portfolio_value",
        }
        assert required.issubset(summary.keys())

    async def test_summary_zeros_for_fresh_user(self, auth_client: AsyncClient):
        """A brand-new user (no accounts, FDs or stocks) should have all-zero totals."""
        resp = await auth_client.get("/api/v1/dashboard")
        s = resp.json()["data"]["summary"]
        assert s["total_balance"]           == 0.0
        assert s["total_fds"]               == 0
        assert s["total_fd_amount"]         == 0.0
        assert s["total_stock_value"]       == 0.0
        assert s["stock_profit_loss"]       == 0.0
        assert s["overall_portfolio_value"] == 0.0

    async def test_summary_reflects_savings_balance(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """After depositing, total_balance must equal the account balance."""
        acc_id = funded_account["account_id"]
        # Check current balance via account endpoint
        bal_resp = await auth_client.get(f"/api/v1/accounts/{acc_id}/balance")
        expected_balance = bal_resp.json()["data"]["balance"]

        dash = await auth_client.get("/api/v1/dashboard")
        s = dash.json()["data"]["summary"]
        assert abs(s["total_balance"] - expected_balance) < 0.01

    async def test_summary_reflects_active_fd(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """Creating one FD should increment total_fds to 1 and populate total_fd_amount."""
        await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": FD_AMOUNT,
            "tenure_months": FD_TENURE,
        })
        dash = await auth_client.get("/api/v1/dashboard")
        s = dash.json()["data"]["summary"]
        assert s["total_fds"] == 1
        assert s["total_fd_amount"] >= float(FD_AMOUNT)   # includes interest

    async def test_summary_reflects_stock_value(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """After buying stocks the stock portfolio value should be > 0."""
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": STOCK_SYMBOL,
            "quantity": STOCK_QTY,
        })
        dash = await auth_client.get("/api/v1/dashboard")
        s = dash.json()["data"]["summary"]
        assert s["total_stock_value"] > 0.0

    async def test_overall_portfolio_is_sum(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """overall_portfolio_value ≈ total_balance + total_fd_amount + total_stock_value."""
        # Create an FD and buy stocks so all three components are non-zero
        account_id = funded_account["account_id"]
        await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": account_id,
            "amount": FD_AMOUNT,
            "tenure_months": FD_TENURE,
        })
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id,
            "stock_symbol": STOCK_SYMBOL,
            "quantity": 5,
        })
        dash = await auth_client.get("/api/v1/dashboard")
        s = dash.json()["data"]["summary"]
        expected = s["total_balance"] + s["total_fd_amount"] + s["total_stock_value"]
        assert abs(s["overall_portfolio_value"] - expected) < 0.01

    # ------------------------------------------------------------------ #
    # Accounts section                                                     #
    # ------------------------------------------------------------------ #

    async def test_accounts_list_is_empty_for_fresh_user(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.json()["data"]["accounts"] == []

    async def test_accounts_list_contains_funded_account(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        accounts = resp.json()["data"]["accounts"]
        ids = [a["account_id"] for a in accounts]
        assert funded_account["account_id"] in ids

    async def test_accounts_list_entry_has_required_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        account = resp.json()["data"]["accounts"][0]
        for field in ("account_id", "account_number", "account_type", "balance", "status"):
            assert field in account

    # ------------------------------------------------------------------ #
    # Active FDs section                                                   #
    # ------------------------------------------------------------------ #

    async def test_active_fds_empty_for_fresh_user(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.json()["data"]["active_fds"] == []

    async def test_active_fds_shows_created_fd(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": FD_AMOUNT,
            "tenure_months": FD_TENURE,
        })
        resp = await auth_client.get("/api/v1/dashboard")
        active_fds = resp.json()["data"]["active_fds"]
        assert len(active_fds) == 1

    async def test_active_fds_entry_has_required_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": FD_AMOUNT,
            "tenure_months": FD_TENURE,
        })
        resp = await auth_client.get("/api/v1/dashboard")
        fd = resp.json()["data"]["active_fds"][0]
        for field in ("fd_id", "fd_number", "principal_amount", "maturity_amount",
                      "maturity_date", "interest_rate"):
            assert field in fd

    async def test_active_fds_limited_to_five(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """Dashboard shows at most 5 active FDs."""
        account_id = funded_account["account_id"]
        for i in range(7):
            r = await auth_client.post("/api/v1/fixed-deposits", json={
                "account_id": account_id,
                "amount": "1000.00",
                "tenure_months": 6,
            })
            if r.status_code != 201:
                break   # stop if balance runs out
        resp = await auth_client.get("/api/v1/dashboard")
        assert len(resp.json()["data"]["active_fds"]) <= 5

    # ------------------------------------------------------------------ #
    # Stock portfolio section                                              #
    # ------------------------------------------------------------------ #

    async def test_stock_portfolio_keys(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/dashboard")
        sp = resp.json()["data"]["stock_portfolio"]
        for key in ("current_value", "total_profit_loss", "holdings_count"):
            assert key in sp

    async def test_stock_portfolio_zero_for_fresh_user(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        sp = resp.json()["data"]["stock_portfolio"]
        assert sp["current_value"]   == 0.0
        assert sp["holdings_count"]  == 0

    async def test_stock_portfolio_updates_after_buy(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": STOCK_SYMBOL,
            "quantity": STOCK_QTY,
        })
        resp = await auth_client.get("/api/v1/dashboard")
        sp = resp.json()["data"]["stock_portfolio"]
        assert sp["holdings_count"] == 1
        assert sp["current_value"]  > 0.0

    # ------------------------------------------------------------------ #
    # Recent transactions section                                          #
    # ------------------------------------------------------------------ #

    async def test_recent_transactions_empty_for_fresh_user(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        assert resp.json()["data"]["recent_transactions"] == []

    async def test_recent_transactions_after_deposit(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """funded_account fixture deposits money — at least one transaction should appear."""
        resp = await auth_client.get("/api/v1/dashboard")
        txns = resp.json()["data"]["recent_transactions"]
        assert len(txns) >= 1

    async def test_recent_transactions_max_ten(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        # Make 12 deposits so there are more transactions than the 10-item cap
        for _ in range(12):
            await auth_client.post(f"/api/v1/accounts/{account_id}/deposit", json={
                "amount": "100.00",
                "description": "Bulk deposit",
            })
        resp = await auth_client.get("/api/v1/dashboard")
        txns = resp.json()["data"]["recent_transactions"]
        assert len(txns) <= 10

    async def test_recent_transactions_entry_has_required_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.get("/api/v1/dashboard")
        txn = resp.json()["data"]["recent_transactions"][0]
        for field in ("transaction_id", "transaction_number", "type", "amount",
                      "balance_after", "description", "timestamp"):
            assert field in txn

    # ------------------------------------------------------------------ #
    # Auth guard                                                           #
    # ------------------------------------------------------------------ #

    async def test_dashboard_unauthenticated_returns_401(
        self, auth_client: AsyncClient
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.get("/api/v1/dashboard")
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401

    async def test_dashboard_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        resp = await client.get(
            "/api/v1/dashboard",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert resp.status_code == 401
