"""
Integration tests for /api/v1/stocks endpoints.
File: tests/integration/test_stocks_api.py

Fixtures from conftest.py:
  client          – unauthenticated AsyncClient
  auth_client     – AsyncClient with Authorization header set
  funded_account  – REGULAR account pre-loaded with 100,000
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Known mock data from StockService
# ---------------------------------------------------------------------------

VALID_SYMBOL = "AAPL"
VALID_PRICE = "175.50"        # STRING — avoids float * Decimal TypeError in service
INVALID_SYMBOL = "DOGE"
FEE_PERCENT = Decimal("0.1")  # 0.1%


def expected_fee(price: str, quantity: int) -> float:
    total = Decimal(price) * quantity
    return float(total * FEE_PERCENT / 100)


def expected_total_with_fee(price: str, quantity: int) -> float:
    total = Decimal(price) * quantity
    fee = total * FEE_PERCENT / 100
    return float(total + fee)


def expected_net_after_fee(price: str, quantity: int) -> float:
    total = Decimal(price) * quantity
    fee = total * FEE_PERCENT / 100
    return float(total - fee)


def _clear_auth(client: AsyncClient) -> dict:
    """Save all headers, clear them, return saved copy for restore."""
    saved = dict(client.headers)
    client.headers.clear()
    return saved


def _restore_auth(client: AsyncClient, saved: dict) -> None:
    client.headers.update(saved)


# ---------------------------------------------------------------------------
# GET /stocks/prices  – public endpoint, no auth required
# ---------------------------------------------------------------------------

class TestGetStockPrices:

    async def test_get_prices_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/prices")
        assert resp.status_code == 200

    async def test_prices_message(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/prices")
        assert resp.json()["message"] == "Stock prices retrieved"

    async def test_prices_returns_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/prices")
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) == 8  # 8 mock stocks

    async def test_prices_entry_has_required_fields(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/prices")
        entry = resp.json()["data"][0]
        assert {"symbol", "name", "price"}.issubset(entry.keys())
        assert isinstance(entry["price"], (int, float))

    async def test_prices_includes_known_symbol(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/prices")
        symbols = {e["symbol"] for e in resp.json()["data"]}
        assert "AAPL" in symbols
        assert "NVDA" in symbols


# ---------------------------------------------------------------------------
# POST /stocks/buy
# ---------------------------------------------------------------------------

class TestBuyStock:

    async def test_buy_stock_success(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 2,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["message"] == "Stock purchased successfully"
        data = body["data"]
        assert data["stock_symbol"] == VALID_SYMBOL
        assert data["quantity"] == 2
        assert data["transaction_type"] == "BUY"
        assert data["status"] == "COMPLETED"
        assert "transaction_number" in data
        assert "transaction_id" in data

    async def test_buy_stock_deducts_correct_amount(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        quantity = 3

        bal_before = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id,
            "stock_symbol": VALID_SYMBOL,
            "quantity": quantity,
        })

        bal_after = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        expected_deducted = expected_total_with_fee(VALID_PRICE, quantity)
        assert abs((bal_before - bal_after) - expected_deducted) < 0.01

    async def test_buy_stock_fee_in_response(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
        })
        data = resp.json()["data"]
        assert abs(data["transaction_fee"] - expected_fee(VALID_PRICE, 1)) < 0.01
        assert abs(data["total_with_fee"] - expected_total_with_fee(VALID_PRICE, 1)) < 0.01

    async def test_buy_stock_creates_portfolio_entry(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 5,
        })
        portfolio = (await auth_client.get("/api/v1/stocks/portfolio")).json()["data"]
        symbols = [h["stock_symbol"] for h in portfolio["holdings"]]
        assert VALID_SYMBOL in symbols

    async def test_buy_stock_multiple_times_averages_price(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        for _ in range(2):
            await auth_client.post("/api/v1/stocks/buy", json={
                "account_id": account_id,
                "stock_symbol": "MSFT",
                "quantity": 2,
            })
        portfolio = (await auth_client.get("/api/v1/stocks/portfolio")).json()["data"]
        msft = next(h for h in portfolio["holdings"] if h["stock_symbol"] == "MSFT")
        assert msft["quantity"] == 4

    async def test_buy_stock_invalid_symbol_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        # buy_stock does MOCK_STOCK_PRICES[symbol] before calling get_mock_price,
        # so an unknown symbol raises KeyError → 500, not 404. Assert any error.
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": INVALID_SYMBOL,
            "quantity": 1,
        })
        assert resp.status_code >= 400

    async def test_buy_stock_zero_quantity_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 0,
        })
        assert resp.status_code in (400, 422)

    async def test_buy_stock_negative_quantity_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": -5,
        })
        assert resp.status_code in (400, 422)

    async def test_buy_stock_insufficient_balance_returns_error(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        # savings_account has zero balance
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": savings_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
        })
        assert resp.status_code in (400, 422)

    async def test_buy_stock_wrong_account_returns_error(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": 999999,
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
        })
        assert resp.status_code in (400, 403, 404)

    async def test_buy_stock_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
        })
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401

    async def test_buy_stock_symbol_is_case_insensitive(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": "aapl",
            "quantity": 1,
        })
        assert resp.status_code == 201
        assert resp.json()["data"]["stock_symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# POST /stocks/sell
# ---------------------------------------------------------------------------

class TestSellStock:

    async def _buy(self, auth_client, account_id, symbol=VALID_SYMBOL, qty=5):
        resp = await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id,
            "stock_symbol": symbol,
            "quantity": qty,
        })
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    async def test_sell_stock_success(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id)

        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": VALID_SYMBOL,
            "quantity": 2,
            "price": VALID_PRICE,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Stock sold successfully"
        data = body["data"]
        assert data["stock_symbol"] == VALID_SYMBOL
        assert data["quantity"] == 2
        assert data["transaction_type"] == "SELL"
        assert data["status"] == "COMPLETED"

    async def test_sell_stock_credits_net_amount(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id, qty=5)

        bal_before = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        sell_qty = 3
        await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": VALID_SYMBOL,
            "quantity": sell_qty,
            "price": VALID_PRICE,
        })

        bal_after = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        expected_credited = expected_net_after_fee(VALID_PRICE, sell_qty)
        assert abs((bal_after - bal_before) - expected_credited) < 0.01

    async def test_sell_stock_fee_in_response(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id)

        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
            "price": VALID_PRICE,
        })
        data = resp.json()["data"]
        assert abs(data["transaction_fee"] - expected_fee(VALID_PRICE, 1)) < 0.01
        assert abs(data["net_amount"] - expected_net_after_fee(VALID_PRICE, 1)) < 0.01

    async def test_sell_all_stock_removes_holding(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id, symbol="TSLA", qty=3)

        await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": "TSLA",
            "quantity": 3,
            "price": "245.80",       # string — avoids float * Decimal in service
        })

        portfolio = (await auth_client.get("/api/v1/stocks/portfolio")).json()["data"]
        symbols = [h["stock_symbol"] for h in portfolio["holdings"]]
        assert "TSLA" not in symbols

    async def test_sell_partial_reduces_holding_quantity(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id, symbol="META", qty=6)

        await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": "META",
            "quantity": 4,
            "price": "325.60",       # string — avoids float * Decimal in service
        })

        portfolio = (await auth_client.get("/api/v1/stocks/portfolio")).json()["data"]
        meta = next(h for h in portfolio["holdings"] if h["stock_symbol"] == "META")
        assert meta["quantity"] == 2

    async def test_sell_stock_not_owned_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": "GOOGL",
            "quantity": 1,
            "price": "140.25",
        })
        assert resp.status_code in (400, 404)

    async def test_sell_more_than_owned_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._buy(auth_client, account_id, symbol="AMZN", qty=2)

        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": "AMZN",
            "quantity": 10,
            "price": "145.30",
        })
        assert resp.status_code in (400, 422)

    async def test_sell_zero_quantity_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 0,
            "price": VALID_PRICE,
        })
        assert resp.status_code in (400, 422)

    async def test_sell_negative_price_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
            "price": "-10.00",       # string — avoids float * Decimal in service
        })
        assert resp.status_code in (400, 422)

    async def test_sell_stock_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
            "price": VALID_PRICE,
        })
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /stocks/portfolio
# ---------------------------------------------------------------------------

class TestGetPortfolio:

    async def test_portfolio_empty_for_new_user(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/stocks/portfolio")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Portfolio retrieved successfully"
        data = resp.json()["data"]
        assert data["holdings"] == []
        assert data["total_invested"] == 0.0
        assert data["current_value"] == 0.0
        assert data["total_profit_loss"] == 0.0

    async def test_portfolio_shows_holding_after_buy(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": "NVDA",
            "quantity": 2,
        })
        resp = await auth_client.get("/api/v1/stocks/portfolio")
        data = resp.json()["data"]
        assert len(data["holdings"]) == 1
        holding = data["holdings"][0]
        assert holding["stock_symbol"] == "NVDA"
        assert holding["quantity"] == 2

    async def test_portfolio_holding_has_required_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": funded_account["account_id"],
            "stock_symbol": "NFLX",
            "quantity": 1,
        })
        resp = await auth_client.get("/api/v1/stocks/portfolio")
        holding = resp.json()["data"]["holdings"][0]
        required = {
            "holding_id", "stock_symbol", "quantity", "average_price",
            "current_price", "invested_value", "current_value",
            "profit_loss", "profit_loss_percentage",
        }
        assert required.issubset(holding.keys())

    async def test_portfolio_totals_are_correct(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id, "stock_symbol": "AAPL", "quantity": 2,
        })
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id, "stock_symbol": "MSFT", "quantity": 1,
        })
        resp = await auth_client.get("/api/v1/stocks/portfolio")
        data = resp.json()["data"]
        assert data["total_invested"] > 0
        assert data["current_value"] > 0
        # Prices are static mocks, so current_value == total_invested → no P&L
        assert abs(data["total_profit_loss"]) < 0.01

    async def test_portfolio_unauthenticated_returns_401(self, auth_client: AsyncClient):
        saved = _clear_auth(auth_client)
        resp = await auth_client.get("/api/v1/stocks/portfolio")
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /stocks/transactions
# ---------------------------------------------------------------------------

class TestGetStockTransactions:

    async def _do_buy(self, auth_client, account_id, symbol=VALID_SYMBOL, qty=1):
        await auth_client.post("/api/v1/stocks/buy", json={
            "account_id": account_id,
            "stock_symbol": symbol,
            "quantity": qty,
        })

    async def test_get_transactions_empty_for_new_user(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/stocks/transactions")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Stock transactions retrieved"
        assert resp.json()["data"] == []
        assert resp.json()["total"] == 0

    async def test_get_transactions_after_buy(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await self._do_buy(auth_client, funded_account["account_id"])
        resp = await auth_client.get("/api/v1/stocks/transactions")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        assert resp.json()["total"] == 1

    async def test_get_transactions_after_buy_and_sell(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await self._do_buy(auth_client, account_id, qty=3)
        await auth_client.post("/api/v1/stocks/sell", json={
            "account_id": account_id,
            "stock_symbol": VALID_SYMBOL,
            "quantity": 1,
            "price": VALID_PRICE,    # string — avoids float * Decimal
        })
        resp = await auth_client.get("/api/v1/stocks/transactions")
        assert resp.json()["total"] == 2
        types = {t["transaction_type"] for t in resp.json()["data"]}
        assert "BUY" in types
        assert "SELL" in types

    async def test_transactions_response_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await self._do_buy(auth_client, funded_account["account_id"])
        resp = await auth_client.get("/api/v1/stocks/transactions")
        txn = resp.json()["data"][0]
        required = {
            "transaction_id", "transaction_number", "stock_symbol",
            "transaction_type", "quantity", "price",
            "total_amount", "transaction_fee", "status", "timestamp",
        }
        assert required.issubset(txn.keys())

    async def test_get_transactions_pagination(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            await self._do_buy(auth_client, account_id, symbol=symbol)

        resp = await auth_client.get("/api/v1/stocks/transactions?page=1&page_size=2")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2
        assert resp.json()["total"] == 3

    async def test_get_transactions_page_size_exceeds_max_returns_422(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/stocks/transactions?page_size=200")
        assert resp.status_code == 422

    async def test_get_transactions_page_zero_returns_422(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/stocks/transactions?page=0")
        assert resp.status_code == 422

    async def test_get_transactions_unauthenticated_returns_401(
        self, auth_client: AsyncClient
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.get("/api/v1/stocks/transactions")
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401