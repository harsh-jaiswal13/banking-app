"""
Unit Tests for FixedDepositService (app/services/fixed_deposit.py)

Run with:
    pytest tests/unit/services/test_fixed_deposit_service.py -v
    pytest tests/unit/services/test_fixed_deposit_service.py::TestCreateFD -v

WHAT'S NEW vs previous tests:
    1. Date-dependent logic — close_fd_prematurely and withdraw_matured_fd
       both call date.today() internally. We freeze time using patch so tests
       are deterministic regardless of when they run.
    2. Penalty math — premature closure deducts 1.5% of principal
    3. Maturity math — simple interest formula: P * (1 + r * t)
    4. FDStatus enum used in comparisons — same enum-read-only rule applies
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fixed_deposit import FixedDepositService
from app.models.fixed_deposit import FDStatus
from app.core.exceptions import (
    AccountNotFoundException,
    InsufficientBalanceException,
    BankingException,
)


# ---------------------------------------------------------------------------
# Helpers — Fake objects
# ---------------------------------------------------------------------------

def make_fake_account(account_id=1, user_id=1, balance=Decimal("50000.00")):
    account = MagicMock()
    account.account_id = account_id
    account.user_id = user_id
    account.balance = balance
    return account


def make_fake_fd(
    fd_id=1,
    user_id=1,
    fd_number="FD123456",
    principal_amount=Decimal("10000.00"),
    interest_rate=Decimal("6.5"),
    tenure_months=12,
    maturity_amount=Decimal("10650.00"),
    maturity_date=None,          # default: 1 year from today (in the future)
    status=FDStatus.ACTIVE,
    savings_account_id=1,
    closed_at=None,
    closure_amount=None,
    penalty_amount=None,
):
    fd = MagicMock()
    fd.fd_id = fd_id
    fd.user_id = user_id
    fd.fd_number = fd_number
    fd.principal_amount = principal_amount
    fd.interest_rate = interest_rate
    fd.tenure_months = tenure_months
    fd.maturity_amount = maturity_amount
    fd.savings_account_id = savings_account_id
    fd.closed_at = closed_at
    fd.closure_amount = closure_amount
    fd.penalty_amount = penalty_amount
    fd.created_at = "2024-01-01T00:00:00"

    # maturity_date: default is 1 year in the future (FD not yet matured)
    fd.maturity_date = maturity_date or (date.today() + timedelta(days=365))

    # status: assign real enum for comparisons — do NOT set .value after
    fd.status = status

    return fd


def make_mock_repos(account=None, fd=None, fd_list=None):
    fd_repo = MagicMock()
    fd_repo.get = AsyncMock(return_value=fd)
    fd_repo.create = AsyncMock(return_value=fd)
    fd_repo.update = AsyncMock(return_value=fd)
    fd_repo.fd_number_exists = AsyncMock(return_value=False)  # unique on first try
    fd_repo.get_by_user_with_status = AsyncMock(return_value=fd_list or [])

    account_repo = MagicMock()
    account_repo.get = AsyncMock(return_value=account)

    transaction_repo = MagicMock()
    transaction_repo.create = AsyncMock(return_value=MagicMock())

    return fd_repo, account_repo, transaction_repo


def make_mock_account_service():
    svc = MagicMock()
    svc.withdraw = AsyncMock(return_value={"balance_after": 40000.0})
    svc.deposit = AsyncMock(return_value={"balance_after": 60000.0})
    return svc


def make_service(account=None, fd=None, fd_list=None):
    """One-liner to build FixedDepositService with all 4 dependencies mocked."""
    fd_repo, account_repo, transaction_repo = make_mock_repos(
        account=account, fd=fd, fd_list=fd_list
    )
    account_service = make_mock_account_service()
    service = FixedDepositService(
        fixed_deposit_repo=fd_repo,
        account_repo=account_repo,
        transaction_repo=transaction_repo,
        account_service=account_service,
    )
    return service, fd_repo, account_repo, account_service


# ---------------------------------------------------------------------------
# CHECKPOINT A — create_fd()
# ---------------------------------------------------------------------------

class TestCreateFD:

    @pytest.mark.asyncio
    async def test_create_fd_success_returns_fd_dict(self):
        """Happy path: valid inputs → FD created and dict returned"""
        account = make_fake_account(balance=Decimal("50000.00"))
        fake_fd = make_fake_fd()
        service, fd_repo, _, _ = make_service(account=account, fd=fake_fd)

        with patch("app.services.fixed_deposit.generate_fd_number", return_value="FD123456"):
            result = await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )

        assert result["fd_number"] == "FD123456"
        assert result["principal_amount"] == 10000.0
        assert "maturity_amount" in result
        assert "maturity_date" in result

    @pytest.mark.asyncio
    async def test_create_fd_maturity_amount_calculation_12_months(self):
        """
        Simple interest formula: P * (1 + r/100 * t_years)
        principal=10000, rate=6.5% (12 months), tenure=12 months=1 year
        maturity = 10000 * (1 + 0.065 * 1) = 10000 * 1.065 = 10650.00
        """
        account = make_fake_account(balance=Decimal("50000.00"))
        # Give the fake FD the expected maturity amount
        fake_fd = make_fake_fd(maturity_amount=Decimal("10650.00"))
        service, _, _, _ = make_service(account=account, fd=fake_fd)

        with patch("app.services.fixed_deposit.generate_fd_number", return_value="FD001"):
            result = await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )

        assert result["maturity_amount"] == pytest.approx(10650.00)

    @pytest.mark.asyncio
    async def test_create_fd_maturity_amount_calculation_6_months(self):
        """
        principal=10000, rate=6.0% (6 months), tenure=6 months=0.5 years
        maturity = 10000 * (1 + 0.06 * 0.5) = 10000 * 1.03 = 10300.00
        """
        account = make_fake_account(balance=Decimal("50000.00"))
        fake_fd = make_fake_fd(maturity_amount=Decimal("10300.00"))
        service, _, _, _ = make_service(account=account, fd=fake_fd)

        with patch("app.services.fixed_deposit.generate_fd_number", return_value="FD001"):
            result = await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=6
            )

        assert result["maturity_amount"] == pytest.approx(10300.00)

    @pytest.mark.asyncio
    async def test_create_fd_withdraws_amount_from_savings(self):
        """
        After FD is created, account_service.withdraw() must be called
        with the exact principal amount — money leaves the savings account.
        """
        account = make_fake_account(balance=Decimal("50000.00"))
        fake_fd = make_fake_fd()
        service, _, _, account_service = make_service(account=account, fd=fake_fd)

        with patch("app.services.fixed_deposit.generate_fd_number", return_value="FD001"):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )

        account_service.withdraw.assert_called_once()
        call_kwargs = account_service.withdraw.call_args.kwargs
        assert call_kwargs["amount"] == Decimal("10000.00")
        assert call_kwargs["account_id"] == 1
        assert call_kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_create_fd_retries_on_duplicate_fd_number(self):
        """
        First generated FD number already exists → retry.
        side_effect=[True, False]: first call=collision, second=unique.
        """
        account = make_fake_account(balance=Decimal("50000.00"))
        fake_fd = make_fake_fd()
        service, fd_repo, _, _ = make_service(account=account, fd=fake_fd)
        fd_repo.fd_number_exists = AsyncMock(side_effect=[True, False])

        with patch("app.services.fixed_deposit.generate_fd_number", return_value="FD001"):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )

        assert fd_repo.fd_number_exists.call_count == 2

    @pytest.mark.asyncio
    async def test_create_fd_raises_for_invalid_tenure(self):
        """
        Tenure not in [6, 12, 24, 36, 60] → BankingException.
        e.g. tenure=7 is not a supported product.
        """
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException) as exc_info:
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=7
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_fd_raises_for_zero_amount(self):
        """amount=0 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("0"), tenure_months=12
            )

    @pytest.mark.asyncio
    async def test_create_fd_raises_for_negative_amount(self):
        """amount < 0 → BankingException"""
        service, *_ = make_service(account=make_fake_account())

        with pytest.raises(BankingException):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("-5000"), tenure_months=12
            )

    @pytest.mark.asyncio
    async def test_create_fd_raises_if_account_not_found(self):
        """No account in DB → AccountNotFoundException"""
        service, *_ = make_service(account=None)

        with pytest.raises(AccountNotFoundException):
            await service.create_fd(
                user_id=1, account_id=999,
                amount=Decimal("10000.00"), tenure_months=12
            )

    @pytest.mark.asyncio
    async def test_create_fd_raises_if_wrong_owner(self):
        """Account belongs to user 2, user 1 requests → AccountNotFoundException"""
        account = make_fake_account(user_id=2)
        service, *_ = make_service(account=account)

        with pytest.raises(AccountNotFoundException):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )

    @pytest.mark.asyncio
    async def test_create_fd_raises_if_insufficient_balance(self):
        """Balance < FD amount → InsufficientBalanceException"""
        account = make_fake_account(balance=Decimal("5000.00"))
        service, *_ = make_service(account=account)

        with pytest.raises(InsufficientBalanceException):
            await service.create_fd(
                user_id=1, account_id=1,
                amount=Decimal("10000.00"), tenure_months=12
            )


# ---------------------------------------------------------------------------
# CHECKPOINT B — get_fd() and get_all_user_fds()
# ---------------------------------------------------------------------------

class TestGetFD:

    @pytest.mark.asyncio
    async def test_get_fd_returns_fd_dict(self):
        """Happy path: FD exists and belongs to user"""
        fake_fd = make_fake_fd()
        service, *_ = make_service(fd=fake_fd)

        result = await service.get_fd(fd_id=1, user_id=1)

        assert result["fd_id"] == 1
        assert result["fd_number"] == "FD123456"
        assert result["principal_amount"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_fd_raises_if_not_found(self):
        """FD not in DB → BankingException 404"""
        service, *_ = make_service(fd=None)

        with pytest.raises(BankingException) as exc_info:
            await service.get_fd(fd_id=999, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_fd_raises_if_wrong_owner(self):
        """FD belongs to user 2, user 1 requests → BankingException 404"""
        fake_fd = make_fake_fd(user_id=2)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.get_fd(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_all_user_fds_returns_list(self):
        """Returns list of FD dicts for the user"""
        fd_list = [make_fake_fd(fd_id=1), make_fake_fd(fd_id=2, fd_number="FD999")]
        service, *_ = make_service(fd_list=fd_list)

        result = await service.get_all_user_fds(user_id=1)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_all_user_fds_returns_empty_for_no_fds(self):
        """User with no FDs → empty list"""
        service, *_ = make_service(fd_list=[])

        result = await service.get_all_user_fds(user_id=1)

        assert result == []


# ---------------------------------------------------------------------------
# CHECKPOINT C — close_fd_prematurely()
#
# KEY CONCEPT: date.today() is called inside the service.
# We must FREEZE TIME so tests are not date-dependent.
#
# If today is 2024-06-01 and maturity is 2025-01-01:
#   - Premature closure → allowed  (today < maturity)
# If today is 2025-06-01 and maturity is 2025-01-01:
#   - Already matured  → not allowed (today >= maturity)
#
# By patching date.today() we control which scenario we're in.
# ---------------------------------------------------------------------------

class TestCloseFDPrematurely:

    @pytest.mark.asyncio
    async def test_premature_closure_success_returns_closure_dict(self):
        """
        Happy path: ACTIVE FD, maturity is in the future.
        
        We freeze today = 2024-06-01 and maturity = 2025-06-01
        so today < maturity (premature closure is allowed).
        """
        fake_fd = make_fake_fd(
            principal_amount=Decimal("10000.00"),
            maturity_date=date(2025, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, fd_repo, _, account_service = make_service(fd=fake_fd)

        frozen_today = date(2024, 6, 1)   # 1 year before maturity

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = frozen_today

            result = await service.close_fd_prematurely(fd_id=1, user_id=1)

        assert result["status"] == FDStatus.CLOSED.value
        assert "penalty_amount" in result
        assert "closure_amount" in result

    @pytest.mark.asyncio
    async def test_premature_closure_penalty_calculation(self):
        """
        Penalty = 1.5% of principal
        principal = 10000
        penalty   = 10000 * 0.015 = 150.00
        closure   = 10000 - 150   = 9850.00
        """
        fake_fd = make_fake_fd(
            principal_amount=Decimal("10000.00"),
            maturity_date=date(2025, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, *_ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)

            result = await service.close_fd_prematurely(fd_id=1, user_id=1)

        assert result["penalty_amount"] == pytest.approx(150.00)
        assert result["closure_amount"] == pytest.approx(9850.00)

    @pytest.mark.asyncio
    async def test_premature_closure_deposits_closure_amount_to_savings(self):
        """
        account_service.deposit() must be called with closure_amount (principal - penalty),
        NOT the full principal. User doesn't get their full money back.
        """
        fake_fd = make_fake_fd(
            principal_amount=Decimal("10000.00"),
            maturity_date=date(2025, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, _, _, account_service = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)

            await service.close_fd_prematurely(fd_id=1, user_id=1)

        account_service.deposit.assert_called_once()
        call_kwargs = account_service.deposit.call_args.kwargs
        # closure = 10000 - 150 = 9850
        assert call_kwargs["amount"] == pytest.approx(Decimal("9850.00"), rel=Decimal("0.001"))

    @pytest.mark.asyncio
    async def test_premature_closure_updates_fd_status_to_closed(self):
        """fd_repo.update() must be called with status=FDStatus.CLOSED"""
        fake_fd = make_fake_fd(
            maturity_date=date(2025, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, fd_repo, _, _ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)

            await service.close_fd_prematurely(fd_id=1, user_id=1)

        fd_repo.update.assert_called_once()
        update_data = fd_repo.update.call_args[0][1]   # second positional arg
        assert update_data["status"] == FDStatus.CLOSED

    @pytest.mark.asyncio
    async def test_premature_closure_raises_if_already_matured(self):
        """
        today >= maturity_date → FD already matured, use mature endpoint instead.
        Freeze today = day AFTER maturity to simulate this.
        """
        fake_fd = make_fake_fd(
            maturity_date=date(2024, 1, 1),   # matured in the past
            status=FDStatus.ACTIVE,
        )
        service, *_ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)  # after maturity

            with pytest.raises(BankingException) as exc_info:
                await service.close_fd_prematurely(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_premature_closure_raises_if_fd_not_active(self):
        """Already CLOSED FD → BankingException (can't close twice)"""
        fake_fd = make_fake_fd(status=FDStatus.CLOSED)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.close_fd_prematurely(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_premature_closure_raises_if_fd_not_found(self):
        """FD not in DB → BankingException 404"""
        service, *_ = make_service(fd=None)

        with pytest.raises(BankingException) as exc_info:
            await service.close_fd_prematurely(fd_id=999, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_premature_closure_raises_if_wrong_owner(self):
        """FD belongs to user 2, user 1 requests → BankingException 404"""
        fake_fd = make_fake_fd(user_id=2)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.close_fd_prematurely(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# CHECKPOINT D — withdraw_matured_fd()
#
# Mirror of premature closure but:
#   - Requires today >= maturity_date  (opposite condition)
#   - Credits full maturity_amount (no penalty)
#   - Sets status to MATURED (not CLOSED)
# ---------------------------------------------------------------------------

class TestWithdrawMaturedFD:

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_success(self):
        """
        Happy path: ACTIVE FD, today >= maturity_date.
        Freeze today = day of maturity.
        """
        fake_fd = make_fake_fd(
            principal_amount=Decimal("10000.00"),
            maturity_amount=Decimal("10650.00"),
            maturity_date=date(2024, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, *_ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)  # exactly on maturity

            result = await service.withdraw_matured_fd(fd_id=1, user_id=1)

        assert result["fd_id"] == 1

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_credits_full_maturity_amount(self):
        """
        No penalty on maturity. Full maturity_amount (principal + interest)
        must be deposited into the savings account.
        """
        fake_fd = make_fake_fd(
            maturity_amount=Decimal("10650.00"),
            maturity_date=date(2024, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, _, _, account_service = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)

            await service.withdraw_matured_fd(fd_id=1, user_id=1)

        account_service.deposit.assert_called_once()
        call_kwargs = account_service.deposit.call_args.kwargs
        assert call_kwargs["amount"] == Decimal("10650.00")  # full maturity, no penalty

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_updates_status_to_matured(self):
        """fd_repo.update() must set status=FDStatus.MATURED"""
        fake_fd = make_fake_fd(
            maturity_date=date(2024, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, fd_repo, _, _ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 1)

            await service.withdraw_matured_fd(fd_id=1, user_id=1)

        update_data = fd_repo.update.call_args[0][1]
        assert update_data["status"] == FDStatus.MATURED

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_raises_if_not_yet_matured(self):
        """
        today < maturity_date → FD not ready yet.
        Freeze today = 1 day BEFORE maturity.
        """
        fake_fd = make_fake_fd(
            maturity_date=date(2024, 6, 1),
            status=FDStatus.ACTIVE,
        )
        service, *_ = make_service(fd=fake_fd)

        with patch("app.services.fixed_deposit.date") as mock_date:
            mock_date.today.return_value = date(2024, 5, 31)  # 1 day before

            with pytest.raises(BankingException) as exc_info:
                await service.withdraw_matured_fd(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_raises_if_already_closed(self):
        """CLOSED FD cannot be withdrawn again → BankingException"""
        fake_fd = make_fake_fd(status=FDStatus.CLOSED)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.withdraw_matured_fd(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_raises_if_already_matured_status(self):
        """MATURED status FD cannot be withdrawn again → BankingException"""
        fake_fd = make_fake_fd(status=FDStatus.MATURED)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.withdraw_matured_fd(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_raises_if_not_found(self):
        """FD not in DB → BankingException 404"""
        service, *_ = make_service(fd=None)

        with pytest.raises(BankingException) as exc_info:
            await service.withdraw_matured_fd(fd_id=999, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_withdraw_matured_fd_raises_if_wrong_owner(self):
        """FD belongs to user 2 → BankingException 404"""
        fake_fd = make_fake_fd(user_id=2)
        service, *_ = make_service(fd=fake_fd)

        with pytest.raises(BankingException) as exc_info:
            await service.withdraw_matured_fd(fd_id=1, user_id=1)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# CHECKPOINT E — Interest rate lookup (all valid tenures)
# ---------------------------------------------------------------------------

class TestInterestRates:
    """
    Verify all 5 supported tenures map to the correct interest rate.
    These are the actual product rates — if someone changes them
    accidentally, these tests will catch it.
    """

    EXPECTED_RATES = {
        6:  Decimal("6.0"),
        12: Decimal("6.5"),
        24: Decimal("7.0"),
        36: Decimal("7.5"),
        60: Decimal("8.0"),
    }

    def test_all_supported_tenures_have_correct_rates(self):
        """Each tenure maps to the agreed interest rate"""
        for tenure, expected_rate in self.EXPECTED_RATES.items():
            assert FixedDepositService.INTEREST_RATES[tenure] == expected_rate

    def test_unsupported_tenure_not_in_rates(self):
        """Tenures like 7, 18, 48 are not supported"""
        for bad_tenure in [1, 7, 18, 48, 120]:
            assert bad_tenure not in FixedDepositService.INTEREST_RATES

    def test_premature_closure_penalty_is_correct(self):
        """Penalty rate must be 1.5% — if someone changes it, catch it here"""
        assert FixedDepositService.PREMATURE_CLOSURE_PENALTY == Decimal("1.5")