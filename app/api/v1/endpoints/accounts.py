from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from app.db.session import get_db
from app.dependencies import get_current_user ,get_account_service
from app.services.account import AccountService
from app.schemas.account import (
    AccountCreate, DepositRequest, WithdrawRequest,
    AccountResponse, TransactionResponse
)
from app.core.response import success_response, paginated_response

router = APIRouter(prefix="/accounts", tags=["Savings Accounts"])


@router.post("", response_model=dict, status_code=201)
async def create_account(
    account_data: AccountCreate,
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Create a new savings account"""
    result = await account_service.create_account(
        user_id=current_user["user_id"],
        account_type=account_data.account_type
    )
    return success_response(data=result, message="Account created successfully")


@router.get("/{account_id}", response_model=dict)
async def get_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Get account details"""
    result = await account_service.get_account(account_id, current_user["user_id"])
    return success_response(data=result, message="Account retrieved")


@router.post("/{account_id}/deposit", response_model=dict)
async def deposit(
    account_id: int,
    deposit_data: DepositRequest,
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Deposit money into account"""
    result = await account_service.deposit(
        account_id=account_id,
        user_id=current_user["user_id"],
        amount=deposit_data.amount,
        description=deposit_data.description
    )
    return success_response(data=result, message="Deposit successful")


@router.post("/{account_id}/withdraw", response_model=dict)
async def withdraw(
    account_id: int,
    withdraw_data: WithdrawRequest,
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Withdraw money from account"""
    result = await account_service.withdraw(
        account_id=account_id,
        user_id=current_user["user_id"],
        amount=withdraw_data.amount,
        description=withdraw_data.description
    )
    return success_response(data=result, message="Withdrawal successful")


@router.get("/{account_id}/balance", response_model=dict)
async def get_balance(
    account_id: int,
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Get account balance"""
    result = await account_service.get_balance(account_id, current_user["user_id"])
    return success_response(data=result, message="Balance retrieved")


@router.get("/{account_id}/transactions", response_model=dict)
async def get_transactions(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service)
):
    """Get transaction history"""
    transactions, total = await account_service.get_transactions(
        account_id, current_user["user_id"], page, page_size
    )
    return paginated_response(
        data=transactions,
        total=total,
        page=page,
        page_size=page_size,
        message="Transactions retrieved"
    )