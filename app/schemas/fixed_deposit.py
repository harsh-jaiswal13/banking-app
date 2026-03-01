
# app/schemas/fixed_deposit.py
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import date, datetime
from typing import Optional


class FDCreate(BaseModel):
    """Schema for creating fixed deposit"""
    account_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    tenure_months: int = Field(..., gt=0, description="Tenure in months (6, 12, 24, 36, 60)")
    
    @validator('tenure_months')
    def validate_tenure(cls, v):
        allowed_tenures = [6, 12, 24, 36, 60]
        if v not in allowed_tenures:
            raise ValueError(f'Tenure must be one of {allowed_tenures}')
        return v


class FDResponse(BaseModel):
    """Schema for FD response"""
    fd_id: int
    fd_number: str
    principal_amount: float
    interest_rate: float
    tenure_months: int
    maturity_amount: float
    maturity_date: date
    status: str
    created_at: datetime


class FDCloseRequest(BaseModel):
    """Schema for closing FD prematurely"""
    confirm: bool = Field(..., description="Confirmation to close FD")

