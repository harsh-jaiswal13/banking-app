"""
Integration tests for /api/v1/accounts endpoints.
File: tests/integration/test_accounts_api.py

Fixtures provided by conftest.py:
  client          – unauthenticated AsyncClient
  auth_client     – AsyncClient with Authorization header set
  savings_account – REGULAR account belonging to auth_client's user
  funded_account  – savings_account pre-loaded with 100 000
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_login(client: AsyncClient, email: str) -> str:
    """Register a second user and return their bearer token."""
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "SecurePass1!",
        "full_name": "Other User",
        "phone": "9000000001",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "SecurePass1!",
    })
    data = resp.json()
    if "data" in data and isinstance(data["data"], dict):
        return data["data"]["access_token"]
    return data["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /accounts  – create account
# ---------------------------------------------------------------------------

class TestCreateAccount:

    async def test_create_regular_account_returns_201(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/accounts", json={"account_type": "REGULAR"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["message"] == "Account created successfully"
        account = body["data"]
        assert account["account_type"] == "REGULAR"
        assert account["status"] == "ACTIVE"
        assert float(account["balance"]) == 0.0
        assert "account_number" in account
        assert "account_id" in account

    @pytest.mark.parametrize("account_type", ["SALARY", "PREMIUM"])
    async def test_create_account_valid_types(
        self, auth_client: AsyncClient, account_type: str
    ):
        resp = await auth_client.post(
            "/api/v1/accounts", json={"account_type": account_type}
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["account_type"] == account_type

    async def test_create_account_defaults_to_regular(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/accounts", json={})
        assert resp.status_code == 201
        assert resp.json()["data"]["account_type"] == "REGULAR"

    async def test_create_account_invalid_type_returns_422(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/v1/accounts", json={"account_type": "UNKNOWN"}
        )
        assert resp.status_code == 422

    async def test_create_account_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/accounts", json={"account_type": "REGULAR"})
        assert resp.status_code == 401

    async def test_created_account_has_interest_rate_field(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/accounts", json={"account_type": "REGULAR"})
        account = resp.json()["data"]
        assert "interest_rate" in account
        assert isinstance(account["interest_rate"], (int, float))


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}  – get account details
# ---------------------------------------------------------------------------

class TestGetAccount:

    async def test_get_own_account_returns_200(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["account_id"] == account_id
        assert data["account_number"] == savings_account["account_number"]

    async def test_get_nonexistent_account_returns_404(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/accounts/999999")
        assert resp.status_code == 404

    async def test_get_account_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/accounts/1")
        assert resp.status_code == 401

    async def test_get_another_users_account_is_forbidden(
        self, client: AsyncClient, savings_account: dict
    ):
        other_token = await _register_login(client, "spy_get@example.com")
        account_id = savings_account["account_id"]
        resp = await client.get(
            f"/api/v1/accounts/{account_id}", headers=_bearer(other_token)
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# POST /accounts/{account_id}/deposit
# ---------------------------------------------------------------------------

class TestDeposit:

    async def test_deposit_success(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        resp = await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "500.00", "description": "Salary"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Deposit successful"
        txn = resp.json()["data"]
        assert float(txn["balance_after"]) == 500.00
        # txn_type = txn.get("type") or txn.get("transaction_type")
        # assert txn_type in ("WITHDRAWAL", "DEPOSIT")

    async def test_deposit_accumulates_correctly(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        for amount in ["100.00", "250.50", "149.50"]:
            await auth_client.post(
                f"/api/v1/accounts/{account_id}/deposit",
                json={"amount": amount},
            )
        bal_resp = await auth_client.get(f"/api/v1/accounts/{account_id}/balance")
        assert float(bal_resp.json()["data"]["balance"]) == 500.00

    async def test_deposit_without_description_succeeds(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        resp = await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "10.00"},
        )
        assert resp.status_code == 200

    async def test_deposit_zero_returns_422(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/deposit",
            json={"amount": "0"},
        )
        assert resp.status_code == 422

    async def test_deposit_negative_returns_422(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/deposit",
            json={"amount": "-100.00"},
        )
        assert resp.status_code == 422

    async def test_deposit_missing_amount_returns_422(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/deposit",
            json={"description": "No amount"},
        )
        assert resp.status_code == 422

    async def test_deposit_unauthenticated_returns_401(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        auth_header = auth_client.headers.pop("authorization", None)
        auth_client.cookies.clear()

        resp = await auth_client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/deposit",
            json={"amount": "100.00"},
        )

        if auth_header:
            auth_client.headers["authorization"] = auth_header

        assert resp.status_code == 401

    async def test_deposit_to_another_users_account_is_forbidden(
        self, client: AsyncClient, savings_account: dict
    ):
        other_token = await _register_login(client, "attacker_dep@example.com")
        resp = await client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/deposit",
            json={"amount": "100.00"},
            headers=_bearer(other_token),
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# POST /accounts/{account_id}/withdraw
# ---------------------------------------------------------------------------

class TestWithdraw:

    async def test_withdraw_success(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        resp = await auth_client.post(
            f"/api/v1/accounts/{account_id}/withdraw",
            json={"amount": "500.00", "description": "Rent"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Withdrawal successful"
        txn = resp.json()["data"]
        assert float(txn["balance_after"]) == 99_500.00
        # txn_type = txn.get("type") or txn.get("transaction_type")
        # assert txn_type in ("DEBIT", "WITHDRAWAL")

    async def test_withdraw_exact_balance_succeeds(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "250.00"},
        )
        resp = await auth_client.post(
            f"/api/v1/accounts/{account_id}/withdraw",
            json={"amount": "250.00"},
        )
        assert resp.status_code == 200
        assert float(resp.json()["data"]["balance_after"]) == 0.00

    async def test_withdraw_insufficient_funds_returns_error(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "100.00"},
        )
        resp = await auth_client.post(
            f"/api/v1/accounts/{account_id}/withdraw",
            json={"amount": "999.00"},
        )
        assert resp.status_code in (400, 422)

    async def test_withdraw_from_empty_account_returns_error(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{savings_account['account_id']}/withdraw",
            json={"amount": "1.00"},
        )
        assert resp.status_code in (400, 422)

    async def test_withdraw_zero_returns_422(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{funded_account['account_id']}/withdraw",
            json={"amount": "0"},
        )
        assert resp.status_code == 422

    async def test_withdraw_negative_returns_422(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post(
            f"/api/v1/accounts/{funded_account['account_id']}/withdraw",
            json={"amount": "-50.00"},
        )
        assert resp.status_code == 422

    async def test_withdraw_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        # Remove header
        auth_header = auth_client.headers.pop("authorization", None)

        # Remove cookies
        auth_client.cookies.clear()

        resp = await auth_client.post(
            f"/api/v1/accounts/{funded_account['account_id']}/withdraw",
            json={"amount": "100.00"},
        )

        # Restore header
        if auth_header:
            auth_client.headers["authorization"] = auth_header

        assert resp.status_code == 401

    async def test_withdraw_from_another_users_account_is_forbidden(
        self, client: AsyncClient, funded_account: dict
    ):
        other_token = await _register_login(client, "attacker_wd@example.com")
        resp = await client.post(
            f"/api/v1/accounts/{funded_account['account_id']}/withdraw",
            json={"amount": "100.00"},
            headers=_bearer(other_token),
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/balance
# ---------------------------------------------------------------------------

class TestGetBalance:

    async def test_initial_balance_is_zero(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/balance"
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Balance retrieved"
        assert float(resp.json()["data"]["balance"]) == 0.0

    async def test_balance_reflects_deposit(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "350.00"},
        )
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}/balance")
        assert float(resp.json()["data"]["balance"]) == 350.00

    async def test_balance_reflects_deposit_and_withdrawal(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "1000.00"},
        )
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/withdraw",
            json={"amount": "375.00"},
        )
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}/balance")
        assert float(resp.json()["data"]["balance"]) == 625.00


    async def test_get_balance_unauthenticated_returns_401(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        # Remove Authorization header
        auth_header = auth_client.headers.pop("authorization", None)

        # Remove auth cookies
        auth_client.cookies.clear()

        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/balance"
        )

        # Restore header (so other tests using same client aren't affected)
        if auth_header:
            auth_client.headers["authorization"] = auth_header

        assert resp.status_code == 401
        
    async def test_get_balance_another_users_account_is_forbidden(
        self, client: AsyncClient, savings_account: dict
    ):
        other_token = await _register_login(client, "spy_bal@example.com")
        resp = await client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/balance",
            headers=_bearer(other_token),
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/transactions
# ---------------------------------------------------------------------------

class TestGetTransactions:

    async def _make_transactions(self, auth_client, account_id):
        """3 deposits + 1 withdrawal = 4 transactions total."""
        for amount in ["200.00", "300.00", "100.00"]:
            await auth_client.post(
                f"/api/v1/accounts/{account_id}/deposit",
                json={"amount": amount},
            )
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/withdraw",
            json={"amount": "150.00"},
        )

    async def test_get_transactions_returns_correct_count(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await self._make_transactions(auth_client, account_id)
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Transactions retrieved"
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 4
        assert body["total"] == 4

    async def test_get_transactions_pagination_page_1(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await self._make_transactions(auth_client, account_id)
        resp = await auth_client.get(
            f"/api/v1/accounts/{account_id}/transactions?page=1&page_size=2"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] == 4

    async def test_get_transactions_pagination_page_2(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await self._make_transactions(auth_client, account_id)
        resp = await auth_client.get(
            f"/api/v1/accounts/{account_id}/transactions?page=2&page_size=2"
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    async def test_get_transactions_page_beyond_last_returns_empty(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await self._make_transactions(auth_client, account_id)
        resp = await auth_client.get(
            f"/api/v1/accounts/{account_id}/transactions?page=99&page_size=20"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_get_transactions_page_size_exceeds_max_returns_422(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/transactions?page_size=200"
        )
        assert resp.status_code == 422

    async def test_get_transactions_page_zero_returns_422(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/transactions?page=0"
        )
        assert resp.status_code == 422

    async def test_transaction_response_fields_present(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await auth_client.post(
            f"/api/v1/accounts/{account_id}/deposit",
            json={"amount": "100.00", "description": "Field check"},
        )
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}/transactions")
        txn = resp.json()["data"][0]
        required_keys = {
            "transaction_id", "transaction_number", "type",
            "amount", "balance_after", "status", "timestamp",
        }
        assert required_keys.issubset(txn.keys())

    async def test_transaction_types_are_correct(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        account_id = savings_account["account_id"]
        await self._make_transactions(auth_client, account_id)
        resp = await auth_client.get(f"/api/v1/accounts/{account_id}/transactions")
        type_key = "type" if "type" in resp.json()["data"][0] else "transaction_type"
        types = {txn[type_key] for txn in resp.json()["data"]}
        credit_types = {"WITHDRAWAL", "DEPOSIT"}
        debit_types = {"DEPOSIT", "WITHDRAWAL"}
        assert types & credit_types, f"Expected a credit-type transaction, got: {types}"
        assert types & debit_types, f"Expected a debit-type transaction, got: {types}"

    async def test_get_transactions_empty_account(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/transactions"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["total"] == 0

    async def test_get_transactions_unauthenticated_returns_401(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        # Remove Authorization header
        auth_header = auth_client.headers.pop("authorization", None)

        # Clear authentication cookies
        auth_client.cookies.clear()

        resp = await auth_client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/transactions"
        )

        # Restore header for other tests
        if auth_header:
            auth_client.headers["authorization"] = auth_header

        assert resp.status_code == 401

    async def test_get_transactions_another_users_account_is_forbidden(
        self, client: AsyncClient, savings_account: dict
    ):
        other_token = await _register_login(client, "spy_txn@example.com")
        resp = await client.get(
            f"/api/v1/accounts/{savings_account['account_id']}/transactions",
            headers=_bearer(other_token),
        )
        assert resp.status_code in (403, 404)