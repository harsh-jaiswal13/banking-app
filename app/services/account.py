from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple
from app.repositories.account import AccountRepository
from app.repositories.transaction import TransactionRepository
from app.models.savings_account import AccountStatus
from app.models.transaction import TransactionType, TransactionStatus
from app.core.exceptions import (
    AccountNotFoundException, 
    InvalidAmountException,
    InsufficientBalanceException,
    AccountInactiveException
)
from app.utils.generators import generate_account_number, generate_transaction_number
from app.config import settings


class AccountService:
    """Business logic for savings account operations"""
    
    def __init__(self, account_repo: AccountRepository, transaction_repo: TransactionRepository):
        self.account_repo = account_repo
        self.transaction_repo = transaction_repo
    
    async def create_account(self, user_id: int, account_type: str) -> dict:
        """Create a new savings account"""
        # Generate unique account number
        account_number = generate_account_number()
        
        # Ensure uniqueness
        while await self.account_repo.account_number_exists(account_number):
            account_number = generate_account_number()
        
        account_data = {
            "user_id": user_id,
            "account_number": account_number,
            "balance": Decimal('0.00'),
            "account_type": account_type,
            "interest_rate": Decimal(str(settings.SAVINGS_INTEREST_RATE)),
            "status": AccountStatus.ACTIVE
        }
        
        account = await self.account_repo.create(account_data)
        
        return {
            "account_id": account.account_id,
            "account_number": account.account_number,
            "balance": float(account.balance),
            "account_type": account.account_type.value,
            "interest_rate": float(account.interest_rate),
            "status": account.status.value,
            "created_at": account.created_at
        }
    
    async def get_account(self, account_id: int, user_id: int) -> dict:
        """Get account details"""
        account = await self.account_repo.get(account_id)
        
        if not account:
            raise AccountNotFoundException()
        
        # Verify ownership
        if account.user_id != user_id:
            raise AccountNotFoundException()
        
        return self._account_to_dict(account)
    
    async def deposit(self, account_id: int, user_id: int, amount: Decimal, description: str = None) -> dict:
        """Deposit money into account"""
        # Validate amount
        if amount <= 0:
            raise InvalidAmountException("Deposit amount must be positive")
        
        # Get account
        account = await self.account_repo.get(account_id)
        if not account:
            raise AccountNotFoundException()
        
        # Verify ownership
        if account.user_id != user_id:
            raise AccountNotFoundException()
        
        # Check if account is active
        if account.status != AccountStatus.ACTIVE:
            raise AccountInactiveException()
        
        # Update balance
        new_balance = account.balance + amount
        await self.account_repo.update_balance(account_id, new_balance)
        
        # Record transaction
        transaction = await self._record_transaction(
            account_id=account_id,
            transaction_type=TransactionType.DEPOSIT,
            amount=amount,
            balance_after=new_balance,
            description=description or "Deposit"
        )
        
        return {
            "transaction_id": transaction.transaction_id,
            "transaction_number": transaction.transaction_number,
            "amount": float(amount),
            "balance_after": float(new_balance),
            "timestamp": transaction.created_at
        }
    
    async def withdraw(self, account_id: int, user_id: int, amount: Decimal, description: str = None) -> dict:
        """Withdraw money from account"""
        # Validate amount
        if amount <= 0:
            raise InvalidAmountException("Withdrawal amount must be positive")
        
        # Get account
        account = await self.account_repo.get(account_id)
        if not account:
            raise AccountNotFoundException()
        
        # Verify ownership
        if account.user_id != user_id:
            raise AccountNotFoundException()
        
        # Check if account is active
        if account.status != AccountStatus.ACTIVE:
            raise AccountInactiveException()
        
        # Check sufficient balance
        if account.balance < amount:
            raise InsufficientBalanceException(
                f"Insufficient balance. Available: {account.balance}, Requested: {amount}"
            )
        
        # Update balance
        new_balance = account.balance - amount
        await self.account_repo.update_balance(account_id, new_balance)
        
        # Record transaction
        transaction = await self._record_transaction(
            account_id=account_id,
            transaction_type=TransactionType.WITHDRAWAL,
            amount=amount,
            balance_after=new_balance,
            description=description or "Withdrawal"
        )
        
        return {
            "transaction_id": transaction.transaction_id,
            "transaction_number": transaction.transaction_number,
            "amount": float(amount),
            "balance_after": float(new_balance),
            "timestamp": transaction.created_at
        }
    
    async def get_balance(self, account_id: int, user_id: int) -> dict:
        """Get account balance"""
        account = await self.account_repo.get(account_id)
        
        if not account or account.user_id != user_id:
            raise AccountNotFoundException()
        
        return {
            "account_id": account.account_id,
            "account_number": account.account_number,
            "balance": float(account.balance),
            "status": account.status.value
        }
    
    async def get_transactions(
        self, 
        account_id: int, 
        user_id: int, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[dict], int]:
        """Get transaction history with pagination"""
        account = await self.account_repo.get(account_id)
        
        if not account or account.user_id != user_id:
            raise AccountNotFoundException()
        
        skip = (page - 1) * page_size
        transactions = await self.transaction_repo.get_by_account(
            account_id, 
            skip=skip, 
            limit=page_size
        )
        
        total = await self.transaction_repo.count(filters={"account_id": account_id})
        
        transaction_list = [
            {
                "transaction_id": t.transaction_id,
                "transaction_number": t.transaction_number,
                "type": t.transaction_type.value,
                "amount": float(t.amount),
                "balance_after": float(t.balance_after),
                "description": t.description,
                "status": t.status.value,
                "timestamp": t.created_at
            }
            for t in transactions
        ]
        
        return transaction_list, total
    
    async def _record_transaction(
        self,
        account_id: int,
        transaction_type: TransactionType,
        amount: Decimal,
        balance_after: Decimal,
        description: str = None,
        reference_id: str = None
    ):
        """Internal method to record transaction"""
        transaction_number = generate_transaction_number()
        
        transaction_data = {
            "account_id": account_id,
            "transaction_number": transaction_number,
            "transaction_type": transaction_type,
            "amount": amount,
            "balance_after": balance_after,
            "description": description,
            "reference_id": reference_id,
            "status": TransactionStatus.SUCCESS
        }
        
        return await self.transaction_repo.create(transaction_data)
    
    def _account_to_dict(self, account) -> dict:
        """Convert account model to dictionary"""
        return {
            "account_id": account.account_id,
            "account_number": account.account_number,
            "balance": float(account.balance),
            "account_type": account.account_type.value,
            "interest_rate": float(account.interest_rate),
            "status": account.status.value,
            "created_at": account.created_at,
            "updated_at": account.updated_at
        }