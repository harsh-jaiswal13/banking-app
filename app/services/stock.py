from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from app.repositories.stock import StockHoldingRepository, StockTransactionRepository
from app.repositories.account import AccountRepository
from app.models.stock import StockTransactionType, StockTransactionStatus
from app.core.exceptions import (
    AccountNotFoundException,
    InsufficientBalanceException,
    BankingException
)
from app.utils.generators import generate_stock_transaction_number
from app.services.account import AccountService


class StockService:
    """Business logic for stock trading operations"""
    
    # Mock stock prices 
    MOCK_STOCK_PRICES = {
        "AAPL": Decimal("175.50"),
        "GOOGL": Decimal("140.25"),
        "MSFT": Decimal("380.75"),
        "AMZN": Decimal("145.30"),
        "TSLA": Decimal("245.80"),
        "NFLX": Decimal("485.20"),
        "META": Decimal("325.60"),
        "NVDA": Decimal("495.40")
    }
    
    STOCK_NAMES = {
        "AAPL": "Apple Inc.",
        "GOOGL": "Alphabet Inc.",
        "MSFT": "Microsoft Corporation",
        "AMZN": "Amazon.com Inc.",
        "TSLA": "Tesla Inc.",
        "NFLX": "Netflix Inc.",
        "META": "Meta Platforms Inc.",
        "NVDA": "NVIDIA Corporation"
    }
    
    TRANSACTION_FEE_PERCENT = Decimal("0.1")  # 0.1% transaction fee
    
    def __init__(
        self, holding_repo: StockHoldingRepository, 
        stock_transaction_repo: StockTransactionRepository, 
        account_repo: AccountRepository, 
        account_service: AccountService
    ):
        self.holding_repo = holding_repo
        self.stock_transaction_repo = stock_transaction_repo
        self.account_repo = account_repo
        self.account_service = account_service
    
    def get_mock_price(self, stock_symbol: str) -> Decimal:
        """Get mock price for a stock"""
        stock_symbol = stock_symbol.upper()
        if stock_symbol not in self.MOCK_STOCK_PRICES:
            raise BankingException(
                f"Stock symbol '{stock_symbol}' not found. Available: {list(self.MOCK_STOCK_PRICES.keys())}",
                status_code=404
            )
        return self.MOCK_STOCK_PRICES[stock_symbol]
    
   
    def get_all_prices(self) -> list:
        """Get all mock stock prices as array"""
        return [
            {
                "symbol": symbol,
                "name": self.STOCK_NAMES.get(symbol, symbol),
                "price": float(price)
            }
            for symbol, price in self.MOCK_STOCK_PRICES.items()
        ]
    
    async def buy_stock(
        self, 
        user_id: int, 
        account_id: int,
        stock_symbol: str, 
        quantity: int, 
    ) -> dict:
        """Buy stocks - deduct from savings account"""
        # Validate inputs
        stock_symbol = stock_symbol.upper()

        if stock_symbol not in self.MOCK_STOCK_PRICES:
            raise BankingException(
                f"Stock symbol '{stock_symbol}' not found. Available: {list(self.MOCK_STOCK_PRICES.keys())}",
                status_code=404
            )
        if quantity <= 0:
            raise BankingException("Quantity must be positive", status_code=400)

        price = self.MOCK_STOCK_PRICES[stock_symbol]

        # Validate accountQuantity must be positive
        account = await self.account_repo.get(account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException()
        
        # Calculate total amount
        total_amount = price * Decimal(quantity)
        transaction_fee = total_amount * (self.TRANSACTION_FEE_PERCENT / Decimal('100'))
        total_with_fee = total_amount + transaction_fee
        
        # Check sufficient balance
        if account.balance < total_with_fee:
            raise InsufficientBalanceException(
                f"Insufficient balance. Required: {total_with_fee} (including fee: {transaction_fee}), Available: {account.balance}"
            )
        
        # Deduct from account
        transaction_number = generate_stock_transaction_number()
        await self.account_service.withdraw(
            account_id=account_id,
            user_id=user_id,
            amount=total_with_fee,
            description=f"Stock Purchase - {stock_symbol} x {quantity} @ {price} (TXN: {transaction_number})"
        )
        
        # Update or create holding
        holding = await self.holding_repo.get_by_user_and_symbol(user_id, stock_symbol)
        
        if holding:
            # Update existing holding - calculate new average price
            total_current_value = holding.average_price * Decimal(holding.quantity)
            total_new_value = price * Decimal(quantity)
            new_total_value = total_current_value + total_new_value
            new_total_quantity = holding.quantity + quantity
            new_average_price = new_total_value / Decimal(new_total_quantity)
            
            await self.holding_repo.update(holding, {
                "quantity": new_total_quantity,
                "average_price": new_average_price
            })
        else:
            # Create new holding
            holding_data = {
                "user_id": user_id,
                "stock_symbol": stock_symbol,
                "quantity": quantity,
                "average_price": price
            }
            holding = await self.holding_repo.create(holding_data)
        
        # Record stock transaction
        stock_transaction_data = {
            "user_id": user_id,
            "transaction_number": transaction_number,
            "stock_symbol": stock_symbol,
            "transaction_type": StockTransactionType.BUY,
            "quantity": quantity,
            "price": price,
            "total_amount": total_amount,
            "transaction_fee": transaction_fee,
            "status": StockTransactionStatus.COMPLETED
        }
        stock_transaction = await self.stock_transaction_repo.create(stock_transaction_data)
        print(stock_transaction)
        return {
            "transaction_id": stock_transaction.transaction_id,
            "transaction_number": stock_transaction.transaction_number,
            "stock_symbol": stock_symbol,
            "transaction_type": "BUY",
            "quantity": quantity,
            "price": float(price),
            "total_amount": float(total_amount),
            "transaction_fee": float(transaction_fee),
            "total_with_fee": float(total_with_fee),
            "status": stock_transaction.status.value,
            "timestamp": stock_transaction.created_at
        }
    
    async def sell_stock(
        self, 
        user_id: int, 
        account_id: int,
        stock_symbol: str, 
        quantity: int, 
        price: Decimal
    ) -> dict:
        """Sell stocks - credit to savings account"""
        # Validate inputs
        stock_symbol = stock_symbol.upper()
        if quantity <= 0:
            raise BankingException("Quantity must be positive", status_code=400)
        
        if price <= 0:
            raise BankingException("Price must be positive", status_code=400)
        
        # Validate account
        account = await self.account_repo.get(account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException()
        
        # Check if user has the stock
        holding = await self.holding_repo.get_by_user_and_symbol(user_id, stock_symbol)
        if not holding:
            raise BankingException(f"You don't own any {stock_symbol} stock", status_code=400)
        
        if holding.quantity < quantity:
            raise BankingException(
                f"Insufficient stock quantity. You have {holding.quantity}, trying to sell {quantity}",
                status_code=400
            )
        
        # Calculate total amount
        total_amount = price * Decimal(quantity)
        transaction_fee = total_amount * (self.TRANSACTION_FEE_PERCENT / Decimal('100'))
        net_amount = total_amount - transaction_fee
        
        # Update holding
        new_quantity = holding.quantity - quantity
        if new_quantity == 0:
            # Delete holding if quantity becomes zero
            await self.holding_repo.delete(holding.holding_id)
        else:
            await self.holding_repo.update(holding, {"quantity": new_quantity})
        
        # Credit to account
        transaction_number = generate_stock_transaction_number()
        await self.account_service.deposit(
            account_id=account_id,
            user_id=user_id,
            amount=net_amount,
            description=f"Stock Sale - {stock_symbol} x {quantity} @ {price} (TXN: {transaction_number})"
        )
        
        # Record stock transaction
        stock_transaction_data = {
            "user_id": user_id,
            "transaction_number": transaction_number,
            "stock_symbol": stock_symbol,
            "transaction_type": StockTransactionType.SELL,
            "quantity": quantity,
            "price": price,
            "total_amount": total_amount,
            "transaction_fee": transaction_fee,
            "status": StockTransactionStatus.COMPLETED
        }
        stock_transaction = await self.stock_transaction_repo.create(stock_transaction_data)
        
        return {
            "transaction_id": stock_transaction.transaction_id,
            "transaction_number": stock_transaction.transaction_number,
            "stock_symbol": stock_symbol,
            "transaction_type": "SELL",
            "quantity": quantity,
            "price": float(price),
            "total_amount": float(total_amount),
            "transaction_fee": float(transaction_fee),
            "net_amount": float(net_amount),
            "status": stock_transaction.status.value,
            "timestamp": stock_transaction.created_at
        }
    
    async def get_portfolio(self, user_id: int) -> dict:
        """Get user's stock portfolio with current values"""
        holdings = await self.holding_repo.get_by_user(user_id)
        
        holdings_data = []
        total_invested = Decimal('0')
        total_current_value = Decimal('0')
        
        for holding in holdings:
            # Get current price (mock)
            current_price = self.get_mock_price(holding.stock_symbol)
            current_value = current_price * Decimal(holding.quantity)
            invested_value = holding.average_price * Decimal(holding.quantity)
            profit_loss = current_value - invested_value
            profit_loss_percentage = (profit_loss / invested_value * Decimal('100')) if invested_value > 0 else Decimal('0')
            
            holdings_data.append({
                "holding_id": holding.holding_id,
                "stock_symbol": holding.stock_symbol,
                "quantity": holding.quantity,
                "average_price": float(holding.average_price),
                "current_price": float(current_price),
                "invested_value": float(invested_value),
                "current_value": float(current_value),
                "profit_loss": float(profit_loss),
                "profit_loss_percentage": float(profit_loss_percentage)
            })
            
            total_invested += invested_value
            total_current_value += current_value
        
        total_profit_loss = total_current_value - total_invested
        total_profit_loss_percentage = (total_profit_loss / total_invested * Decimal('100')) if total_invested > 0 else Decimal('0')
        
        return {
            "total_invested": float(total_invested),
            "current_value": float(total_current_value),
            "total_profit_loss": float(total_profit_loss),
            "total_profit_loss_percentage": float(total_profit_loss_percentage),
            "holdings": holdings_data
        }
    
    async def get_stock_transactions(self, user_id: int, page: int = 1, page_size: int = 20) -> tuple:
        """Get stock transaction history"""
        skip = (page - 1) * page_size
        transactions = await self.stock_transaction_repo.get_by_user(user_id, skip=skip, limit=page_size)
        
        total = await self.stock_transaction_repo.count(filters={"user_id": user_id})
        
        transaction_list = [
            {
                "transaction_id": t.transaction_id,
                "transaction_number": t.transaction_number,
                "stock_symbol": t.stock_symbol,
                "transaction_type": t.transaction_type.value,
                "quantity": t.quantity,
                "price": float(t.price),
                "total_amount": float(t.total_amount),
                "transaction_fee": float(t.transaction_fee),
                "status": t.status.value,
                "timestamp": t.created_at
            }
            for t in transactions
        ]
        
        return transaction_list, total
