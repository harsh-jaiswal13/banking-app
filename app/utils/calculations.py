from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Tuple


def calculate_fd_maturity(
    principal: Decimal,
    interest_rate: Decimal,
    tenure_months: int
) -> Decimal:
    """
    Calculate FD maturity amount using compound interest
    Formula: A = P(1 + r/n)^(nt)
    Where:
        A = Maturity amount
        P = Principal
        r = Annual interest rate (decimal)
        n = Compounding frequency (4 for quarterly)
        t = Time in years
    """
    # Convert annual rate to decimal
    rate = interest_rate / Decimal('100')
    
    # Quarterly compounding
    n = Decimal('4')
    
    # Time in years
    t = Decimal(tenure_months) / Decimal('12')
    
    # Calculate maturity
    amount = principal * ((1 + rate / n) ** (n * t))
    
    # Round to 2 decimal places
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_maturity_date(tenure_months: int, start_date: date = None) -> date:
    """Calculate FD maturity date"""
    if start_date is None:
        start_date = date.today()
    
    # Add months
    month = start_date.month - 1 + tenure_months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    
    return date(year, month, day)


def calculate_premature_closure_amount(
    principal: Decimal,
    interest_rate: Decimal,
    tenure_months: int,
    months_elapsed: int,
    penalty_rate: Decimal = Decimal('1.0')
) -> Tuple[Decimal, Decimal]:
    """
    Calculate premature FD closure amount
    Returns: (closure_amount, penalty_amount)
    """
    # Calculate interest for elapsed period with penalty
    reduced_rate = interest_rate - penalty_rate
    reduced_rate = max(reduced_rate, Decimal('0'))  # Can't be negative
    
    # Calculate proportional interest
    rate = reduced_rate / Decimal('100')
    t = Decimal(months_elapsed) / Decimal('12')
    
    interest = principal * rate * t
    closure_amount = principal + interest
    
    # Calculate penalty (what was lost)
    normal_rate = interest_rate / Decimal('100')
    normal_interest = principal * normal_rate * t
    penalty = normal_interest - interest
    
    return (
        closure_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    )


def calculate_stock_transaction_fee(amount: Decimal, fee_percentage: Decimal = Decimal('0.1')) -> Decimal:
    """Calculate stock transaction fee"""
    fee = amount * (fee_percentage / Decimal('100'))
    return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_average_price(
    current_avg: Decimal,
    current_qty: int,
    new_price: Decimal,
    new_qty: int
) -> Decimal:
    """Calculate new average price after buying more stocks"""
    if current_qty + new_qty == 0:
        return Decimal('0')
    
    total_value = (current_avg * current_qty) + (new_price * new_qty)
    total_qty = current_qty + new_qty
    
    avg_price = total_value / total_qty
    return avg_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)