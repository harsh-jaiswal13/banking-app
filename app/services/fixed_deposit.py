from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from typing import List, Optional
from app.repositories.fixed_deposit import FixedDepositRepository
from app.repositories.account import AccountRepository
from app.repositories.transaction import TransactionRepository
from app.models.fixed_deposit import FDStatus
from app.models.transaction import TransactionType
from app.core.exceptions import (
    AccountNotFoundException,
    InsufficientBalanceException,
    BankingException
)
from app.utils.generators import generate_fd_number
from app.services.account import AccountService
class FixedDepositService:
    """Business logic for fixed deposit operations"""
    
    # Interest rates by tenure (in months)
    INTEREST_RATES = {
        6: Decimal('6.0'),
        12: Decimal('6.5'),
        24: Decimal('7.0'),
        36: Decimal('7.5'),
        60: Decimal('8.0')
    }
    
    PREMATURE_CLOSURE_PENALTY = Decimal('1.5')  # 1.5% penalty
    
    def __init__(
        self, 
        fixed_deposit_repo: FixedDepositRepository, 
        account_repo:       AccountRepository, 
        transaction_repo:   TransactionRepository,
        account_service:    AccountService
    ):
        self.fd_repo          = fixed_deposit_repo
        self.account_repo     = account_repo
        self.transaction_repo = transaction_repo
        self.account_service  = account_service
    
    async def create_fd(
        self, 
        user_id: int, 
        account_id: int, 
        amount: Decimal, 
        tenure_months: int
    ) -> dict:
        """Create a new fixed deposit"""
        # Validate tenure
        if tenure_months not in self.INTEREST_RATES:
            raise BankingException(
                f"Invalid tenure. Allowed values: {list(self.INTEREST_RATES.keys())}",
                status_code=400
            )
        
        # Validate amount
        if amount <= 0:
            raise BankingException("FD amount must be positive", status_code=400)
        
        # Get and validate account
        account = await self.account_repo.get(account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException()
        
        # Check sufficient balance
        if account.balance < amount:
            raise InsufficientBalanceException(
                f"Insufficient balance. Available: {account.balance}, Required: {amount}"
            )
        
        # Calculate interest rate
        interest_rate = self.INTEREST_RATES[tenure_months]
        
        # Calculate maturity amount (simple interest)
        # Formula: Maturity = Principal * (1 + (rate * tenure_years))
        tenure_years = Decimal(tenure_months) / Decimal('12')
        maturity_amount = amount * (Decimal('1') + (interest_rate / Decimal('100') * tenure_years))
        
        # Calculate maturity date
        maturity_date = date.today() + timedelta(days=tenure_months * 30)
        
        # Generate FD number
        fd_number = generate_fd_number()
        while await self.fd_repo.fd_number_exists(fd_number):
            fd_number = generate_fd_number()
        
        # Deduct from savings account
        await self.account_service.withdraw(
            account_id=account_id,
            user_id=user_id,
            amount=amount,
            description=f"FD Creation - {fd_number}"
        )
        
        # Create FD
        fd_data = {
            "user_id": user_id,
            "savings_account_id": account_id,
            "fd_number": fd_number,
            "principal_amount": amount,
            "interest_rate": interest_rate,
            "tenure_months": tenure_months,
            "maturity_amount": maturity_amount,
            "maturity_date": maturity_date,
            "status": FDStatus.ACTIVE
        }
        
        fd = await self.fd_repo.create(fd_data)
        
        return self._fd_to_dict(fd)
    
    async def get_fd(self, fd_id: int, user_id: int) -> dict:
        """Get FD details"""
        fd = await self.fd_repo.get(fd_id)
        
        if not fd or fd.user_id != user_id:
            raise BankingException("Fixed Deposit not found", status_code=404)
        
        return self._fd_to_dict(fd)
    
    async def get_all_user_fds(
        self, 
        user_id: int, 
        status: Optional[str] = None
    ) -> List[dict]:
        """Get all FDs for a user with optional status filter"""
        fds = await self.fd_repo.get_by_user_with_status(user_id, status)
        return [self._fd_to_dict(fd) for fd in fds]
    
    async def close_fd_prematurely(self, fd_id: int, user_id: int) -> dict:
        """Close FD before maturity with penalty"""
        fd = await self.fd_repo.get(fd_id)
        
        if not fd or fd.user_id != user_id:
            raise BankingException("Fixed Deposit not found", status_code=404)
        
        if fd.status != FDStatus.ACTIVE:
            raise BankingException(
                f"Cannot close FD. Current status: {fd.status.value}",
                status_code=400
            )
        
        # Check if already matured
        if date.today() >= fd.maturity_date:
            raise BankingException(
                "FD has already matured. Use mature endpoint instead.",
                status_code=400
            )
        
        # Calculate penalty
        penalty_amount = fd.principal_amount * (self.PREMATURE_CLOSURE_PENALTY / Decimal('100'))
        
        # Calculate closure amount (principal - penalty)
        closure_amount = fd.principal_amount - penalty_amount
        
        # Update FD status
        update_data = {
            "status": FDStatus.CLOSED,
            "closed_at": datetime.now(),
            "closure_amount": closure_amount,
            "penalty_amount": penalty_amount
        }
        await self.fd_repo.update(fd, update_data)
        
        # Credit to savings account
        await self.account_service.deposit(
            account_id=fd.savings_account_id,
            user_id=user_id,
            amount=closure_amount,
            description=f"FD Premature Closure - {fd.fd_number} (Penalty: {penalty_amount})"
        )
        
        return {
            "fd_id": fd.fd_id,
            "fd_number": fd.fd_number,
            "principal_amount": float(fd.principal_amount),
            "closure_amount": float(closure_amount),
            "penalty_amount": float(penalty_amount),
            "status": FDStatus.CLOSED.value,
            "closed_at": fd.closed_at
        }
    
    async def withdraw_matured_fd(self, fd_id: int, user_id: int) -> dict:
        """Withdraw matured FD amount"""
        fd = await self.fd_repo.get(fd_id)
        
        if not fd or fd.user_id != user_id:
            raise BankingException("Fixed Deposit not found", status_code=404)
        
        if fd.status != FDStatus.ACTIVE:
            raise BankingException(
                f"Cannot withdraw FD. Current status: {fd.status.value}",
                status_code=400
            )
        
        # Check if matured
        if date.today() < fd.maturity_date:
            raise BankingException(
                f"FD has not matured yet. Maturity date: {fd.maturity_date}",
                status_code=400
            )
        
        # Update FD status
        update_data = {
            "status": FDStatus.MATURED,
            "closed_at": datetime.now()
        }
        await self.fd_repo.update(fd, update_data)
        
        # Credit to savings account
        await self.account_service.deposit(
            account_id=fd.savings_account_id,
            user_id=user_id,
            amount=fd.maturity_amount,
            description=f"FD Maturity Credit - {fd.fd_number}"
        )
        
        return self._fd_to_dict(fd)

    def _fd_to_dict(self, fd) -> dict:
        """Convert FD model to dictionary"""
        result = {
            "fd_id": fd.fd_id,
            "fd_number": fd.fd_number,
            "principal_amount": float(fd.principal_amount),
            "interest_rate": float(fd.interest_rate),
            "tenure_months": fd.tenure_months,
            "maturity_amount": float(fd.maturity_amount),
            "maturity_date": fd.maturity_date,
            "status": fd.status.value,
            "created_at": fd.created_at
        }
        
        # Add closure info if applicable
        if fd.status == FDStatus.CLOSED and fd.closed_at:
            result.update({
                "closed_at": fd.closed_at,
                "closure_amount": float(fd.closure_amount) if fd.closure_amount else None,
                "penalty_amount": float(fd.penalty_amount) if fd.penalty_amount else None
            })
        
        return result
