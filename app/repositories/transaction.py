from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Transaction repository operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Transaction, db)
    
    async def get_by_account(
        self, 
        account_id: int, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Transaction]:
        """Get transactions for an account"""
        query = select(Transaction).where(
            Transaction.account_id == account_id
        ).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_by_transaction_number(self, transaction_number: str) -> Optional[Transaction]:
        """Get transaction by transaction number"""
        query = select(Transaction).where(Transaction.transaction_number == transaction_number)
        result = await self.db.execute(query)
        return result.scalars().first()