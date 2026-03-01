from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, BigInteger, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class AccountType(str, enum.Enum):
    REGULAR = "REGULAR"
    SALARY = "SALARY"
    PREMIUM = "PREMIUM"


class SavingsAccount(Base):
    __tablename__ = "savings_accounts"
    
    account_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    account_number = Column(String(20), unique=True, nullable=False, index=True)
    balance = Column(Numeric(15, 2), default=0.00, nullable=False)
    account_type = Column(SQLEnum(AccountType), default=AccountType.REGULAR, nullable=False)
    interest_rate = Column(Numeric(5, 2), default=4.00, nullable=False)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="savings_accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    fixed_deposits = relationship("FixedDeposit", back_populates="savings_account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SavingsAccount {self.account_number}>"