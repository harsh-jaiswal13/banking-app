from fastapi import APIRouter
from app.api.v1.endpoints import auth, accounts, fixed_deposits, stocks, dashboard

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(fixed_deposits.router)
api_router.include_router(stocks.router)
api_router.include_router(dashboard.router)