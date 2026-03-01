import random
import string
from datetime import datetime


def generate_account_number() -> str:
    """
    Generate unique savings account number
    Format: SA + timestamp + 4 random digits
    Example: SA170614278912345678
    """
    timestamp = str(int(datetime.now().timestamp() * 1000))
    random_digits = ''.join(random.choices(string.digits, k=4))
    return f"SA{timestamp[-12:]}{random_digits}"


def generate_fd_number() -> str:
    """
    Generate unique fixed deposit number
    Format: FD + timestamp + 4 random digits
    """
    timestamp = str(int(datetime.now().timestamp() * 1000))
    random_digits = ''.join(random.choices(string.digits, k=4))
    return f"FD{timestamp[-12:]}{random_digits}"


def generate_transaction_number() -> str:
    """
    Generate unique transaction number
    Format: TXN + timestamp + 6 random alphanumeric
    """
    timestamp = str(int(datetime.now().timestamp() * 1000))
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TXN{timestamp[-10:]}{random_chars}"


def generate_stock_transaction_number() -> str:
    """
    Generate unique stock transaction number
    Format: STK + timestamp + 6 random alphanumeric
    """
    timestamp = str(int(datetime.now().timestamp() * 1000))
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"STK{timestamp[-10:]}{random_chars}"