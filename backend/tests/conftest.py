"""
Pytest Configuration

Sets up shared fixtures for all tests.
"""

import pytest
from app.core.database import connect_to_database, close_database_connection


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Connect to database before all tests"""
    await connect_to_database()
    yield
    await close_database_connection()
