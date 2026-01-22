"""Shared pytest configuration and fixtures for all tests.

This module provides common fixtures used across the test suite.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="function")
async def isolated_database(monkeypatch, request):
    """Create a unique temporary database for each integration test.

    This fixture ensures database isolation for integration tests only.
    Each test gets its own temporary database file that's cleaned up afterward.

    Only applies to tests in the integration/ directory.
    """
    # Only apply to integration tests
    test_path = str(request.fspath)
    if "integration" not in test_path:
        yield None
        return

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create unique database path
        db_path = Path(tmpdir) / "test_kato.db"

        # Monkey-patch the Database class to use this path
        from bot.core.database import Database

        original_init = Database.__init__

        def patched_init(self, db_path_param=None):
            # Always use our temp database path
            original_init(self, str(db_path))

        monkeypatch.setattr(Database, "__init__", patched_init)

        yield db_path

        # Cleanup happens automatically when tmpdir context exits


# Auto-use the fixture for all tests (but it only activates for integration tests)
@pytest.fixture(autouse=True)
async def auto_isolated_database(isolated_database):
    """Automatically apply database isolation to integration tests."""
    yield
