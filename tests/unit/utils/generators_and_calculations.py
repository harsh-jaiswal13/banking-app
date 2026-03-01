"""
Tests for app/utils/calculations.py and app/utils/generators.py

These are pure functions with no DB dependency — no fixtures needed.

calculations.py:
    calculate_fd_maturity()              — compound interest maturity amount
    calculate_maturity_date()            — FD maturity date from tenure
    calculate_premature_closure_amount() — closure + penalty on early exit
    calculate_stock_transaction_fee()    — brokerage fee on stock trades
    calculate_average_price()            — weighted average after buying more

generators.py:
    generate_account_number()            — SA + timestamp + 4 digits
    generate_fd_number()                 — FD + timestamp + 4 digits
    generate_transaction_number()        — TXN + timestamp + 6 alphanumeric
    generate_stock_transaction_number()  — STK + timestamp + 6 alphanumeric
"""

import re
import time
import pytest
from decimal import Decimal
from datetime import date

from app.utils.calculations import (
    calculate_fd_maturity,
    calculate_maturity_date,
    calculate_premature_closure_amount,
    calculate_stock_transaction_fee,
    calculate_average_price,
)
from app.utils.generators import (
    generate_account_number,
    generate_fd_number,
    generate_transaction_number,
    generate_stock_transaction_number,
)


# ===========================================================================
# calculate_fd_maturity()
# ===========================================================================

class TestCalculateFdMaturity:

    def test_basic_compound_interest(self):
        """
        P=10000, r=7%, 12 months, quarterly compounding.
        A = 10000 * (1 + 0.07/4)^(4*1) = 10000 * (1.0175)^4 ≈ 10718.59
        """
        result = calculate_fd_maturity(
            principal=Decimal("10000"),
            interest_rate=Decimal("7"),
            tenure_months=12,
        )
        assert result == Decimal("10718.59")

    def test_returns_decimal(self):
        """Return type must be Decimal, not float."""
        result = calculate_fd_maturity(Decimal("5000"), Decimal("6"), 6)
        assert isinstance(result, Decimal)

    def test_result_rounded_to_two_decimal_places(self):
        """Result must always have exactly 2 decimal places."""
        result = calculate_fd_maturity(Decimal("12345.67"), Decimal("8.5"), 18)
        assert result == result.quantize(Decimal("0.01"))

    def test_higher_rate_yields_higher_maturity(self):
        """All else equal, a higher interest rate must produce more maturity."""
        low = calculate_fd_maturity(Decimal("10000"), Decimal("5"), 12)
        high = calculate_fd_maturity(Decimal("10000"), Decimal("9"), 12)
        assert high > low

    def test_longer_tenure_yields_higher_maturity(self):
        """All else equal, longer tenure must produce more maturity."""
        short = calculate_fd_maturity(Decimal("10000"), Decimal("7"), 6)
        long_ = calculate_fd_maturity(Decimal("10000"), Decimal("7"), 24)
        assert long_ > short

    def test_larger_principal_yields_higher_maturity(self):
        """All else equal, larger principal must produce more maturity."""
        small = calculate_fd_maturity(Decimal("5000"), Decimal("7"), 12)
        large = calculate_fd_maturity(Decimal("50000"), Decimal("7"), 12)
        assert large > small

    def test_maturity_always_greater_than_principal(self):
        """With any positive rate and tenure, maturity must exceed principal."""
        result = calculate_fd_maturity(Decimal("10000"), Decimal("0.01"), 1)
        assert result > Decimal("10000")

    def test_short_tenure_one_month(self):
        """Single-month tenure must still return a sensible result above principal."""
        result = calculate_fd_maturity(Decimal("10000"), Decimal("6"), 1)
        assert result > Decimal("10000")

    def test_large_principal(self):
        """Must handle large principal amounts without overflow or precision loss."""
        result = calculate_fd_maturity(Decimal("10000000"), Decimal("7"), 12)
        assert result > Decimal("10000000")
        assert isinstance(result, Decimal)


# ===========================================================================
# calculate_maturity_date()
# ===========================================================================

class TestCalculateMaturityDate:

    def test_adds_correct_number_of_months(self):
        """12-month tenure from Jan 1 → Jan 1 next year."""
        start = date(2024, 1, 1)
        result = calculate_maturity_date(12, start_date=start)
        assert result == date(2025, 1, 1)

    def test_6_month_tenure(self):
        """6-month tenure from Jan 1 → Jul 1."""
        start = date(2024, 1, 1)
        result = calculate_maturity_date(6, start_date=start)
        assert result == date(2024, 7, 1)

    def test_3_month_tenure(self):
        """3-month tenure from Jan 1 → Apr 1."""
        start = date(2024, 1, 1)
        result = calculate_maturity_date(3, start_date=start)
        assert result == date(2024, 4, 1)

    def test_crosses_year_boundary(self):
        """Tenure that spills into the next year must advance the year correctly."""
        start = date(2024, 10, 15)
        result = calculate_maturity_date(6, start_date=start)
        assert result == date(2025, 4, 15)

    def test_end_of_month_clamping_feb(self):
        """
        Jan 31 + 1 month → Feb 28/29 (clamped — Feb has no 31st).
        Must not raise and must return a valid date.
        """
        start = date(2024, 1, 31)
        result = calculate_maturity_date(1, start_date=start)
        assert result.month == 2
        assert result.year == 2024
        assert result.day <= 29  # 2024 is a leap year

    def test_end_of_month_clamping_non_leap(self):
        """Jan 31 + 1 month in a non-leap year → Feb 28."""
        start = date(2023, 1, 31)
        result = calculate_maturity_date(1, start_date=start)
        assert result == date(2023, 2, 28)

    def test_defaults_to_today_when_no_start_date(self):
        """Called with no start_date must use today as the base."""
        today = date.today()
        result = calculate_maturity_date(12)
        assert result.year == today.year + 1 or (
            result.month == today.month and result.year == today.year + 1
        )
        # Simpler: just check it's in the future
        assert result > today

    def test_returns_date_object(self):
        """Return type must be datetime.date."""
        result = calculate_maturity_date(6, start_date=date(2024, 1, 1))
        assert isinstance(result, date)

    def test_24_month_tenure(self):
        """24-month tenure → exactly 2 years later."""
        start = date(2024, 3, 15)
        result = calculate_maturity_date(24, start_date=start)
        assert result == date(2026, 3, 15)


# ===========================================================================
# calculate_premature_closure_amount()
# ===========================================================================

class TestCalculatePrematureClosureAmount:

    def test_returns_tuple_of_two_decimals(self):
        """Must return a 2-tuple of Decimals."""
        result = calculate_premature_closure_amount(
            principal=Decimal("10000"),
            interest_rate=Decimal("7"),
            tenure_months=12,
            months_elapsed=6,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, Decimal) for v in result)

    def test_closure_amount_greater_than_principal(self):
        """Even with penalty, customer should get back at least the principal."""
        closure, penalty = calculate_premature_closure_amount(
            principal=Decimal("10000"),
            interest_rate=Decimal("7"),
            tenure_months=12,
            months_elapsed=6,
        )
        assert closure >= Decimal("10000")

    def test_penalty_is_non_negative(self):
        """Penalty must never be negative."""
        _, penalty = calculate_premature_closure_amount(
            principal=Decimal("10000"),
            interest_rate=Decimal("7"),
            tenure_months=12,
            months_elapsed=6,
        )
        assert penalty >= Decimal("0")

    def test_both_values_rounded_to_two_decimal_places(self):
        """Both returned values must have exactly 2 decimal places."""
        closure, penalty = calculate_premature_closure_amount(
            principal=Decimal("10000"),
            interest_rate=Decimal("7"),
            tenure_months=12,
            months_elapsed=6,
        )
        assert closure == closure.quantize(Decimal("0.01"))
        assert penalty == penalty.quantize(Decimal("0.01"))

    def test_higher_penalty_rate_reduces_closure_amount(self):
        """A higher penalty rate must result in a lower closure amount."""
        closure_low, _ = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 12, 6, penalty_rate=Decimal("0.5")
        )
        closure_high, _ = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 12, 6, penalty_rate=Decimal("2.0")
        )
        assert closure_low > closure_high

    def test_rate_cannot_go_negative(self):
        """
        If penalty_rate > interest_rate, the effective rate is clamped to 0.
        Customer still gets back at least the principal.
        """
        closure, penalty = calculate_premature_closure_amount(
            principal=Decimal("10000"),
            interest_rate=Decimal("2"),
            tenure_months=12,
            months_elapsed=6,
            penalty_rate=Decimal("5"),  # exceeds interest rate
        )
        assert closure >= Decimal("10000")

    def test_default_penalty_rate_is_one_percent(self):
        """Default penalty_rate=1.0 must be applied when not specified."""
        result_default = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 12, 6
        )
        result_explicit = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 12, 6, penalty_rate=Decimal("1.0")
        )
        assert result_default == result_explicit

    def test_longer_elapsed_time_yields_more_interest(self):
        """More time elapsed → more interest earned (even after penalty)."""
        closure_short, _ = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 24, 3
        )
        closure_long, _ = calculate_premature_closure_amount(
            Decimal("10000"), Decimal("7"), 24, 12
        )
        assert closure_long > closure_short


# ===========================================================================
# calculate_stock_transaction_fee()
# ===========================================================================

class TestCalculateStockTransactionFee:

    def test_default_fee_percentage(self):
        """Default fee is 0.1% of the transaction amount."""
        fee = calculate_stock_transaction_fee(Decimal("10000"))
        assert fee == Decimal("10.00")

    def test_custom_fee_percentage(self):
        """Custom fee percentage must be applied correctly."""
        fee = calculate_stock_transaction_fee(Decimal("10000"), Decimal("0.5"))
        assert fee == Decimal("50.00")

    def test_returns_decimal(self):
        """Return type must be Decimal."""
        fee = calculate_stock_transaction_fee(Decimal("5000"))
        assert isinstance(fee, Decimal)

    def test_result_rounded_to_two_decimal_places(self):
        """Fee must always be rounded to 2 decimal places."""
        fee = calculate_stock_transaction_fee(Decimal("333.33"), Decimal("0.1"))
        assert fee == fee.quantize(Decimal("0.01"))

    def test_higher_amount_yields_higher_fee(self):
        """Larger transaction amount must result in larger fee."""
        fee_small = calculate_stock_transaction_fee(Decimal("1000"))
        fee_large = calculate_stock_transaction_fee(Decimal("100000"))
        assert fee_large > fee_small

    def test_higher_percentage_yields_higher_fee(self):
        """Higher fee percentage on the same amount must yield larger fee."""
        fee_low = calculate_stock_transaction_fee(Decimal("10000"), Decimal("0.1"))
        fee_high = calculate_stock_transaction_fee(Decimal("10000"), Decimal("0.5"))
        assert fee_high > fee_low

    def test_zero_amount_yields_zero_fee(self):
        """Zero transaction amount → zero fee."""
        fee = calculate_stock_transaction_fee(Decimal("0"))
        assert fee == Decimal("0.00")

    def test_small_amount_rounds_correctly(self):
        """Tiny amounts that produce sub-cent fees must round to 0.00."""
        fee = calculate_stock_transaction_fee(Decimal("1.00"), Decimal("0.1"))
        # 0.1% of 1.00 = 0.001 → rounds to 0.00
        assert fee == Decimal("0.00")


# ===========================================================================
# calculate_average_price()
# ===========================================================================

class TestCalculateAveragePrice:

    def test_basic_weighted_average(self):
        """
        10 shares @ 100 + 10 shares @ 200 = 20 shares @ 150 average.
        """
        result = calculate_average_price(
            current_avg=Decimal("100"),
            current_qty=10,
            new_price=Decimal("200"),
            new_qty=10,
        )
        assert result == Decimal("150.00")

    def test_buying_at_same_price_keeps_average(self):
        """Buying more at the current average price must not change the average."""
        result = calculate_average_price(
            current_avg=Decimal("150"),
            current_qty=10,
            new_price=Decimal("150"),
            new_qty=5,
        )
        assert result == Decimal("150.00")

    def test_buying_lower_brings_average_down(self):
        """Buying at a lower price must reduce the average."""
        result = calculate_average_price(
            current_avg=Decimal("200"),
            current_qty=10,
            new_price=Decimal("100"),
            new_qty=10,
        )
        assert result < Decimal("200")

    def test_buying_higher_brings_average_up(self):
        """Buying at a higher price must raise the average."""
        result = calculate_average_price(
            current_avg=Decimal("100"),
            current_qty=10,
            new_price=Decimal("200"),
            new_qty=5,
        )
        assert result > Decimal("100")

    def test_returns_decimal(self):
        """Return type must be Decimal."""
        result = calculate_average_price(Decimal("100"), 10, Decimal("120"), 5)
        assert isinstance(result, Decimal)

    def test_result_rounded_to_two_decimal_places(self):
        """Result must always have exactly 2 decimal places."""
        result = calculate_average_price(Decimal("100"), 3, Decimal("200"), 3)
        assert result == result.quantize(Decimal("0.01"))

    def test_zero_total_quantity_returns_zero(self):
        """
        current_qty=0 and new_qty=0 → return Decimal('0') to avoid division
        by zero. This is the guard clause in the implementation.
        """
        result = calculate_average_price(Decimal("100"), 0, Decimal("200"), 0)
        assert result == Decimal("0")

    def test_first_purchase_zero_current_qty(self):
        """
        First-ever purchase: current_qty=0, current_avg irrelevant.
        Average must equal new_price.
        """
        result = calculate_average_price(
            current_avg=Decimal("0"),
            current_qty=0,
            new_price=Decimal("350"),
            new_qty=5,
        )
        assert result == Decimal("350.00")

    def test_unequal_quantities(self):
        """Weighted average with unequal quantities must be correct."""
        # 1 share @ 300 + 3 shares @ 100 = 4 shares @ 150
        result = calculate_average_price(
            current_avg=Decimal("300"),
            current_qty=1,
            new_price=Decimal("100"),
            new_qty=3,
        )
        assert result == Decimal("150.00")


# ===========================================================================
# generate_account_number()
# ===========================================================================

class TestGenerateAccountNumber:

    def test_starts_with_sa_prefix(self):
        """Account number must start with 'SA'."""
        assert generate_account_number().startswith("SA")

    def test_correct_total_length(self):
        """SA (2) + 12 timestamp digits + 4 random digits = 18 chars."""
        assert len(generate_account_number()) == 18

    def test_only_digits_after_prefix(self):
        """Characters after the 'SA' prefix must all be digits."""
        number = generate_account_number()
        assert number[2:].isdigit()

    def test_generates_unique_numbers(self):
        """Two calls in quick succession must produce different numbers."""
        numbers = {generate_account_number() for _ in range(20)}
        # With timestamp + 4 random digits the collision probability is negligible
        assert len(numbers) > 1

    def test_format_matches_pattern(self):
        """Must match pattern SA followed by exactly 16 digits."""
        pattern = re.compile(r"^SA\d{16}$")
        assert pattern.match(generate_account_number())


# ===========================================================================
# generate_fd_number()
# ===========================================================================

class TestGenerateFdNumber:

    def test_starts_with_fd_prefix(self):
        """FD number must start with 'FD'."""
        assert generate_fd_number().startswith("FD")

    def test_correct_total_length(self):
        """FD (2) + 12 timestamp digits + 4 random digits = 18 chars."""
        assert len(generate_fd_number()) == 18

    def test_only_digits_after_prefix(self):
        """Characters after the 'FD' prefix must all be digits."""
        number = generate_fd_number()
        assert number[2:].isdigit()

    def test_generates_unique_numbers(self):
        """Two calls must produce different numbers."""
        numbers = {generate_fd_number() for _ in range(20)}
        assert len(numbers) > 1

    def test_format_matches_pattern(self):
        """Must match pattern FD followed by exactly 16 digits."""
        pattern = re.compile(r"^FD\d{16}$")
        assert pattern.match(generate_fd_number())


# ===========================================================================
# generate_transaction_number()
# ===========================================================================

class TestGenerateTransactionNumber:

    def test_starts_with_txn_prefix(self):
        """Transaction number must start with 'TXN'."""
        assert generate_transaction_number().startswith("TXN")

    def test_correct_total_length(self):
        """TXN (3) + 10 timestamp digits + 6 random chars = 19 chars."""
        assert len(generate_transaction_number()) == 19

    def test_alphanumeric_after_prefix(self):
        """Characters after 'TXN' must be alphanumeric (uppercase + digits)."""
        number = generate_transaction_number()
        suffix = number[3:]
        assert suffix.isalnum()
        assert suffix == suffix.upper()

    def test_generates_unique_numbers(self):
        """Two calls must produce different numbers."""
        numbers = {generate_transaction_number() for _ in range(20)}
        assert len(numbers) > 1

    def test_format_matches_pattern(self):
        """Must match TXN + 10 digits + 6 uppercase alphanumeric."""
        pattern = re.compile(r"^TXN\d{10}[A-Z0-9]{6}$")
        assert pattern.match(generate_transaction_number())


# ===========================================================================
# generate_stock_transaction_number()
# ===========================================================================

class TestGenerateStockTransactionNumber:

    def test_starts_with_stk_prefix(self):
        """Stock transaction number must start with 'STK'."""
        assert generate_stock_transaction_number().startswith("STK")

    def test_correct_total_length(self):
        """STK (3) + 10 timestamp digits + 6 random chars = 19 chars."""
        assert len(generate_stock_transaction_number()) == 19

    def test_alphanumeric_after_prefix(self):
        """Characters after 'STK' must be alphanumeric (uppercase + digits)."""
        number = generate_stock_transaction_number()
        suffix = number[3:]
        assert suffix.isalnum()
        assert suffix == suffix.upper()

    def test_generates_unique_numbers(self):
        """Two calls must produce different numbers."""
        numbers = {generate_stock_transaction_number() for _ in range(20)}
        assert len(numbers) > 1

    def test_format_matches_pattern(self):
        """Must match STK + 10 digits + 6 uppercase alphanumeric."""
        pattern = re.compile(r"^STK\d{10}[A-Z0-9]{6}$")
        assert pattern.match(generate_stock_transaction_number())

    def test_distinct_from_transaction_number(self):
        """Stock transaction numbers must be distinguishable from regular ones by prefix."""
        stock_num = generate_stock_transaction_number()
        tx_num = generate_transaction_number()
        assert stock_num.startswith("STK")
        assert tx_num.startswith("TXN")