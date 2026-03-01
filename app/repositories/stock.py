from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.stock import StockHolding, StockTransaction
from app.repositories.base import BaseRepository


class StockHoldingRepository(BaseRepository[StockHolding]):
    """Stock Holding repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(StockHolding, db)
    
    async def get_by_user_and_symbol(self, user_id: int, stock_symbol: str) -> Optional[StockHolding]:
        """Get holding by user and stock symbol"""
        query = select(StockHolding).where(
            StockHolding.user_id == user_id,
            StockHolding.stock_symbol == stock_symbol
        )
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_user(self, user_id: int) -> List[StockHolding]:
        """Get all holdings for a user"""
        query = select(StockHolding).where(
            StockHolding.user_id == user_id,
            StockHolding.quantity > 0
        )
        result = await self.db.execute(query)
        return result.scalars().all()


class StockTransactionRepository(BaseRepository[StockTransaction]):
    """Stock Transaction repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(StockTransaction, db)
    
    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 20) -> List[StockTransaction]:
        """Get stock transactions for a user"""
        query = select(StockTransaction).where(
            StockTransaction.user_id == user_id
        ).order_by(StockTransaction.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()