from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, BigInteger, ForeignKey, Numeric, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum


class StockTransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class StockTransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class StockHolding(Base):
    __tablename__ = "stock_holdings"
    
    holding_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_symbol = Column(String(10), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    average_price = Column(Numeric(10, 2), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="stock_holdings")
    
    def __repr__(self):
        return f"<StockHolding {self.stock_symbol}: {self.quantity}>"


class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    
    transaction_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_number = Column(String(30), unique=True, nullable=False, index=True)
    
    stock_symbol = Column(String(10), nullable=False, index=True)
    transaction_type = Column(SQLEnum(StockTransactionType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    transaction_fee = Column(Numeric(10, 2), nullable=False, default=0.00)
    
    status = Column(SQLEnum(StockTransactionStatus), default=StockTransactionStatus.COMPLETED, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="stock_transactions")
    
    def __repr__(self):
        return f"<StockTransaction {self.transaction_number}>"