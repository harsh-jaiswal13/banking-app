from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.session import get_db
from app.dependencies import get_current_user,get_fd_service
from app.services.fixed_deposit import FixedDepositService
from app.schemas.fixed_deposit import FDCreate, FDResponse, FDCloseRequest
from app.core.response import success_response
from app.core.exceptions import BankingException

router = APIRouter(prefix="/fixed-deposits", tags=["Fixed Deposits"])


@router.post("", response_model=dict, status_code=201)
async def create_fixed_deposit(
    fd_data: FDCreate,
    current_user: dict = Depends(get_current_user),
    service: FixedDepositService = Depends(get_fd_service)
):
    """Create a new fixed deposit"""
    try:
        result = await service.create_fd(
            user_id=current_user["user_id"],
            account_id=fd_data.account_id,
            amount=fd_data.amount,
            tenure_months=fd_data.tenure_months
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return success_response(data=result, message="Fixed Deposit created successfully")


@router.get("/{fd_id}", response_model=dict)
async def get_fixed_deposit(
    fd_id: int,
    current_user: dict = Depends(get_current_user),
    service: FixedDepositService = Depends(get_fd_service)
):
    """Get fixed deposit details"""
    try:
        result = await service.get_fd(fd_id, current_user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return success_response(data=result, message="Fixed Deposit retrieved")


@router.get("", response_model=dict)
async def get_all_fixed_deposits(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, MATURED, CLOSED"),
    current_user: dict = Depends(get_current_user),
    service: FixedDepositService = Depends(get_fd_service)
):
    """Get all fixed deposits for the user with optional status filter"""
    try:
        result = await service.get_all_user_fds(current_user["user_id"], status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return success_response(
        data=result, 
        message=f"Retrieved {len(result)} fixed deposit(s)"
    )


@router.post("/{fd_id}/close", response_model=dict)
async def close_fixed_deposit(
    fd_id: int,
    close_request: FDCloseRequest,
    current_user: dict = Depends(get_current_user),
    service: FixedDepositService = Depends(get_fd_service)
):
    """Close fixed deposit prematurely (before maturity)"""
    if not close_request.confirm:
        raise BankingException("Confirmation required to close FD", status_code=400)
    
    result = await service.close_fd_prematurely(fd_id, current_user["user_id"])
    return success_response(data=result, message="Fixed Deposit closed successfully")


@router.post("/{fd_id}/withdraw", response_model=dict)
async def withdraw_matured_fd(
    fd_id: int,
    current_user: dict = Depends(get_current_user),
    service: FixedDepositService = Depends(get_fd_service)
):
    """Withdraw matured fixed deposit amount"""
    result = await service.withdraw_matured_fd(fd_id, current_user["user_id"])
    return success_response(data=result, message="Maturity amount withdrawn successfully")
