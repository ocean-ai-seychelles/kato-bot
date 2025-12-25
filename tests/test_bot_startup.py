"""Integration test for bot startup sequence.

This test verifies that the bot can initialize properly without connecting
to Discord. It tests:
    - Config loading
    - Database initialization
    - Bot class instantiation
    - setup_hook execution (database connection and migrations)

This test does NOT require a Discord token or active bot connection.

Usage:
    uv run pytest tests/test_bot_startup.py -v
"""

import pytest

from bot.core.bot import DoryBot
from bot.core.config import Config


class TestBotStartup:
    """Test suite for bot initialization and startup sequence."""

    @pytest.mark.asyncio
    async def test_bot_initializes_with_config(self) -> None:
        """Test that bot initializes successfully with valid config."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        assert bot.config == config
        assert bot.db is not None
        assert bot.command_prefix == "!"

    @pytest.mark.asyncio
    async def test_bot_setup_hook_connects_database(self) -> None:
        """Test that setup_hook establishes database connection."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        # Database should not be connected yet
        assert bot.db.connection is None

        # Run setup hook
        await bot.setup_hook()

        # Database should now be connected
        assert bot.db.connection is not None

        # Verify migrations were applied by checking for tables
        tables = await bot.db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )

        table_names = [table["name"] for table in tables]
        assert "schema_migrations" in table_names
        assert "guild_config" in table_names
        assert "warnings" in table_names

        # Cleanup
        await bot.close()

    @pytest.mark.asyncio
    async def test_bot_close_cleans_up_database(self) -> None:
        """Test that bot.close() properly closes database connection."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.setup_hook()
        assert bot.db.connection is not None

        # Close bot
        await bot.close()

        # Database should be closed
        assert bot.db.connection is None

    @pytest.mark.asyncio
    async def test_bot_has_required_intents(self) -> None:
        """Test that bot is configured with required Discord intents."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        # Verify required intents are enabled
        assert bot.intents.members is True
        assert bot.intents.message_content is True
        assert bot.intents.reactions is True
        assert bot.intents.moderation is True
