
# app/schemas/dashboard.py
from pydantic import BaseModel
from typing import List


class DashboardSummary(BaseModel):
    """Schema for dashboard summary"""
    total_balance: float
    total_fds: int
    total_fd_amount: float
    total_stock_value: float
    portfolio_value: float
    recent_transactions: List[TransactionResponse]

