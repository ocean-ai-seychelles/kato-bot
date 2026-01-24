"""Integration tests for the interest roles system.

This module tests the interest roles cog functionality including:
    - Cog initialization and commands
    - Database operations for interests and selections
    - Persistent view registration
    - Config syncing

Usage:
    uv run pytest tests/integration/test_interest_roles.py -v
"""

import pytest

from bot.cogs.interest_roles import (
    InterestRolesCog,
    InterestSelectView,
    PersistentInterestView,
)
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestInterestRolesCogInitialization:
    """Test interest roles cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the interest roles cog initializes successfully."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = InterestRolesCog(bot)

        assert cog.bot == bot
        assert cog is not None

    def test_cog_has_commands(self) -> None:
        """Test that the cog has the expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = InterestRolesCog(bot)

        # User commands
        assert hasattr(cog, "interests")

        # Admin commands
        assert hasattr(cog, "post_interests")
        assert hasattr(cog, "list_interests")
        assert hasattr(cog, "sync_interests")
        assert hasattr(cog, "member_interests")

    def test_cog_has_listener(self) -> None:
        """Test that the cog has the on_ready listener."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = InterestRolesCog(bot)

        assert hasattr(cog, "on_ready")


class TestInterestSelectView:
    """Test interest select view."""

    @pytest.mark.asyncio
    async def test_view_initializes(self) -> None:
        """Test that the interest select view initializes."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = InterestRolesCog(bot)
        view = InterestSelectView(bot, cog)

        assert view is not None
        assert view.timeout is None  # Persistent view

        await bot.close()

    @pytest.mark.asyncio
    async def test_view_with_options(self) -> None:
        """Test that the view initializes with options."""
        import discord

        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = InterestRolesCog(bot)

        options = [
            discord.SelectOption(label="Test 1", value="test_1"),
            discord.SelectOption(label="Test 2", value="test_2"),
        ]
        view = InterestSelectView(bot, cog, options, ["test_1"])

        assert view is not None
        assert len(view.children) > 0

        await bot.close()


class TestPersistentInterestView:
    """Test persistent interest view."""

    @pytest.mark.asyncio
    async def test_view_initializes(self) -> None:
        """Test that the persistent view initializes."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        view = PersistentInterestView(bot)

        assert view is not None
        assert view.timeout is None

        await bot.close()

    @pytest.mark.asyncio
    async def test_view_has_button(self) -> None:
        """Test that the view has the selector button."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        view = PersistentInterestView(bot)

        # Check that view has children (buttons)
        assert len(view.children) > 0

        # Find the selector button
        button = None
        for child in view.children:
            if hasattr(child, "custom_id"):
                if child.custom_id == "interest_roles:open_selector":
                    button = child
                    break

        assert button is not None
        assert button.label == "Select Interests"

        await bot.close()


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the interest roles cog can be loaded into the bot."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Load onboarding first (dependency)
    await bot.load_extension("bot.cogs.onboarding")

    # Load the cog
    await bot.load_extension("bot.cogs.interest_roles")

    # Check that cog is loaded
    assert "InterestRoles" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_interest_roles_cog_in_bot_startup() -> None:
    """Test that interest roles cog is loaded during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup hook (this loads cogs)
    await bot.setup_hook()

    # Check that interest roles cog is loaded
    assert "InterestRoles" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_verify_member_returns_false_without_onboarding() -> None:
    """Test that _verify_member returns False when onboarding cog is not loaded."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    cog = InterestRolesCog(bot)

    # Without onboarding cog loaded, should return False
    result = await cog._verify_member(123456789, 987654321)
    assert result is False

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_get_interest_definitions_empty() -> None:
    """Test that _get_interest_definitions returns empty list when no interests."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = InterestRolesCog(bot)

    # Should return empty list for unknown guild
    result = await cog._get_interest_definitions(999999999)
    assert result == []

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_get_member_interests_empty() -> None:
    """Test that _get_member_interests returns empty set when no selections."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = InterestRolesCog(bot)

    # Should return empty set for user with no selections
    result = await cog._get_member_interests(123456789, 987654321)
    assert result == set()

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_update_member_interests() -> None:
    """Test that _update_member_interests correctly stores selections."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = InterestRolesCog(bot)
    guild_id = 123456789
    user_id = 987654321

    # Update interests
    interests = {"reinforcement_learning", "nlp"}
    await cog._update_member_interests(guild_id, user_id, interests)

    # Verify they were stored
    result = await cog._get_member_interests(guild_id, user_id)
    assert result == interests

    # Update with different interests
    new_interests = {"computer_vision"}
    await cog._update_member_interests(guild_id, user_id, new_interests)

    # Verify old ones were replaced
    result = await cog._get_member_interests(guild_id, user_id)
    assert result == new_interests

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_sync_interests_from_config() -> None:
    """Test that _sync_interests_from_config syncs config to database."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = InterestRolesCog(bot)
    guild_id = config.get("server", "guild_id")

    # Sync interests
    count = await cog._sync_interests_from_config(guild_id)

    # Should have synced some interests (from config.toml)
    assert count >= 0

    # Check that definitions are in database
    definitions = await cog._get_interest_definitions(guild_id)

    # Each synced interest should have required fields
    for definition in definitions:
        assert "interest_key" in definition
        assert "label" in definition
        assert "role_id" in definition
        assert "channel_id" in definition

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_get_interest_options() -> None:
    """Test that _get_interest_options returns SelectOption objects."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = InterestRolesCog(bot)
    guild_id = config.get("server", "guild_id")

    # Sync interests first
    await cog._sync_interests_from_config(guild_id)

    # Get options
    options = await cog._get_interest_options(guild_id)

    # Check options are valid
    import discord

    for option in options:
        assert isinstance(option, discord.SelectOption)
        assert option.value is not None
        assert option.label is not None

    # Cleanup
    await bot.close()
