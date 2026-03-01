
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# This ensures our create_all sees the same metadata as your models.
from app.db.session import Base

# Import every model so their tables register with Base.metadata.
# Missing one = that table won't be created = FK errors.
from app.models.user import User
from app.models.savings_account import SavingsAccount
from app.models.fixed_deposit import FixedDeposit
from app.models.transaction import Transaction
from app.models.stock import StockHolding, StockTransaction

# YOUR APP uses:  postgresql://...          (psycopg2, sync)
# TESTS use:      postgresql+asyncpg://...  (asyncpg, async)
TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:root@localhost:5432/banking_app"
)
# DATABASE_URL=postgresql://postgres:root@localhost:5432/banking_app
@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield _engine

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await _engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.connect() as conn:
        await conn.begin()  # outer transaction — never committed

        async with async_session(bind=conn) as session:
            await session.begin_nested()  # savepoint
            yield session
            await session.rollback()  # rolls back to savepoint

        await conn.rollback()  # rolls back the outer transaction