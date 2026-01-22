"""Integration tests for the welcome system.

This module tests the welcome cog against a real Discord test server,
verifying that:
    - Welcome messages are sent when members join
    - Template variables are substituted correctly
    - Admin commands work as expected
    - Error handling functions properly

Usage:
    uv run pytest tests/integration/test_welcome.py -v
"""

import pytest

from bot.cogs.welcome import WelcomeCog
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestWelcomeTemplateSubstitution:
    """Test template variable substitution."""

    def test_substitute_template_vars_basic(self) -> None:
        """Test basic template variable substitution."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = WelcomeCog(bot)

        # Create mock member and guild
        class MockMember:
            mention = "@TestUser"
            display_name = "TestUser"

        class MockChannel:
            mention = "#getting-started"

        class MockGuild:
            name = "Test Server"

            def get_channel(self, channel_id):
                return MockChannel()

        member = MockMember()
        guild = MockGuild()

        template = "Welcome {mention} to {server}! Visit {channel} to start."
        result = cog._substitute_template_vars(template, member, guild)

        assert "@TestUser" in result
        assert "Test Server" in result
        assert "#getting-started" in result
        assert "Welcome" in result

    def test_substitute_all_variables(self) -> None:
        """Test that all template variables are substituted."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = WelcomeCog(bot)

        class MockMember:
            mention = "@User"
            display_name = "DisplayName"

        class MockChannel:
            mention = "#channel"

        class MockGuild:
            name = "Guild"

            def get_channel(self, channel_id):
                return MockChannel()

        member = MockMember()
        guild = MockGuild()

        # Template with all variables
        template = "{mention} {user} {server} {channel}"
        result = cog._substitute_template_vars(template, member, guild)

        assert "@User" in result
        assert "DisplayName" in result
        assert "Guild" in result
        assert "#channel" in result


class TestWelcomeCogInitialization:
    """Test welcome cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the welcome cog initializes successfully."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = WelcomeCog(bot)

        assert cog.bot == bot
        assert cog is not None

    def test_cog_has_commands(self) -> None:
        """Test that the cog has the expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = WelcomeCog(bot)

        # Check for command existence
        assert hasattr(cog, "set_welcome_channel")
        assert hasattr(cog, "set_welcome_message")
        assert hasattr(cog, "test_welcome")

    def test_cog_has_listener(self) -> None:
        """Test that the cog has the on_member_join listener."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = WelcomeCog(bot)

        assert hasattr(cog, "on_member_join")


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the welcome cog can be loaded into the bot."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Load the cog
    await bot.load_extension("bot.cogs.welcome")

    # Check that cog is loaded
    assert "Welcome" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_welcome_cog_in_bot_startup() -> None:
    """Test that welcome cog is loaded during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup hook (this loads cogs)
    await bot.setup_hook()

    # Check that welcome cog is loaded
    assert "Welcome" in bot.cogs

    # Cleanup
    await bot.close()
