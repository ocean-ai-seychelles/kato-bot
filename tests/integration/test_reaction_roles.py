"""Integration tests for the reaction role system.

This module tests the reaction roles cog against the database, verifying that:
    - Reaction role mappings are stored and retrieved correctly
    - Database sync from config works
    - Cog initializes and loads properly
    - Admin commands function as expected

Usage:
    uv run pytest tests/integration/test_reaction_roles.py -v
"""

from unittest.mock import patch

import pytest

from bot.cogs.reaction_roles import ReactionRolesCog
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestReactionRoleMappings:
    """Test reaction role mapping database operations."""

    @pytest.mark.asyncio
    async def test_get_reaction_role_mapping_returns_role_id(self) -> None:
        """Test that _get_reaction_role_mapping returns the correct role ID."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        # Connect database
        await bot.db.connect()
        await bot.db.apply_migrations()

        # Insert guild_config first (to satisfy foreign key)
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert a test mapping
        await bot.db.execute(
            """
            INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)
            """,
            (123456, 789012, "✅", 345678),
        )

        # Test retrieval
        role_id = await cog._get_reaction_role_mapping(789012, "✅")

        assert role_id == 345678

        # Cleanup
        await bot.db.close()

    @pytest.mark.asyncio
    async def test_get_reaction_role_mapping_returns_none_when_not_found(self) -> None:
        """Test that _get_reaction_role_mapping returns None when no mapping exists."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        # Connect database
        await bot.db.connect()
        await bot.db.apply_migrations()

        # Test retrieval for non-existent mapping
        role_id = await cog._get_reaction_role_mapping(999999, "❌")

        assert role_id is None

        # Cleanup
        await bot.db.close()

    @pytest.mark.asyncio
    async def test_sync_reaction_roles_from_config(self) -> None:
        """Test that reaction roles are synced from config to database."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        # Connect database
        await bot.db.connect()
        await bot.db.apply_migrations()

        # Insert guild_config first (to satisfy foreign key)
        guild_id = config.get("server", "guild_id")
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

        # Get expected values from config
        message_id = config.get("reaction_roles", "message_id")
        mappings = config.get("reaction_roles", "mappings", default=[])

        # Sync from config
        await cog._sync_reaction_roles_from_config(guild_id)

        # Verify mappings were created
        db_mappings = await bot.db.fetch_all(
            "SELECT * FROM reaction_roles WHERE message_id = ?",
            (message_id,),
        )

        assert len(db_mappings) == len(mappings)

        # Verify each mapping
        for i, mapping in enumerate(mappings):
            assert db_mappings[i]["emoji"] == mapping["emoji"]
            assert db_mappings[i]["role_id"] == mapping["role_id"]
            assert db_mappings[i]["message_id"] == message_id

        # Cleanup
        await bot.db.close()

    @pytest.mark.asyncio
    async def test_sync_clears_old_mappings_for_message(self) -> None:
        """Test that syncing clears old mappings for the same message."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        # Connect database
        await bot.db.connect()
        await bot.db.apply_migrations()

        # Use a test message_id and mock the config to return it
        test_message_id = 123456789
        test_mappings = [{"emoji": "✅", "role_id": 111111}]
        guild_id = config.get("server", "guild_id")

        # Insert guild_config first (to satisfy foreign key)
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

        # Insert an old mapping that's not in config
        await bot.db.execute(
            """
            INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, test_message_id, "❌", 999999),
        )

        # Mock config to return valid reaction_roles settings
        def mock_get(section: str, key: str, default=None):
            if section == "reaction_roles" and key == "message_id":
                return test_message_id
            if section == "reaction_roles" and key == "mappings":
                return test_mappings
            return config.get(section, key, default=default)

        # Sync from config (should clear old mapping and add new ones)
        with patch.object(bot.config, "get", side_effect=mock_get):
            await cog._sync_reaction_roles_from_config(guild_id)

        # Verify old mapping was removed
        old_mapping = await bot.db.fetch_one(
            "SELECT * FROM reaction_roles WHERE emoji = ?",
            ("❌",),
        )

        assert old_mapping is None

        # Verify new mapping was added
        new_mapping = await bot.db.fetch_one(
            "SELECT * FROM reaction_roles WHERE emoji = ?",
            ("✅",),
        )
        assert new_mapping is not None
        assert new_mapping["role_id"] == 111111

        # Cleanup
        await bot.db.close()


class TestReactionRolesCogInitialization:
    """Test reaction roles cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the reaction roles cog initializes successfully."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        assert cog.bot == bot
        assert cog is not None

    def test_cog_has_listeners(self) -> None:
        """Test that the cog has the expected event listeners."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        assert hasattr(cog, "on_ready")
        assert hasattr(cog, "on_raw_reaction_add")
        assert hasattr(cog, "on_raw_reaction_remove")

    def test_cog_has_commands(self) -> None:
        """Test that the cog has the expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ReactionRolesCog(bot)

        # Check for command existence
        assert hasattr(cog, "add_reaction_role")
        assert hasattr(cog, "remove_reaction_role")
        assert hasattr(cog, "list_reaction_roles")
        assert hasattr(cog, "sync_reaction_roles")


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the reaction roles cog can be loaded into the bot."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Load the cog
    await bot.load_extension("bot.cogs.reaction_roles")

    # Check that cog is loaded
    assert "ReactionRoles" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_reaction_roles_cog_in_bot_startup() -> None:
    """Test that reaction roles cog is loaded during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup hook (this loads cogs)
    await bot.setup_hook()

    # Check that reaction roles cog is loaded
    assert "ReactionRoles" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_reaction_roles_synced_on_ready() -> None:
    """Test that reaction roles are synced from config when bot starts."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup hook
    await bot.setup_hook()

    # Get the cog
    cog = bot.cogs.get("ReactionRoles")
    assert cog is not None

    # Manually trigger on_ready to sync
    await cog.on_ready()

    # Verify mappings were synced
    message_id = config.get("reaction_roles", "message_id")
    mappings = await bot.db.fetch_all(
        "SELECT * FROM reaction_roles WHERE message_id = ?",
        (message_id,),
    )

    expected_mappings = config.get("reaction_roles", "mappings", default=[])
    assert len(mappings) == len(expected_mappings)

    # Cleanup
    await bot.close()
