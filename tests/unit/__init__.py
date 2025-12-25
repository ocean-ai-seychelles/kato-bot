"""Unit tests for isolated bot component testing.

These tests validate the correctness of individual functions and classes in
isolation, without requiring a Discord server or making external API calls.
Unit tests use mocks and stubs to simulate dependencies, making them fast and
suitable for continuous integration.

Test Modules:
    test_config.py:
        - Config loader successfully parses valid TOML files
        - FileNotFoundError raised for missing config files
        - ValueError raised for invalid/incomplete configurations
        - Nested key access via get() method works correctly
        - Default values returned when keys don't exist
        - Type validation for required config sections

    test_database.py:
        - Database connection establishes successfully
        - Schema migrations apply correctly
        - Migration tracking prevents duplicate application
        - CRUD operations for all tables work correctly:
            * guild_config: insert, update, select
            * warnings: insert, select by user, count warnings
            * mod_actions: insert, select by action type
            * message_logs: insert, select by message ID
            * automod_violations: insert, select by violation type
            * reaction_roles: insert, delete, select by message
            * banned_words: insert, delete, check if word banned
        - Foreign key constraints are enforced
        - Indexes exist for performance-critical queries
        - Database closes cleanly without leaving locks

    test_utils.py:
        - checks.py: Permission check decorators function correctly
        - embeds.py: Embed factory functions create valid embeds
        - helpers.py:
            * Template variable substitution replaces all placeholders
            * Duration parsing converts strings to seconds correctly
            * User ID extraction from mentions works with various formats
            * Rate limiting logic correctly tracks and resets windows

Testing Approach:
    - Pure functions tested with various inputs and edge cases
    - Classes tested with dependency injection and mocking
    - Database tests use in-memory SQLite (:memory:) for speed
    - Discord objects (Member, Guild, etc.) mocked with unittest.mock
    - Async functions tested with pytest-asyncio

Mocking Strategy:
    - unittest.mock.AsyncMock for async Discord API methods
    - unittest.mock.Mock for sync methods and properties
    - pytest fixtures for common mock objects (mock_bot, mock_guild, etc.)
    - Patch Discord API calls to prevent actual network requests

Running Unit Tests:
    # All unit tests
    uv run pytest tests/unit/ -v

    # Specific test file
    uv run pytest tests/unit/test_config.py -v

    # With coverage
    uv run pytest tests/unit/ --cov=bot.core --cov=bot.utils

    # Coverage report in terminal
    uv run pytest tests/unit/ --cov=bot --cov-report=term-missing

Benefits of Unit Tests:
    - Fast execution (no API calls or network latency)
    - Can run in CI/CD without Discord server
    - Catch logic errors before integration testing
    - Provide clear documentation of expected behavior
    - Enable test-driven development (TDD)
    - High code coverage with less infrastructure
"""
