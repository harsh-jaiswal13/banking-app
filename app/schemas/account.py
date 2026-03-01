
# app/schemas/account.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional


class AccountCreate(BaseModel):
    """Schema for creating savings account"""
    account_type: str = Field(default="REGULAR", pattern="^(REGULAR|SALARY|PREMIUM)$")


class DepositRequest(BaseModel):
    """Schema for deposit request"""
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    description: Optional[str] = Field(None, max_length=200)


class WithdrawRequest(BaseModel):
    """Schema for withdrawal request"""
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    description: Optional[str] = Field(None, max_length=200)


class AccountResponse(BaseModel):
    """Schema for account response"""
    account_id: int
    account_number: str
    balance: float
    account_type: str
    interest_rate: float
    status: str
    created_at: datetime
    updated_at: datetime


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    transaction_id: int
    transaction_number: str
    type: str
    amount: float
    balance_after: float
    description: Optional[str]
    status: str
    timestamp: datetime

