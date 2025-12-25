"""Comprehensive test suite for the Dory Discord moderation bot.

This package contains all tests for the Dory bot, organized into integration
tests (which run against a real Discord test server) and unit tests (which test
pure Python logic in isolation using mocks).

Test Organization:
    integration/: Integration tests that require a real Discord server
        - test_welcome.py: Tests for member join events and welcome messages
        - test_reaction_roles.py: Tests for reaction role assignment/removal
        - test_automod.py: Tests for spam detection, caps, mentions, banned words
        - test_moderation.py: Tests for kick, ban, warn, timeout commands
        - test_logging.py: Tests for audit trail and message logging

    unit/: Unit tests for isolated component testing
        - test_config.py: Config loader validation and error handling
        - test_database.py: Database CRUD operations and schema validation
        - test_utils.py: Utility functions and helper methods

    test_config/: Test server configuration (gitignored, contains secrets)
        - test_server.toml: Discord test server credentials and IDs

Testing Strategy:
    - Integration tests validate end-to-end functionality with Discord API
    - Unit tests ensure core logic correctness without Discord dependencies
    - Pytest fixtures in conftest.py provide reusable test infrastructure
    - All tests use async/await patterns (pytest-asyncio)
    - Test coverage tracked with pytest-cov

Fixtures (in conftest.py):
    - test_bot: Bot instance configured for testing
    - test_guild: Reference to the Discord test server
    - test_channels: Dictionary of test channels (welcome, mod_log, etc.)
    - test_roles: Dictionary of test roles (moderator, admin, initial)
    - test_database: Clean database instance for each test

Running Tests:
    # All tests
    uv run pytest tests/

    # Only integration tests
    uv run pytest tests/integration/

    # Only unit tests
    uv run pytest tests/unit/

    # With coverage report
    uv run pytest --cov=bot tests/

    # Verbose output
    uv run pytest -v tests/

Test Requirements:
    - A dedicated Discord test server must be set up
    - Test server credentials stored in tests/test_config/test_server.toml
    - Test server should mirror production structure (channels, roles)
    - Bot must have appropriate permissions in test server
"""
