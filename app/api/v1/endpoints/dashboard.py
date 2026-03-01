from fastapi import APIRouter, Depends
from app.dependencies import get_current_user,get_dashboard_service
from app.core.response import success_response
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=dict)
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Get comprehensive dashboard summary including:
    - Total balance across all savings accounts
    - Active FDs count and total amount
    - Stock portfolio value and profit/loss
    - Overall portfolio value
    - Recent transactions
    """
    result = await dashboard_service.get_dashboard_summary(current_user["user_id"])
    return success_response(data=result, message="Dashboard data retrieved successfully")
