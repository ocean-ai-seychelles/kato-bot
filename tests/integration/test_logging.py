"""Integration tests for the audit logging cog.

This module tests the logging cog against the database, verifying that:
    - Message events are logged correctly
    - Cog initializes and loads properly
    - Audit commands work correctly

Usage:
    uv run pytest tests/integration/test_logging.py -v

"""

import pytest

from bot.cogs.logging import LoggingCog
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestLoggingCogInitialization:
    """Test logging cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the logging cog initializes correctly."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = LoggingCog(bot)

        assert cog.bot is bot
        assert cog.qualified_name == "Logging"

    def test_cog_has_commands(self) -> None:
        """Test that the logging cog has all expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = LoggingCog(bot)

        command_names = [cmd.name for cmd in cog.get_commands()]

        assert "audit" in command_names
        assert "messagelog" in command_names


class TestMessageLogsDatabase:
    """Test message_logs database operations."""

    @pytest.mark.asyncio
    async def test_log_message_edit(self) -> None:
        """Test logging a message edit event."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists (foreign key)
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log edit event
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 333444, 789012, "original content", "edited"),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM message_logs WHERE message_id = ?",
            (333444,),
        )

        assert row is not None
        assert row["event_type"] == "edited"
        assert row["content"] == "original content"
        assert row["author_id"] == 789012

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_log_message_delete(self) -> None:
        """Test logging a message delete event."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log delete event
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 555666, 789012, "deleted content", "deleted"),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM message_logs WHERE message_id = ?",
            (555666,),
        )

        assert row is not None
        assert row["event_type"] == "deleted"
        assert row["content"] == "deleted content"

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_query_logs_by_author(self) -> None:
        """Test querying message logs for a specific author."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log multiple events for same author
        events = [
            ("edited", "first edit"),
            ("deleted", "deleted message"),
            ("edited", "second edit"),
        ]

        for i, (event_type, content) in enumerate(events):
            await bot.db.execute(
                """
                INSERT INTO message_logs
                (guild_id, channel_id, message_id, author_id,
                 content, event_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (123456, 111222, 1000 + i, 789012, content, event_type),
            )

        # Query by author
        rows = await bot.db.fetch_all(
            """
            SELECT event_type, content FROM message_logs
            WHERE guild_id = ? AND author_id = ?
            ORDER BY created_at
            """,
            (123456, 789012),
        )

        assert len(rows) == 3
        assert rows[0]["event_type"] == "edited"
        assert rows[1]["event_type"] == "deleted"
        assert rows[2]["event_type"] == "edited"

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_query_logs_by_event_type(self) -> None:
        """Test querying message logs by event type."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log multiple events
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 1001, 789012, "edit 1", "edited"),
        )
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 1002, 789012, "delete 1", "deleted"),
        )
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 1003, 789012, "edit 2", "edited"),
        )

        # Query only edits
        rows = await bot.db.fetch_all(
            """
            SELECT * FROM message_logs
            WHERE guild_id = ? AND event_type = 'edited'
            """,
            (123456,),
        )

        assert len(rows) == 2

        await bot.db.close()


class TestAuditLogQueries:
    """Test audit log query operations."""

    @pytest.mark.asyncio
    async def test_combined_audit_query(self) -> None:
        """Test querying combined audit data for a user."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Add message log
        await bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 111222, 1001, 789012, "test message", "deleted"),
        )

        # Add warning
        await bot.db.execute(
            """
            INSERT INTO warnings
            (guild_id, user_id, moderator_id, reason, severity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (123456, 789012, 345678, "Test warning", 1),
        )

        # Add mod action
        await bot.db.execute(
            """
            INSERT INTO mod_actions
            (guild_id, action_type, target_user_id, moderator_id, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (123456, "warn", 789012, 345678, "Warning issued"),
        )

        # Query all data for user
        message_logs = await bot.db.fetch_all(
            "SELECT * FROM message_logs WHERE author_id = ?",
            (789012,),
        )
        warnings = await bot.db.fetch_all(
            "SELECT * FROM warnings WHERE user_id = ?",
            (789012,),
        )
        mod_actions = await bot.db.fetch_all(
            "SELECT * FROM mod_actions WHERE target_user_id = ?",
            (789012,),
        )

        assert len(message_logs) == 1
        assert len(warnings) == 1
        assert len(mod_actions) == 1

        await bot.db.close()


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the logging cog loads without errors."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    await bot.db.connect()
    await bot.db.apply_migrations()

    # Load the cog
    await bot.load_extension("bot.cogs.logging")

    # Verify cog is loaded
    assert "Logging" in bot.cogs

    await bot.db.close()


@pytest.mark.asyncio
async def test_logging_cog_in_bot_startup() -> None:
    """Test that logging cog loads during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup_hook which loads all cogs
    await bot.setup_hook()

    # Verify logging cog is loaded
    assert "Logging" in bot.cogs

    await bot.db.close()
