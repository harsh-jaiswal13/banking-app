# app/db/base.py
from app.db.session import Base

# Import ALL models here so relationships can be resolved
from app.models.user import User
from app.models.savings_account import SavingsAccount
from app.models.fixed_deposit import FixedDeposit
from app.models.transaction import Transaction
from app.models.stock import StockHolding, StockTransaction
