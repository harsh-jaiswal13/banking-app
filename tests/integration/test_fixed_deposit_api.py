"""
Integration tests for /api/v1/fixed-deposits endpoints.
File: tests/integration/test_fixed_deposit_api.py

Fixtures from conftest.py:
  client          – unauthenticated AsyncClient
  auth_client     – AsyncClient with Authorization header set
  savings_account – REGULAR account (zero balance) for the authenticated user
  funded_account  – REGULAR account pre-loaded with 100,000
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Constants — mirror the service's INTEREST_RATES / PREMATURE_CLOSURE_PENALTY
# ---------------------------------------------------------------------------

VALID_AMOUNT    = "10000.00"
VALID_TENURE    = 12          # → 6.5 % interest
INVALID_TENURE  = 7           # not in [6, 12, 24, 36, 60]
FEE_PERCENT     = Decimal("1.5")   # premature closure penalty


def _premature_closure_amount(principal: float) -> float:
    """Return the expected payout after the 1.5 % premature-closure penalty."""
    p = Decimal(str(principal))
    penalty = p * FEE_PERCENT / 100
    return float(p - penalty)


# ---------------------------------------------------------------------------
# Helpers
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


async def _create_fd(
    auth_client: AsyncClient,
    account_id: int,
    amount: str = VALID_AMOUNT,
    tenure: int = VALID_TENURE,
) -> dict:
    """Helper: create an FD and return its data dict."""
    resp = await auth_client.post("/api/v1/fixed-deposits", json={
        "account_id": account_id,
        "amount": amount,
        "tenure_months": tenure,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ===========================================================================
# POST /api/v1/fixed-deposits  – create FD
# ===========================================================================

class TestCreateFixedDeposit:

    async def test_create_fd_returns_201(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": VALID_AMOUNT,
            "tenure_months": VALID_TENURE,
        })
        assert resp.status_code == 201

    async def test_create_fd_response_message(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": VALID_AMOUNT,
            "tenure_months": VALID_TENURE,
        })
        assert resp.json()["message"] == "Fixed Deposit created successfully"

    async def test_create_fd_response_fields(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        data = await _create_fd(auth_client, funded_account["account_id"])
        required = {
            "fd_id", "fd_number", "principal_amount",
            "interest_rate", "tenure_months", "maturity_amount",
            "maturity_date", "status", "created_at",
        }
        assert required.issubset(data.keys())

    async def test_create_fd_status_is_active(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        data = await _create_fd(auth_client, funded_account["account_id"])
        assert data["status"] == "ACTIVE"

    async def test_create_fd_principal_matches_request(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        data = await _create_fd(auth_client, funded_account["account_id"])
        assert abs(data["principal_amount"] - float(VALID_AMOUNT)) < 0.01

    async def test_create_fd_maturity_greater_than_principal(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        data = await _create_fd(auth_client, funded_account["account_id"])
        assert data["maturity_amount"] > data["principal_amount"]

    async def test_create_fd_deducts_from_account(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        bal_before = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        await _create_fd(auth_client, account_id)

        bal_after = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        assert abs((bal_before - bal_after) - float(VALID_AMOUNT)) < 0.01

    async def test_create_fd_unique_fd_numbers(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        fd1 = await _create_fd(auth_client, account_id)
        fd2 = await _create_fd(auth_client, account_id, amount="5000.00")
        assert fd1["fd_number"] != fd2["fd_number"]

    @pytest.mark.parametrize("tenure", [6, 12, 24, 36, 60])
    async def test_create_fd_valid_tenures(
        self, auth_client: AsyncClient, funded_account: dict, tenure: int
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": "5000.00",
            "tenure_months": tenure,
        })
        assert resp.status_code == 201
        assert resp.json()["data"]["tenure_months"] == tenure

    async def test_create_fd_invalid_tenure_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": VALID_AMOUNT,
            "tenure_months": INVALID_TENURE,
        })
        assert resp.status_code in (400, 422)

    async def test_create_fd_zero_amount_returns_422(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": "0",
            "tenure_months": VALID_TENURE,
        })
        assert resp.status_code == 422

    async def test_create_fd_negative_amount_returns_422(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": "-500.00",
            "tenure_months": VALID_TENURE,
        })
        assert resp.status_code == 422

    async def test_create_fd_insufficient_balance_returns_error(
        self, auth_client: AsyncClient, savings_account: dict
    ):
        # savings_account has zero balance
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": savings_account["account_id"],
            "amount": VALID_AMOUNT,
            "tenure_months": VALID_TENURE,
        })
        assert resp.status_code in (400, 422)

    async def test_create_fd_wrong_account_returns_error(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": 999999,
            "amount": VALID_AMOUNT,
            "tenure_months": VALID_TENURE,
        })
        assert resp.status_code in (400, 404)

    async def test_create_fd_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.post("/api/v1/fixed-deposits", json={
            "account_id": funded_account["account_id"],
            "amount": VALID_AMOUNT,
            "tenure_months": VALID_TENURE,
        })
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ===========================================================================
# GET /api/v1/fixed-deposits/{fd_id}  – get single FD
# ===========================================================================

class TestGetFixedDeposit:

    async def test_get_fd_returns_200(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get(f"/api/v1/fixed-deposits/{fd['fd_id']}")
        assert resp.status_code == 200

    async def test_get_fd_message(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get(f"/api/v1/fixed-deposits/{fd['fd_id']}")
        assert resp.json()["message"] == "Fixed Deposit retrieved"

    async def test_get_fd_data_matches_create(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get(f"/api/v1/fixed-deposits/{fd['fd_id']}")
        fetched = resp.json()["data"]
        assert fetched["fd_id"]       == fd["fd_id"]
        assert fetched["fd_number"]   == fd["fd_number"]
        assert abs(fetched["principal_amount"] - fd["principal_amount"]) < 0.01

    async def test_get_nonexistent_fd_returns_error(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.get("/api/v1/fixed-deposits/999999")
        assert resp.status_code in (400, 404, 422)

    async def test_get_other_users_fd_is_forbidden(
        self, client: AsyncClient, funded_account: dict, auth_client: AsyncClient
    ):
        """A second user should not be able to retrieve another user's FD."""
        fd = await _create_fd(auth_client, funded_account["account_id"])

        # Register + login a different user
        await client.post("/api/v1/auth/register", json={
            "email": "spy_fd@example.com",
            "password": "SecurePass1!",
            "full_name": "Spy User",
            "phone": "9000000099",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "spy_fd@example.com",
            "password": "SecurePass1!",
        })
        other_token = login.json()["data"]["access_token"]

        resp = await client.get(
            f"/api/v1/fixed-deposits/{fd['fd_id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code in (400, 403, 404, 422)

    async def test_get_fd_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        saved = _clear_auth(auth_client)
        resp = await auth_client.get(f"/api/v1/fixed-deposits/{fd['fd_id']}")
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ===========================================================================
# GET /api/v1/fixed-deposits  – list all FDs (with optional status filter)
# ===========================================================================

class TestListFixedDeposits:

    async def test_list_returns_200(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/fixed-deposits")
        assert resp.status_code == 200

    async def test_list_empty_for_new_user(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/fixed-deposits")
        assert resp.json()["data"] == []

    async def test_list_contains_created_fd(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get("/api/v1/fixed-deposits")
        fds = resp.json()["data"]
        assert any(f["fd_id"] == fd["fd_id"] for f in fds)

    async def test_list_count_grows_with_multiple_fds(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        await _create_fd(auth_client, account_id, amount="5000.00")
        await _create_fd(auth_client, account_id, amount="3000.00", tenure=6)
        resp = await auth_client.get("/api/v1/fixed-deposits")
        assert len(resp.json()["data"]) == 2

    async def test_list_filter_active_status(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get("/api/v1/fixed-deposits?status=ACTIVE")
        assert resp.status_code == 200
        fds = resp.json()["data"]
        assert all(f["status"] == "ACTIVE" for f in fds)

    async def test_list_filter_closed_status_empty_initially(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.get("/api/v1/fixed-deposits?status=CLOSED")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_list_unauthenticated_returns_401(
        self, auth_client: AsyncClient
    ):
        saved = _clear_auth(auth_client)
        resp = await auth_client.get("/api/v1/fixed-deposits")
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ===========================================================================
# POST /api/v1/fixed-deposits/{fd_id}/close  – premature closure
# ===========================================================================

class TestCloseFixedDeposit:

    async def test_premature_close_returns_200(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        assert resp.status_code == 200

    async def test_premature_close_response_message(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        assert resp.json()["message"] == "Fixed Deposit closed successfully"

    async def test_premature_close_status_becomes_closed(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        assert resp.json()["data"]["status"] == "CLOSED"

    async def test_premature_close_applies_penalty(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        data = resp.json()["data"]
        expected_closure = _premature_closure_amount(fd["principal_amount"])
        assert abs(data["closure_amount"] - expected_closure) < 0.01

    async def test_premature_close_credits_account(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        account_id = funded_account["account_id"]
        fd = await _create_fd(auth_client, account_id)

        bal_before = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        closure_amount = resp.json()["data"]["closure_amount"]

        bal_after = (await auth_client.get(
            f"/api/v1/accounts/{account_id}/balance"
        )).json()["data"]["balance"]

        assert abs((bal_after - bal_before) - closure_amount) < 0.01

    async def test_premature_close_without_confirm_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": False},
        )
        assert resp.status_code in (400, 422)

    async def test_premature_close_already_closed_fd_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        # Close it once
        await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        # Try to close again
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        assert resp.status_code in (400, 422)

    async def test_close_nonexistent_fd_returns_error(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post(
            "/api/v1/fixed-deposits/999999/close",
            json={"confirm": True},
        )
        assert resp.status_code in (400, 404, 422)

    async def test_premature_close_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        saved = _clear_auth(auth_client)
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401


# ===========================================================================
# POST /api/v1/fixed-deposits/{fd_id}/withdraw  – withdraw matured FD
# ===========================================================================

class TestWithdrawMaturedFD:
    """
    The matured-withdraw endpoint requires `fd.maturity_date <= today`.
    Since all FDs created in tests have future maturity dates (tenure ≥ 6 months),
    these tests cover the negative paths (not matured yet, already closed, etc.).
    The happy-path is indirectly covered by verifying the service logic in unit tests.
    """

    async def test_withdraw_not_matured_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """FD created today has a future maturity date — withdraw should fail."""
        fd = await _create_fd(auth_client, funded_account["account_id"])
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/withdraw"
        )
        # Service raises BankingException(status_code=400) for unmatured FDs
        assert resp.status_code in (400, 422)

    async def test_withdraw_after_premature_close_returns_error(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        """Cannot withdraw a CLOSED FD."""
        fd = await _create_fd(auth_client, funded_account["account_id"])
        await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/close",
            json={"confirm": True},
        )
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/withdraw"
        )
        assert resp.status_code in (400, 422)

    async def test_withdraw_nonexistent_fd_returns_error(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post("/api/v1/fixed-deposits/999999/withdraw")
        assert resp.status_code in (400, 404, 422)

    async def test_withdraw_unauthenticated_returns_401(
        self, auth_client: AsyncClient, funded_account: dict
    ):
        fd = await _create_fd(auth_client, funded_account["account_id"])
        saved = _clear_auth(auth_client)
        resp = await auth_client.post(
            f"/api/v1/fixed-deposits/{fd['fd_id']}/withdraw"
        )
        _restore_auth(auth_client, saved)
        assert resp.status_code == 401
