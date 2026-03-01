from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, BigInteger, ForeignKey, Numeric, Integer, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class FDStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    CLOSED = "CLOSED"


class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"
    
    fd_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    savings_account_id = Column(BigInteger, ForeignKey("savings_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    fd_number = Column(String(20), unique=True, nullable=False, index=True)
    
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    maturity_amount = Column(Numeric(15, 2), nullable=False)
    maturity_date = Column(Date, nullable=False, index=True)
    
    status = Column(SQLEnum(FDStatus), default=FDStatus.ACTIVE, nullable=False, index=True)
    
    # For premature closure
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closure_amount = Column(Numeric(15, 2), nullable=True)
    penalty_amount = Column(Numeric(15, 2), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="fixed_deposits")
    savings_account = relationship("SavingsAccount", back_populates="fixed_deposits")
    
    def __repr__(self):
        return f"<FixedDeposit {self.fd_number}>"