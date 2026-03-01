from fastapi import APIRouter, Depends, Query
from app.dependencies import get_current_user, get_stock_service
from app.services.stock import StockService
from app.schemas.stock import (
    StockBuyRequest,
    StockSellRequest,
    StockBuyApiResponse,
    StockSellApiResponse,
    PortfolioApiResponse,
    StockPricesApiResponse,
    StockTransactionsPaginatedResponse,
)
from app.core.response import success_response, paginated_response

router = APIRouter(prefix="/stocks", tags=["Stock Trading"])


@router.post(
    "/buy",
    response_model=StockBuyApiResponse,
    status_code=201,
    summary="Buy stocks",
    description=(
        "Purchase shares of a stock. The total cost (quantity × price + 0.1 % fee) "
        "is debited from the specified savings account."
    ),
)
async def buy_stock(
    buy_request: StockBuyRequest,
    current_user: dict = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """Buy stocks — deduct amount from savings account."""
    result = await service.buy_stock(
        user_id=current_user["user_id"],
        account_id=buy_request.account_id,
        stock_symbol=buy_request.stock_symbol,
        quantity=buy_request.quantity,
    )
    return success_response(data=result, message="Stock purchased successfully")


@router.post(
    "/sell",
    response_model=StockSellApiResponse,
    summary="Sell stocks",
    description=(
        "Sell shares you already own. The net proceeds (quantity × price − 0.1 % fee) "
        "are credited to the specified savings account."
    ),
)
async def sell_stock(
    sell_request: StockSellRequest,
    current_user: dict = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """Sell stocks — credit amount to savings account."""
    result = await service.sell_stock(
        user_id=current_user["user_id"],
        account_id=sell_request.account_id,
        stock_symbol=sell_request.stock_symbol,
        quantity=sell_request.quantity,
        price=sell_request.price,
    )
    return success_response(data=result, message="Stock sold successfully")


@router.get(
    "/portfolio",
    response_model=PortfolioApiResponse,
    summary="Get portfolio",
    description=(
        "Returns the authenticated user's current stock holdings enriched with "
        "live mock prices, current value, and profit/loss figures."
    ),
)
async def get_portfolio(
    current_user: dict = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """Get user's stock portfolio with current values and profit/loss."""
    result = await service.get_portfolio(current_user["user_id"])
    return success_response(data=result, message="Portfolio retrieved successfully")


@router.get(
    "/transactions",
    response_model=StockTransactionsPaginatedResponse,
    summary="List stock transactions",
    description="Paginated history of all buy/sell transactions for the authenticated user.",
)
async def get_stock_transactions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of records per page"),
    current_user: dict = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """Get stock transaction history with pagination."""
    transactions, total = await service.get_stock_transactions(
        current_user["user_id"], page, page_size
    )
    return paginated_response(
        data=transactions,
        total=total,
        page=page,
        page_size=page_size,
        message="Stock transactions retrieved",
    )


@router.get(
    "/prices",
    response_model=StockPricesApiResponse,
    summary="List available stock prices",
    description=(
        "Public endpoint — returns the mock prices for all supported ticker symbols. "
        "No authentication required."
    ),
)
async def get_stock_prices(
    service: StockService = Depends(get_stock_service),
):
    """Get mock stock prices (public endpoint)."""
    prices = service.get_all_prices()
    return success_response(data=prices, message="Stock prices retrieved")
