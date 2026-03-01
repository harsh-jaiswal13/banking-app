from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, BigInteger, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class TransactionType(str, enum.Enum):
    DEPOSIT         = "DEPOSIT"
    WITHDRAWAL      = "WITHDRAWAL"
    TRANSFER        = "TRANSFER"
    FD_CREATE       = "FD_CREATE"
    FD_MATURE       = "FD_MATURE"
    FD_CLOSE        = "FD_CLOSE"
    STOCK_BUY       = "STOCK_BUY"
    STOCK_SELL      = "STOCK_SELL"
    INTEREST_CREDIT = "INTEREST_CREDIT"


class TransactionStatus(str, enum.Enum):
    SUCCESS         = "SUCCESS"
    FAILED          = "FAILED"
    PENDING         = "PENDING"
    REVERSED        = "REVERSED"


class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    account_id = Column(BigInteger, ForeignKey("savings_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_number = Column(String(30), unique=True, nullable=False, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String(50), nullable=True)  # For linking to FD, Stock transactions
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.SUCCESS, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    account = relationship("SavingsAccount", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction {self.transaction_number}>"