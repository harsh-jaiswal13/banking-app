from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.fixed_deposit import FixedDeposit, FDStatus
from app.repositories.base import BaseRepository


class FixedDepositRepository(BaseRepository[FixedDeposit]):
    """Fixed Deposit repository operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(FixedDeposit, db)
    
    async def get_by_user(self, user_id: int) -> List[FixedDeposit]:
        """Get all FDs for a user"""
        query = select(FixedDeposit).where(
            FixedDeposit.user_id == user_id
        ).order_by(FixedDeposit.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_active_by_user(self, user_id: int) -> List[FixedDeposit]:
        """Get active FDs for a user"""
        query = select(FixedDeposit).where(
            FixedDeposit.user_id == user_id,
            FixedDeposit.status == FDStatus.ACTIVE
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_by_user_with_status(self, user_id: int, status: str = None) -> List[FixedDeposit]:
        """Get all FDs for a user, optionally filtered by status"""
        query = select(FixedDeposit).where(FixedDeposit.user_id == user_id)
        
        if status:
            query = query.where(FixedDeposit.status == status)
        
        query = query.order_by(FixedDeposit.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def fd_number_exists(self, fd_number: str) -> bool:
        """Check if FD number already exists"""
        query = select(FixedDeposit).where(FixedDeposit.fd_number == fd_number)
        result = await self.db.execute(query)
        return result.scalars().first() is not None
    
    async def get_by_fd_number(self, fd_number: str):
        """Get FD by FD number"""
        query = select(FixedDeposit).where(FixedDeposit.fd_number == fd_number)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_active_fds_count(self, user_id: int) -> int:
        """Get count of active FDs for a user"""
        query = select(func.count()).select_from(FixedDeposit).where(
            and_(
                FixedDeposit.user_id == user_id,
                FixedDeposit.status == FDStatus.ACTIVE
            )
        )
        result = await self.db.execute(query)
        return result.scalar()
    
    async def get_total_fd_amount(self, user_id: int) -> float:
        """Get total principal amount in active FDs"""
        query = select(func.sum(FixedDeposit.principal_amount)).where(
            and_(
                FixedDeposit.user_id == user_id,
                FixedDeposit.status == FDStatus.ACTIVE
            )
        )
        result = await self.db.execute(query)
        val = result.scalar()
        return float(val) if val else 0.0