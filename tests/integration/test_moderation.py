"""Integration tests for the moderation cog.

This module tests the moderation cog against the database, verifying that:
    - Warning operations (add, list, clear) work correctly
    - Mod actions are logged to the database
    - Cog initializes and loads properly

Usage:
    uv run pytest tests/integration/test_moderation.py -v

"""

import pytest

from bot.cogs.moderation import ModerationCog
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestModerationCogInitialization:
    """Test moderation cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the moderation cog initializes correctly."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ModerationCog(bot)

        assert cog.bot is bot
        assert cog.qualified_name == "Moderation"

    def test_cog_has_commands(self) -> None:
        """Test that the moderation cog has all expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = ModerationCog(bot)

        command_names = [cmd.name for cmd in cog.get_commands()]

        assert "kick" in command_names
        assert "ban" in command_names
        assert "timeout" in command_names
        assert "warn" in command_names
        assert "warnings" in command_names
        assert "clearwarnings" in command_names


class TestWarningsDatabase:
    """Test warning database operations."""

    @pytest.mark.asyncio
    async def test_add_warning(self) -> None:
        """Test adding a warning to the database."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists (foreign key)
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert warning
        await bot.db.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (123456, 789012, 345678, "Test warning", 1),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM warnings WHERE user_id = ?",
            (789012,),
        )

        assert row is not None
        assert row["reason"] == "Test warning"
        assert row["severity"] == 1
        assert row["guild_id"] == 123456
        assert row["moderator_id"] == 345678

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_count_user_warnings(self) -> None:
        """Test counting warnings for a user."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert multiple warnings
        for i in range(3):
            await bot.db.execute(
                """
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (123456, 789012, 345678, f"Warning {i + 1}", 1),
            )

        # Count
        row = await bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (123456, 789012),
        )

        assert row is not None
        assert row["count"] == 3

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_delete_specific_warning(self) -> None:
        """Test deleting a specific warning by ID."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert warning
        await bot.db.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (123456, 789012, 345678, "Test warning", 1),
        )

        # Get warning ID
        row = await bot.db.fetch_one(
            "SELECT id FROM warnings WHERE guild_id = ? AND user_id = ?",
            (123456, 789012),
        )
        warning_id = row["id"]

        # Delete
        await bot.db.execute(
            "DELETE FROM warnings WHERE id = ?",
            (warning_id,),
        )

        # Verify deleted
        row = await bot.db.fetch_one(
            "SELECT * FROM warnings WHERE id = ?",
            (warning_id,),
        )

        assert row is None

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_clear_all_user_warnings(self) -> None:
        """Test clearing all warnings for a user."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert multiple warnings
        for i in range(3):
            await bot.db.execute(
                """
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (123456, 789012, 345678, f"Warning {i + 1}", 1),
            )

        # Clear all
        await bot.db.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (123456, 789012),
        )

        # Verify all deleted
        row = await bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (123456, 789012),
        )

        assert row["count"] == 0

        await bot.db.close()


class TestModActionsDatabase:
    """Test mod_actions database operations."""

    @pytest.mark.asyncio
    async def test_log_mod_action(self) -> None:
        """Test logging a moderation action."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log action
        await bot.db.execute(
            """
            INSERT INTO mod_actions
            (guild_id, action_type, target_user_id, moderator_id,
             reason, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, "kick", 789012, 345678, "Test kick", None),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM mod_actions WHERE target_user_id = ?",
            (789012,),
        )

        assert row is not None
        assert row["action_type"] == "kick"
        assert row["reason"] == "Test kick"

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_log_timeout_with_duration(self) -> None:
        """Test logging a timeout action with duration."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log timeout action with duration (1 hour = 3600 seconds)
        await bot.db.execute(
            """
            INSERT INTO mod_actions
            (guild_id, action_type, target_user_id, moderator_id,
             reason, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, "timeout", 789012, 345678, "Test timeout", 3600),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM mod_actions WHERE action_type = 'timeout'",
            (),
        )

        assert row is not None
        assert row["duration_seconds"] == 3600

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_query_mod_actions_by_user(self) -> None:
        """Test querying mod actions for a specific user."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log multiple actions for same user
        actions = [
            ("warn", "First warning"),
            ("warn", "Second warning"),
            ("timeout", "Timeout after warnings"),
        ]
        for action_type, reason in actions:
            await bot.db.execute(
                """
                INSERT INTO mod_actions
                (guild_id, action_type, target_user_id, moderator_id, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (123456, action_type, 789012, 345678, reason),
            )

        # Query all actions for user
        rows = await bot.db.fetch_all(
            """
            SELECT * FROM mod_actions
            WHERE guild_id = ? AND target_user_id = ?
            ORDER BY created_at
            """,
            (123456, 789012),
        )

        assert len(rows) == 3
        assert rows[0]["action_type"] == "warn"
        assert rows[2]["action_type"] == "timeout"

        await bot.db.close()


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the moderation cog loads without errors."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    await bot.db.connect()
    await bot.db.apply_migrations()

    # Load the cog
    await bot.load_extension("bot.cogs.moderation")

    # Verify cog is loaded
    assert "Moderation" in bot.cogs

    await bot.db.close()


@pytest.mark.asyncio
async def test_moderation_cog_in_bot_startup() -> None:
    """Test that moderation cog loads during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup_hook which loads all cogs
    await bot.setup_hook()

    # Verify moderation cog is loaded
    assert "Moderation" in bot.cogs

    await bot.db.close()
