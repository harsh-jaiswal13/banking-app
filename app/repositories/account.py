from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from app.models.savings_account import SavingsAccount, AccountStatus
from app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[SavingsAccount]):
    """Savings Account repository operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(SavingsAccount, db)
    
    async def get_by_account_number(self, account_number: str) -> Optional[SavingsAccount]:
        """Get account by account number"""
        query = select(SavingsAccount).where(SavingsAccount.account_number == account_number)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_user(self, user_id: int) -> List[SavingsAccount]:
        """Get all accounts for a user"""
        query = select(SavingsAccount).where(SavingsAccount.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_active_by_user(self, user_id: int) -> List[SavingsAccount]:
        """Get active accounts for a user"""
        query = select(SavingsAccount).where(
            SavingsAccount.user_id == user_id,
            SavingsAccount.status == AccountStatus.ACTIVE
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_balance(self, account_id: int, new_balance: Decimal) -> SavingsAccount:
        """Update account balance"""
        account = await self.get(account_id)
        if account:
            account.balance = new_balance
            await self.db.commit()
            await self.db.refresh(account)
        return account
    
    async def account_number_exists(self, account_number: str) -> bool:
        """Check if account number exists"""
        query = select(SavingsAccount).where(SavingsAccount.account_number == account_number)
        result = await self.db.execute(query)
        return result.scalars().first() is not None