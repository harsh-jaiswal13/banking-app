from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    """User-specific repository operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number"""
        query = select(User).where(User.phone == phone)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def email_exists(self, email: str) -> bool:
        """Check if email already exists"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalars().first() is not None
    
    async def phone_exists(self, phone: str) -> bool:
        """Check if phone already exists"""
        query = select(User).where(User.phone == phone)
        result = await self.db.execute(query)
        return result.scalars().first() is not None