"""
Unit Tests for AccountService (app/services/account.py)

Run with:
    pytest tests/unit/test_account_service.py -v
    pytest tests/unit/test_account_service.py::TestDeposit -v      ← just one class
    pytest tests/unit/test_account_service.py -v --cov=app/services/account

KEY DIFFERENCE FROM AUTH TESTS:
    AccountService takes TWO repos:
        - AccountRepository    → handles accounts
        - TransactionRepository → handles transaction history
    Both need to be mocked separately.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.account import AccountService
from app.models.savings_account import AccountStatus
from app.models.transaction import TransactionType, TransactionStatus
from app.core.exceptions import (
    AccountNotFoundException,
    InvalidAmountException,
    InsufficientBalanceException,
    AccountInactiveException,
)


# ---------------------------------------------------------------------------
# Helpers — Fake objects
# ---------------------------------------------------------------------------

def make_fake_account(
    account_id=1,
    user_id=1,
    account_number="ACC1234567890",
    balance=Decimal("5000.00"),
    account_type="savings",
    interest_rate=Decimal("3.5"),
    status=AccountStatus.ACTIVE,
):
    """

    THE FIX:
        account.status is left as a MagicMock (the default when you don't assign it).
        MagicMock lets you set ANY attribute freely, including.value.
        
        But the service does:  if account.status != AccountStatus.ACTIVE
        So we need account.status to equal AccountStatus.ACTIVE for active accounts.
        We do this by setting: account.status = status  (real enum)
        And NOT touching account.status.value afterward.
        
        For the .value used in the response dict, MagicMock auto-returns a MagicMock
        for account.status.value — which is fine, we don't assert its exact string
        in most tests. For tests that do check status string, override manually.
    """
    account = MagicMock()
    account.account_id = account_id
    account.user_id = user_id
    account.account_number = account_number
    account.balance = balance
    account.interest_rate = interest_rate
    account.created_at = "2024-01-01T00:00:00"
    account.updated_at = "2024-01-01T00:00:00"

    # account_type: MagicMock handles .value automatically — just set the string
    account.account_type.value = account_type   # MagicMock attr, NOT a real enum → safe

    # status: assign the real enum so != comparisons work in service logic
    # Do NOT set .value after this — Python enums are read-only
    account.status = status

    return account


def make_fake_transaction(
    transaction_id=101,
    transaction_number="TXN123456",
    transaction_type=TransactionType.DEPOSIT,
    amount=Decimal("1000.00"),
    balance_after=Decimal("6000.00"),
    description="Deposit",
):
    """Fake SQLAlchemy Transaction model object."""
    txn = MagicMock()
    txn.transaction_id = transaction_id
    txn.transaction_number = transaction_number
    txn.transaction_type = transaction_type   # real enum for == comparisons
    txn.amount = amount
    txn.balance_after = balance_after
    txn.description = description
    txn.status = TransactionStatus.SUCCESS     # real enum, NOT .value setter
    txn.created_at = "2024-01-01T10:00:00"
    return txn


def make_mock_account_repo(account=None):
    """
    Fake AccountRepository.
    Pass an account object to simulate a found account, None for not found.
    """
    repo = MagicMock()
    repo.get = AsyncMock(return_value=account)
    repo.create = AsyncMock(return_value=account)
    repo.update_balance = AsyncMock(return_value=None)
    repo.account_number_exists = AsyncMock(return_value=False)  # unique on first try
    return repo


def make_mock_transaction_repo(transactions=None, total=0):
    """
    Fake TransactionRepository.
    transactions: list of fake transaction objects for get_by_account
    total: int for count()
    """
    repo = MagicMock()
    repo.create = AsyncMock(return_value=make_fake_transaction())
    repo.get_by_account = AsyncMock(return_value=transactions or [])
    repo.count = AsyncMock(return_value=total)
    return repo


def make_service(account=None, transactions=None, total=0):
    """
    One-liner to build AccountService with both mocked repos.
    Used in most tests to reduce boilerplate.
    """
    account_repo = make_mock_account_repo(account=account)
    transaction_repo = make_mock_transaction_repo(transactions=transactions, total=total)
    service = AccountService(account_repo=account_repo, transaction_repo=transaction_repo)
    return service, account_repo, transaction_repo


# ---------------------------------------------------------------------------
# CHECKPOINT A — create_account()
# ---------------------------------------------------------------------------

class TestCreateAccount:
    """
    create_account() has an interesting loop:
        while account_number_exists: generate new one
    We test both the normal case and the collision case.
    """

    @pytest.mark.asyncio
    async def test_create_account_returns_account_dict(self):
        """Happy path: creates account and returns correct fields"""
        fake_account = make_fake_account()
        service, account_repo, _ = make_service(account=fake_account)

        with patch("app.services.account.generate_account_number", return_value="ACC999"), \
             patch("app.services.account.settings") as mock_settings:

            mock_settings.SAVINGS_INTEREST_RATE = 3.5
            result = await service.create_account(user_id=1, account_type="savings")

        assert result["account_id"] == 1
        assert result["account_number"] == "ACC1234567890"
        assert result["balance"] == 5000.0         # returned as float, not Decimal
        assert "interest_rate" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_create_account_retries_on_duplicate_account_number(self):
        """
        If generated account number already exists, it must keep retrying.
        
        Simulated: first call to account_number_exists returns True (collision),
        second call returns False (unique found).
        """
        fake_account = make_fake_account()
        service, account_repo, _ = make_service(account=fake_account)

        # First number collides, second is unique
        account_repo.account_number_exists = AsyncMock(side_effect=[True, False])

        with patch("app.services.account.generate_account_number", return_value="ACC999"), \
             patch("app.services.account.settings") as mock_settings:

            mock_settings.SAVINGS_INTEREST_RATE = 3.5
            await service.create_account(user_id=1, account_type="savings")

        # generate_account_number called twice, account_number_exists called twice
        assert account_repo.account_number_exists.call_count == 2

    @pytest.mark.asyncio
    async def test_create_account_sets_initial_balance_to_zero(self):
        """New account must always start with balance = 0.00"""
        fake_account = make_fake_account()
        service, account_repo, _ = make_service(account=fake_account)

        with patch("app.services.account.generate_account_number", return_value="ACC999"), \
             patch("app.services.account.settings") as mock_settings:

            mock_settings.SAVINGS_INTEREST_RATE = 3.5
            await service.create_account(user_id=1, account_type="savings")

        # Check what data was passed into account_repo.create()
        created_data = account_repo.create.call_args[0][0]
        assert created_data["balance"] == Decimal("0.00")
        assert created_data["status"] == AccountStatus.ACTIVE


# ---------------------------------------------------------------------------
# CHECKPOINT B — get_account()
# ---------------------------------------------------------------------------

class TestGetAccount:
    """
    get_account() has TWO reasons to raise AccountNotFoundException:
        1. Account doesn't exist in DB
        2. Account exists but belongs to a different user (ownership check)
    
    Both should look identical to the caller — security through obscurity.
    (You don't want to tell a hacker "account exists but isn't yours")
    """

    @pytest.mark.asyncio
    async def test_get_account_returns_account_dict(self):
        """Happy path: account exists and belongs to user"""
        fake_account = make_fake_account(account_id=1, user_id=1)
        service, _, _ = make_service(account=fake_account)

        result = await service.get_account(account_id=1, user_id=1)

        assert result["account_id"] == 1
        assert result["balance"] == 5000.0

    @pytest.mark.asyncio
    async def test_get_account_raises_if_account_not_found(self):
        """DB returns None → AccountNotFoundException"""
        service, _, _ = make_service(account=None)   # ← no account in DB

        with pytest.raises(AccountNotFoundException):
            await service.get_account(account_id=999, user_id=1)

    @pytest.mark.asyncio
    async def test_get_account_raises_if_wrong_owner(self):
        """
        Account exists but user_id doesn't match.
        IMPORTANT: raises AccountNotFoundException (not a 403/PermissionError)
        This is intentional — don't reveal the account exists to the wrong person.
        """
        fake_account = make_fake_account(account_id=1, user_id=2)  # belongs to user 2
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountNotFoundException):
            await service.get_account(account_id=1, user_id=1)  # user 1 requesting


# ---------------------------------------------------------------------------
# CHECKPOINT C — deposit()
# ---------------------------------------------------------------------------

class TestDeposit:
    """
    deposit() has the most checks:
        1. Amount must be positive
        2. Account must exist
        3. User must own the account
        4. Account must be ACTIVE (not frozen/closed)
        5. Balance updated correctly
        6. Transaction recorded
    """

    @pytest.mark.asyncio
    async def test_deposit_success_returns_transaction_details(self):
        """Happy path: valid deposit returns transaction info"""
        fake_account = make_fake_account(balance=Decimal("5000.00"))
        fake_txn = make_fake_transaction(
            amount=Decimal("1000.00"),
            balance_after=Decimal("6000.00")
        )
        service, account_repo, transaction_repo = make_service(account=fake_account)
        transaction_repo.create = AsyncMock(return_value=fake_txn)

        with patch("app.services.account.generate_transaction_number", return_value="TXN123"):
            result = await service.deposit(
                account_id=1, user_id=1, amount=Decimal("1000.00")
            )

        assert result["amount"] == 1000.0
        assert result["balance_after"] == 6000.0
        assert "transaction_id" in result
        assert "transaction_number" in result

    @pytest.mark.asyncio
    async def test_deposit_updates_balance_correctly(self):
        """
        After deposit, update_balance must be called with
        old_balance + deposit_amount (not any other value).
        """
        fake_account = make_fake_account(balance=Decimal("5000.00"))
        service, account_repo, _ = make_service(account=fake_account)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("2500.00"))

        # update_balance must have been called with account_id=1, new_balance=7500
        account_repo.update_balance.assert_called_once_with(1, Decimal("7500.00"))

    @pytest.mark.asyncio
    async def test_deposit_raises_if_amount_is_zero(self):
        """Zero deposit → InvalidAmountException"""
        service, _, _ = make_service(account=make_fake_account())

        with pytest.raises(InvalidAmountException):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("0"))

    @pytest.mark.asyncio
    async def test_deposit_raises_if_amount_is_negative(self):
        """Negative deposit → InvalidAmountException"""
        service, _, _ = make_service(account=make_fake_account())

        with pytest.raises(InvalidAmountException):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("-500.00"))

    @pytest.mark.asyncio
    async def test_deposit_raises_if_account_not_found(self):
        """No account in DB → AccountNotFoundException"""
        service, _, _ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.deposit(account_id=999, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_deposit_raises_if_wrong_owner(self):
        """Account belongs to different user → AccountNotFoundException"""
        fake_account = make_fake_account(user_id=2)  # belongs to user 2
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountNotFoundException):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_deposit_raises_if_account_inactive(self):
        """
        Frozen/closed account must reject deposits.
        We override status to INACTIVE for this test only.
        """
        fake_account = make_fake_account()
        fake_account.status = AccountStatus.INACTIVE   # ← override to inactive
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountInactiveException):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_deposit_records_transaction_with_correct_type(self):
        """Transaction recorded must have type=DEPOSIT, not WITHDRAWAL"""
        fake_account = make_fake_account(balance=Decimal("1000.00"))
        fake_txn = make_fake_transaction()
        service, _, transaction_repo = make_service(account=fake_account)
        transaction_repo.create = AsyncMock(return_value=fake_txn)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            await service.deposit(account_id=1, user_id=1, amount=Decimal("500.00"))

        # Inspect what was passed to transaction_repo.create
        txn_data = transaction_repo.create.call_args[0][0]
        assert txn_data["transaction_type"] == TransactionType.DEPOSIT
        assert txn_data["status"] == TransactionStatus.SUCCESS


# ---------------------------------------------------------------------------
# CHECKPOINT D — withdraw()
# ---------------------------------------------------------------------------

class TestWithdraw:
    """
    withdraw() has everything deposit() has PLUS:
        - Insufficient balance check (can't withdraw more than you have)
    """

    @pytest.mark.asyncio
    async def test_withdraw_success_returns_transaction_details(self):
        """Happy path: sufficient balance → withdrawal succeeds"""
        fake_account = make_fake_account(balance=Decimal("5000.00"))
        fake_txn = make_fake_transaction(
            transaction_type=TransactionType.WITHDRAWAL,
            amount=Decimal("1000.00"),
            balance_after=Decimal("4000.00")
        )
        service, _, transaction_repo = make_service(account=fake_account)
        transaction_repo.create = AsyncMock(return_value=fake_txn)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            result = await service.withdraw(
                account_id=1, user_id=1, amount=Decimal("1000.00")
            )

        assert result["amount"] == 1000.0
        assert result["balance_after"] == 4000.0

    @pytest.mark.asyncio
    async def test_withdraw_updates_balance_correctly(self):
        """After withdrawal, balance = old_balance - withdrawn_amount"""
        fake_account = make_fake_account(balance=Decimal("5000.00"))
        service, account_repo, _ = make_service(account=fake_account)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("1500.00"))

        account_repo.update_balance.assert_called_once_with(1, Decimal("3500.00"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_insufficient_balance(self):
        """
        Withdrawal > balance → InsufficientBalanceException.
        This is the key check that deposit() doesn't have.
        """
        fake_account = make_fake_account(balance=Decimal("500.00"))
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(InsufficientBalanceException):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("1000.00"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_amount_equals_zero(self):
        """Zero withdrawal → InvalidAmountException"""
        service, _, _ = make_service(account=make_fake_account())

        with pytest.raises(InvalidAmountException):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("0"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_amount_is_negative(self):
        """Negative withdrawal → InvalidAmountException"""
        service, _, _ = make_service(account=make_fake_account())

        with pytest.raises(InvalidAmountException):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("-200.00"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_account_not_found(self):
        """No account → AccountNotFoundException"""
        service, _, _ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.withdraw(account_id=999, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_wrong_owner(self):
        """Account belongs to someone else → AccountNotFoundException"""
        fake_account = make_fake_account(user_id=2)
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountNotFoundException):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_withdraw_raises_if_account_inactive(self):
        """Inactive account → AccountInactiveException"""
        fake_account = make_fake_account()
        fake_account.status = AccountStatus.INACTIVE
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountInactiveException):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_withdraw_exact_balance_succeeds(self):
        """
        Edge case: withdrawing EXACTLY the available balance must succeed.
        balance=500, withdraw=500 → balance_after=0, not an error.
        """
        fake_account = make_fake_account(balance=Decimal("500.00"))
        service, account_repo, _ = make_service(account=fake_account)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("500.00"))

        account_repo.update_balance.assert_called_once_with(1, Decimal("0.00"))

    @pytest.mark.asyncio
    async def test_withdraw_records_transaction_with_correct_type(self):
        """Transaction recorded must be WITHDRAWAL, not DEPOSIT"""
        fake_account = make_fake_account(balance=Decimal("2000.00"))
        fake_txn = make_fake_transaction(transaction_type=TransactionType.WITHDRAWAL)
        service, _, transaction_repo = make_service(account=fake_account)
        transaction_repo.create = AsyncMock(return_value=fake_txn)

        with patch("app.services.account.generate_transaction_number", return_value="TXN"):
            await service.withdraw(account_id=1, user_id=1, amount=Decimal("500.00"))

        txn_data = transaction_repo.create.call_args[0][0]
        assert txn_data["transaction_type"] == TransactionType.WITHDRAWAL


# ---------------------------------------------------------------------------
# CHECKPOINT E — get_balance()
# ---------------------------------------------------------------------------

class TestGetBalance:

    @pytest.mark.asyncio
    async def test_get_balance_returns_correct_fields(self):
        """Returns account_id, account_number, balance, status"""
        fake_account = make_fake_account(balance=Decimal("3000.00"))
        service, _, _ = make_service(account=fake_account)

        result = await service.get_balance(account_id=1, user_id=1)

        assert result["balance"] == 3000.0
        assert "account_id" in result
        assert "account_number" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_get_balance_raises_if_account_not_found(self):
        service, _, _ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.get_balance(account_id=999, user_id=1)

    @pytest.mark.asyncio
    async def test_get_balance_raises_if_wrong_owner(self):
        fake_account = make_fake_account(user_id=2)
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountNotFoundException):
            await service.get_balance(account_id=1, user_id=1)


# ---------------------------------------------------------------------------
# CHECKPOINT F — get_transactions() with pagination
# ---------------------------------------------------------------------------

class TestGetTransactions:
    """
    get_transactions() returns a TUPLE: (list_of_transactions, total_count)
    It also handles pagination via page + page_size.
    """

    @pytest.mark.asyncio
    async def test_get_transactions_returns_list_and_total(self):
        """Returns tuple of (transactions list, total count)"""
        fake_account = make_fake_account()
        fake_txns = [make_fake_transaction(), make_fake_transaction(transaction_id=102)]
        service, _, _ = make_service(account=fake_account, transactions=fake_txns, total=2)

        result_list, total = await service.get_transactions(account_id=1, user_id=1)

        assert len(result_list) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_transactions_page_2_skips_correctly(self):
        """
        Page 2 with page_size=10 → skip=10.
        We verify get_by_account is called with skip=10, limit=10.
        """
        fake_account = make_fake_account()
        service, _, transaction_repo = make_service(account=fake_account, transactions=[], total=25)

        await service.get_transactions(account_id=1, user_id=1, page=2, page_size=10)

        transaction_repo.get_by_account.assert_called_once_with(1, skip=10, limit=10)

    @pytest.mark.asyncio
    async def test_get_transactions_empty_account_returns_empty_list(self):
        """Account with no transactions returns empty list, total=0"""
        fake_account = make_fake_account()
        service, _, _ = make_service(account=fake_account, transactions=[], total=0)

        result_list, total = await service.get_transactions(account_id=1, user_id=1)

        assert result_list == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_transactions_raises_if_wrong_owner(self):
        """Other user's account → AccountNotFoundException"""
        fake_account = make_fake_account(user_id=2)
        service, _, _ = make_service(account=fake_account)

        with pytest.raises(AccountNotFoundException):
            await service.get_transactions(account_id=1, user_id=1)

    @pytest.mark.asyncio
    async def test_get_transactions_each_item_has_required_fields(self):
        """Every transaction dict must have these fields"""
        fake_account = make_fake_account()
        fake_txns = [make_fake_transaction()]
        service, _, _ = make_service(account=fake_account, transactions=fake_txns, total=1)

        result_list, _ = await service.get_transactions(account_id=1, user_id=1)

        required_fields = {
            "transaction_id", "transaction_number", "type",
            "amount", "balance_after", "description", "status", "timestamp"
        }
        assert required_fields.issubset(result_list[0].keys())