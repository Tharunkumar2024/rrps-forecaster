"""Test configuration and reusable fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh database session for each test."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Yield session
    async with TestingSessionLocal() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def client(test_db: AsyncSession) -> Generator[TestClient, None, None]:
    """TestClient with overridden database dependency."""
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()


@pytest.fixture(scope="function", autouse=True)
def mock_ml_model() -> Generator:
    """Automatically mock the ML model loader so tests don't require the .joblib file."""
    mock_artifact = {
        "model": None,  # Mock model 
        "feature_cols": ["hour", "day_of_week", "month_sin", "month_cos", "lag_24"],
        "mape": 15.5
    }
    
    # We patch the core model_store functions to return True/MockArtifact
    with patch("app.core.model_store.is_model_available", return_value=True), \
         patch("app.core.model_store.get_forecast_model", return_value=mock_artifact), \
         patch("app.core.model_store.load_forecast_model", return_value=True):
        yield
