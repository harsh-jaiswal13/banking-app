"""
Integration test conftest.py

Sets up:
  - A real async test DB (same engine pattern as unit/repositories/conftest.py)
  - get_db dependency override so the app uses the test DB
  - async HTTP client via httpx + ASGITransport
  - Convenience fixtures: registered user, auth token, authenticated client
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.session import Base, get_db

# Import all models so Base.metadata knows about every table
from app.models.user import User
from app.models.savings_account import SavingsAccount
from app.models.fixed_deposit import FixedDeposit
from app.models.transaction import Transaction
from app.models.stock import StockHolding, StockTransaction

TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:root@localhost:5432/test_banking_db"
)

# ---------------------------------------------------------------------------
# Engine — session scoped (created once for the entire integration test run)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DB session + dependency override — function scoped (fresh per test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Real DB session injected into the app via dependency override."""
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        # Truncate all tables after each test so state never leaks
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    Async HTTP client wired to the FastAPI app.
    The get_db dependency is overridden to use the test session.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Reusable user / auth fixtures
# ---------------------------------------------------------------------------

DEFAULT_USER = {
    "email": "integration@example.com",
    "password": "Passw0rd!",
    "full_name": "Integration User",
    "phone": "9876543210",
}


@pytest_asyncio.fixture(scope="function")
async def registered_user(client):
    """Register a user and return the response data."""
    response = await client.post("/api/v1/auth/register", json=DEFAULT_USER)
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def auth_token(client, registered_user):
    """Log in and return the access token string."""
    response = await client.post("/api/v1/auth/login", json={
        "email": DEFAULT_USER["email"],
        "password": DEFAULT_USER["password"],
    })
    assert response.status_code == 200, response.text
    data = response.json()
    # Support both {"data": {"access_token": ...}} and {"access_token": ...}
    if "data" in data and isinstance(data["data"], dict):
        return data["data"]["access_token"]
    return data["access_token"]


@pytest_asyncio.fixture(scope="function")
async def auth_client(client, auth_token):
    """HTTP client with Authorization header already set."""
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client


@pytest_asyncio.fixture(scope="function")
async def savings_account(auth_client):
    """Create and return a savings account for the authenticated user."""
    response = await auth_client.post(
        "/api/v1/accounts",
        json={"account_type": "REGULAR"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    if "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data


@pytest_asyncio.fixture(scope="function")
async def funded_account(auth_client, savings_account):
    """Savings account pre-loaded with 100,000 so tests can spend freely."""
    account_id = savings_account["account_id"]
    response = await auth_client.post(
        f"/api/v1/accounts/{account_id}/deposit",
        json={"amount": 100000, "description": "Test funding"},
    )
    assert response.status_code == 200, response.text
    return savings_account