from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Banking Application"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    DB_ECHO: bool = False
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 3
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5174"]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Interest Rates (can be moved to database in production)
    SAVINGS_INTEREST_RATE: float = 4.0
    FD_INTEREST_RATES: dict = {
        6: 5.5,   # 6 months
        12: 6.0,  # 1 year
        24: 6.5,  # 2 years
        36: 7.0,  # 3 years
        60: 7.5   # 5 years
    }
    PREMATURE_WITHDRAWAL_PENALTY: float = 1.0  # 1% penalty
    
    # Stock Trading (Mock configuration)
    STOCK_TRANSACTION_FEE: float = 0.1  # 0.1% transaction fee
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()