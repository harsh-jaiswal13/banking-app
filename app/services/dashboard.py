from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from typing import List
from app.repositories.account import AccountRepository
from app.repositories.fixed_deposit import FixedDepositRepository
from app.repositories.stock import StockHoldingRepository
from app.repositories.transaction import TransactionRepository
from app.services.stock import StockService


class DashboardService:
    """Business logic for dashboard and aggregated data"""
    
    def __init__(
        self,
        account_repo: AccountRepository,
        fd_repo: FixedDepositRepository,
        holding_repo: StockHoldingRepository,
        transaction_repo: TransactionRepository,
        stock_service: StockService
    ):
        self.account_repo = account_repo
        self.fd_repo = fd_repo
        self.holding_repo = holding_repo
        self.transaction_repo = transaction_repo
        self.stock_service = stock_service
    
    async def get_dashboard_summary(self, user_id: int) -> dict:
        """Get complete dashboard summary for user"""
        # Get all savings accounts
        accounts = await self.account_repo.get_by_user(user_id)
        total_balance = sum(float(acc.balance) for acc in accounts)
        
        # Get active FDs
        active_fds_count = await self.fd_repo.get_active_fds_count(user_id)
        total_fd_amount = await self.fd_repo.get_total_fd_amount(user_id)
        
        # Get stock portfolio value
        portfolio = await self.stock_service.get_portfolio(user_id)
        total_stock_value = portfolio.get("current_value", 0.0)
        stock_profit_loss = portfolio.get("total_profit_loss", 0.0)
        
        # Calculate overall portfolio value
        overall_portfolio_value = total_balance + total_fd_amount + total_stock_value
        
        # Get recent transactions (last 10 from all accounts)
        recent_transactions = []
        for account in accounts[:3]:  # Limit to first 3 accounts for performance
            transactions = await self.transaction_repo.get_by_account(
                account.account_id, skip=0, limit=5
            )
            for t in transactions:
                recent_transactions.append({
                    "transaction_id": t.transaction_id,
                    "transaction_number": t.transaction_number,
                    "account_number": account.account_number,
                    "type": t.transaction_type.value,
                    "amount": float(t.amount),
                    "balance_after": float(t.balance_after),
                    "description": t.description,
                    "timestamp": t.created_at
                })
        
        # Sort by timestamp and take last 10
        recent_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_transactions = recent_transactions[:10]
        
        # Get accounts summary
        accounts_summary = [
            {
                "account_id": acc.account_id,
                "account_number": acc.account_number,
                "account_type": acc.account_type.value,
                "balance": float(acc.balance),
                "status": acc.status.value
            }
            for acc in accounts
        ]
        
        # Get FDs summary
        active_fds = await self.fd_repo.get_active_by_user(user_id)
        fds_summary = [
            {
                "fd_id": fd.fd_id,
                "fd_number": fd.fd_number,
                "principal_amount": float(fd.principal_amount),
                "maturity_amount": float(fd.maturity_amount),
                "maturity_date": fd.maturity_date,
                "interest_rate": float(fd.interest_rate)
            }
            for fd in active_fds[:5]  # Limit to 5 for dashboard
        ]
        
        return {
            "summary": {
                "total_balance": total_balance,
                "total_fds": active_fds_count,
                "total_fd_amount": total_fd_amount,
                "total_stock_value": total_stock_value,
                "stock_profit_loss": stock_profit_loss,
                "overall_portfolio_value": overall_portfolio_value
            },
            "accounts": accounts_summary,
            "active_fds": fds_summary,
            "stock_portfolio": {
                "current_value": total_stock_value,
                "total_profit_loss": stock_profit_loss,
                "holdings_count": len(portfolio.get("holdings", []))
            },
            "recent_transactions": recent_transactions
        }
