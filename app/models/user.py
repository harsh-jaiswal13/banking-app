from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class KYCStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    savings_accounts   = relationship("SavingsAccount", back_populates="user", cascade="all, delete-orphan")
    fixed_deposits     = relationship("FixedDeposit", back_populates="user", cascade="all, delete-orphan")
    stock_holdings     = relationship("StockHolding", back_populates="user", cascade="all, delete-orphan")
    stock_transactions = relationship("StockTransaction", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"