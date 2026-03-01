# app/schemas/stock.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, TypeVar, Generic

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic API wrapper (mirrors app.core.response structure)
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel, Generic[T]):
    """Standard API envelope returned by all stock endpoints."""
    success: bool
    message: str
    data: Optional[T] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation successful",
                "data": {}
            }
        }


class PaginatedApiResponse(BaseModel, Generic[T]):
    """Paginated envelope returned by list endpoints."""
    success: bool = True
    message: str
    data: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Data retrieved",
                "data": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class StockBuyRequest(BaseModel):
    """Request body for buying stocks."""
    stock_symbol: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Ticker symbol, e.g. AAPL",
        examples=["AAPL"]
    )
    quantity: int = Field(..., gt=0, description="Number of shares to buy", examples=[10])
    account_id: int = Field(
        ..., gt=0,
        description="ID of the savings account to debit",
        examples=[1]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "stock_symbol": "AAPL",
                "quantity": 10,
                "account_id": 1
            }
        }


class StockSellRequest(BaseModel):
    """Request body for selling stocks."""
    stock_symbol: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Ticker symbol, e.g. AAPL",
        examples=["AAPL"]
    )
    quantity: int = Field(..., gt=0, description="Number of shares to sell", examples=[5])
    account_id: int = Field(
        ..., gt=0,
        description="ID of the savings account to credit",
        examples=[1]
    )
    price: Optional[float] = Field(
        None,
        gt=0,
        description="Sell price per share. If omitted the current mock price is used.",
        examples=[180.0]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "stock_symbol": "AAPL",
                "quantity": 5,
                "account_id": 1,
                "price": 180.0
            }
        }


# ---------------------------------------------------------------------------
# Response schemas – individual data objects
# ---------------------------------------------------------------------------

class StockTradeResponse(BaseModel):
    """Response data returned after a buy or sell trade."""
    transaction_id: int = Field(..., description="Internal transaction ID")
    transaction_number: str = Field(..., description="Human-readable reference number")
    stock_symbol: str
    transaction_type: str = Field(..., description="BUY or SELL")
    quantity: int
    price: float = Field(..., description="Price per share at execution time")
    total_amount: float = Field(..., description="quantity × price (before fee)")
    transaction_fee: float = Field(..., description="0.1 % brokerage fee")
    # buy includes total_with_fee; sell includes net_amount
    total_with_fee: Optional[float] = Field(None, description="Total debited (buy trades only)")
    net_amount: Optional[float] = Field(None, description="Net credited after fee (sell trades only)")
    status: str
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 42,
                "transaction_number": "STK-20260301-0001",
                "stock_symbol": "AAPL",
                "transaction_type": "BUY",
                "quantity": 10,
                "price": 175.50,
                "total_amount": 1755.00,
                "transaction_fee": 1.755,
                "total_with_fee": 1756.755,
                "net_amount": None,
                "status": "COMPLETED",
                "timestamp": "2026-03-01T17:00:00"
            }
        }


class StockHoldingDetail(BaseModel):
    """A single stock holding with live P&L."""
    holding_id: int
    stock_symbol: str
    quantity: int
    average_price: float = Field(..., description="Average cost basis per share")
    current_price: float = Field(..., description="Current mock market price")
    invested_value: float = Field(..., description="average_price × quantity")
    current_value: float = Field(..., description="current_price × quantity")
    profit_loss: float = Field(..., description="current_value − invested_value")
    profit_loss_percentage: float

    class Config:
        json_schema_extra = {
            "example": {
                "holding_id": 7,
                "stock_symbol": "AAPL",
                "quantity": 10,
                "average_price": 175.50,
                "current_price": 180.00,
                "invested_value": 1755.00,
                "current_value": 1800.00,
                "profit_loss": 45.00,
                "profit_loss_percentage": 2.56
            }
        }


class PortfolioDetailResponse(BaseModel):
    """Aggregated portfolio summary with all holdings."""
    total_invested: float
    current_value: float
    total_profit_loss: float
    total_profit_loss_percentage: float
    holdings: List[StockHoldingDetail]

    class Config:
        json_schema_extra = {
            "example": {
                "total_invested": 5000.00,
                "current_value": 5200.00,
                "total_profit_loss": 200.00,
                "total_profit_loss_percentage": 4.00,
                "holdings": []
            }
        }


class StockTransactionResponse(BaseModel):
    """A single stock transaction record (used in history list)."""
    transaction_id: int
    transaction_number: str
    stock_symbol: str
    transaction_type: str = Field(..., description="BUY or SELL")
    quantity: int
    price: float
    total_amount: float
    transaction_fee: float
    status: str
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 1,
                "transaction_number": "STK-20260301-0001",
                "stock_symbol": "GOOGL",
                "transaction_type": "SELL",
                "quantity": 3,
                "price": 140.25,
                "total_amount": 420.75,
                "transaction_fee": 0.42,
                "status": "COMPLETED",
                "timestamp": "2026-03-01T12:00:00"
            }
        }


class StockPriceResponse(BaseModel):
    """Current price info for a single stock symbol."""
    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Full company name")
    price: float = Field(..., description="Current mock price in USD")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "price": 175.50
            }
        }


# ---------------------------------------------------------------------------
# Convenience aliases – fully typed envelopes ready for use as response_model
# ---------------------------------------------------------------------------

StockBuyApiResponse = ApiResponse[StockTradeResponse]
StockSellApiResponse = ApiResponse[StockTradeResponse]
PortfolioApiResponse = ApiResponse[PortfolioDetailResponse]
StockPricesApiResponse = ApiResponse[List[StockPriceResponse]]
StockTransactionsPaginatedResponse = PaginatedApiResponse[StockTransactionResponse]

# Legacy names kept for backwards compatibility
StockHoldingResponse = StockHoldingDetail
