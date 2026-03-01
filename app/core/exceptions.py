from fastapi import HTTPException, status


class BankingException(HTTPException):
    """Base exception for banking operations"""
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class UserNotFoundException(BankingException):
    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class UserAlreadyExistsException(BankingException):
    def __init__(self, detail: str = "User already exists"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class AccountNotFoundException(BankingException):
    def __init__(self, detail: str = "Account not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class InsufficientBalanceException(BankingException):
    def __init__(self, detail: str = "Insufficient balance"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class InvalidAmountException(BankingException):
    def __init__(self, detail: str = "Invalid amount"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class InvalidCredentialsException(BankingException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class UnauthorizedException(BankingException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(BankingException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class FixedDepositNotFoundException(BankingException):
    def __init__(self, detail: str = "Fixed deposit not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class FixedDepositAlreadyClosedException(BankingException):
    def __init__(self, detail: str = "Fixed deposit already closed"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class StockNotFoundException(BankingException):
    def __init__(self, detail: str = "Stock holding not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class InsufficientStockException(BankingException):
    def __init__(self, detail: str = "Insufficient stock quantity"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class AccountInactiveException(BankingException):
    def __init__(self, detail: str = "Account is inactive"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)