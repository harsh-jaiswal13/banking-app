from fastapi import Depends, HTTPException, status ,Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth import AuthService
from app.services.account import AccountService
from app.services.fixed_deposit import FixedDepositService
from app.services.stock import StockService
from app.services.dashboard import DashboardService
from app.repositories.fixed_deposit import FixedDepositRepository
from app.repositories.stock import StockHoldingRepository,StockTransactionRepository
from app.repositories.user import UserRepository
from app.repositories.account import AccountRepository
from app.repositories.transaction import TransactionRepository
from typing import Optional

security = HTTPBearer(auto_error=False)


async def get_user_repo(session: AsyncSession = Depends(get_db)):
    return UserRepository(session)

async def get_account_repo(session: AsyncSession = Depends(get_db)):
    return AccountRepository(session)

async def get_transaction_repo(session: AsyncSession = Depends(get_db)):
    return TransactionRepository(session)

async def get_fixed_deposit_repo(session: AsyncSession = Depends(get_db)):
    return FixedDepositRepository(session)


async def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
) -> AuthService:
    """Get auth service instance"""
    return AuthService(user_repo)


async def get_account_service(
    account_repo: AccountRepository = Depends(get_account_repo),
    transaction_repo: TransactionRepository = Depends(get_transaction_repo),
) -> AccountService:
    return AccountService(account_repo,transaction_repo)
        
async def get_fd_service(
    fixed_deposit_repo: FixedDepositRepository = Depends(get_fixed_deposit_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
    transaction_repo: TransactionRepository = Depends(get_transaction_repo),
    account_service : AccountService = Depends(get_account_service)
) -> FixedDepositService:
    return FixedDepositService(fixed_deposit_repo, account_repo, transaction_repo,account_service)  

async def get_stock_holding_repo(session: AsyncSession = Depends(get_db)):
    return StockHoldingRepository(session)

async def get_stock_transaction_repo(session: AsyncSession = Depends(get_db)):
    return StockTransactionRepository(session)

async def get_stock_service(
    stock_holding_repo: StockHoldingRepository = Depends(get_stock_holding_repo),
    stock_transaction_repo: StockTransactionRepository = Depends(get_stock_transaction_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
    account_service: AccountService = Depends(get_account_service),
) -> StockService:
    return StockService(stock_holding_repo, stock_transaction_repo, account_repo, account_service)

async def get_dashboard_service(
    account_repo: AccountRepository = Depends(get_account_repo),
    fixed_deposit_repo: FixedDepositRepository = Depends(get_fixed_deposit_repo),
    stock_holding_repo: StockHoldingRepository = Depends(get_stock_holding_repo),
    stock_transaction_repo: StockTransactionRepository = Depends(get_transaction_repo),
    stock_service: StockService = Depends(get_stock_service),
) -> DashboardService:
    return DashboardService(account_repo, fixed_deposit_repo, stock_holding_repo, stock_transaction_repo,stock_service)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
):
    token = None

    # 1️⃣ Swagger / Postman / curl
    if credentials:
        token = credentials.credentials

    # 2️⃣ Browser (HttpOnly cookie)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await auth_service.get_current_user(token)
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
