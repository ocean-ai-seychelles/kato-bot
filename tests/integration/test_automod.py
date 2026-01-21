"""Integration tests for the auto-moderation cog.

This module tests the automod cog against the database, verifying that:
    - Violation logging works correctly
    - Banned words CRUD operations work
    - Rate limit cache operations work
    - Cog initializes and loads properly

Usage:
    uv run pytest tests/integration/test_automod.py -v

"""

import pytest

from bot.cogs.automod import AutoModCog
from bot.core.bot import DoryBot
from bot.core.config import Config


class TestAutoModCogInitialization:
    """Test automod cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the automod cog initializes correctly."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)
        cog = AutoModCog(bot)

        assert cog.bot is bot
        assert cog.qualified_name == "AutoMod"

    def test_cog_has_commands(self) -> None:
        """Test that the automod cog has all expected commands."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)
        cog = AutoModCog(bot)

        command_names = [cmd.name for cmd in cog.get_commands()]

        assert "addword" in command_names
        assert "addregex" in command_names
        assert "removeword" in command_names
        assert "listwords" in command_names
        assert "automod" in command_names


class TestBannedWordsDatabase:
    """Test banned words database operations."""

    @pytest.mark.asyncio
    async def test_add_banned_word(self) -> None:
        """Test adding a banned word to the database."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists (foreign key)
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert banned word
        await bot.db.execute(
            "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
            (123456, "badword"),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM banned_words WHERE word = ?",
            ("badword",),
        )

        assert row is not None
        assert row["word"] == "badword"
        assert row["is_regex"] == 0
        assert row["guild_id"] == 123456

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_add_banned_regex(self) -> None:
        """Test adding a banned regex pattern to the database."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert regex pattern
        await bot.db.execute(
            "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 1)",
            (123456, r"test\d+"),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM banned_words WHERE word = ?",
            (r"test\d+",),
        )

        assert row is not None
        assert row["word"] == r"test\d+"
        assert row["is_regex"] == 1

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_remove_banned_word(self) -> None:
        """Test removing a banned word from the database."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert then remove
        await bot.db.execute(
            "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
            (123456, "removetest"),
        )

        result = await bot.db.execute(
            "DELETE FROM banned_words WHERE guild_id = ? AND word = ?",
            (123456, "removetest"),
        )

        assert result.rowcount == 1

        # Verify deleted
        row = await bot.db.fetch_one(
            "SELECT * FROM banned_words WHERE word = ?",
            ("removetest",),
        )

        assert row is None

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_list_banned_words(self) -> None:
        """Test listing all banned words for a guild."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert multiple words
        words = ["word1", "word2", "word3"]
        for word in words:
            await bot.db.execute(
                "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
                (123456, word),
            )

        # List all
        rows = await bot.db.fetch_all(
            "SELECT word FROM banned_words WHERE guild_id = ? ORDER BY word",
            (123456,),
        )

        assert len(rows) == 3
        assert [row["word"] for row in rows] == words

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_banned_word_unique_constraint(self) -> None:
        """Test that duplicate banned words are rejected."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Insert first time
        await bot.db.execute(
            "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
            (123456, "duplicate"),
        )

        # Insert again should fail (UNIQUE constraint)
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            await bot.db.execute(
                "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
                (123456, "duplicate"),
            )

        await bot.db.close()


class TestAutoModViolationsDatabase:
    """Test automod_violations database operations."""

    @pytest.mark.asyncio
    async def test_log_violation(self) -> None:
        """Test logging an auto-mod violation."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log violation
        await bot.db.execute(
            """
            INSERT INTO automod_violations
            (guild_id, user_id, channel_id, violation_type,
             message_content, action_taken)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (123456, 789012, 111222, "spam", "test content", "deleted"),
        )

        # Verify
        row = await bot.db.fetch_one(
            "SELECT * FROM automod_violations WHERE user_id = ?",
            (789012,),
        )

        assert row is not None
        assert row["violation_type"] == "spam"
        assert row["action_taken"] == "deleted"
        assert row["message_content"] == "test content"

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_log_different_violation_types(self) -> None:
        """Test logging different violation types."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log different violation types
        violations = [
            ("spam", "deleted"),
            ("caps", "deleted"),
            ("mentions", "timeout"),
            ("banned_word", "warned"),
        ]

        for violation_type, action in violations:
            await bot.db.execute(
                """
                INSERT INTO automod_violations
                (guild_id, user_id, channel_id, violation_type,
                 message_content, action_taken)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (123456, 789012, 111222, violation_type, "test", action),
            )

        # Verify all logged
        rows = await bot.db.fetch_all(
            """
            SELECT violation_type, action_taken
            FROM automod_violations WHERE user_id = ?
            """,
            (789012,),
        )

        assert len(rows) == 4
        violation_types = [row["violation_type"] for row in rows]
        assert "spam" in violation_types
        assert "caps" in violation_types
        assert "mentions" in violation_types
        assert "banned_word" in violation_types

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_query_violations_by_type(self) -> None:
        """Test querying violations by type."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Ensure guild config exists
        await bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (123456,),
        )

        # Log multiple spam violations
        for i in range(3):
            await bot.db.execute(
                """
                INSERT INTO automod_violations
                (guild_id, user_id, channel_id, violation_type,
                 message_content, action_taken)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (123456, 789012, 111222, "spam", f"spam msg {i}", "deleted"),
            )

        # Query by type
        rows = await bot.db.fetch_all(
            """
            SELECT * FROM automod_violations
            WHERE guild_id = ? AND violation_type = ?
            """,
            (123456, "spam"),
        )

        assert len(rows) == 3

        await bot.db.close()


class TestRateLimitCacheDatabase:
    """Test rate_limit_cache database operations."""

    @pytest.mark.asyncio
    async def test_create_rate_limit_entry(self) -> None:
        """Test creating a rate limit cache entry."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Insert entry
        await bot.db.execute(
            """
            INSERT INTO rate_limit_cache
            (user_id, channel_id, message_count, window_start)
            VALUES (?, ?, 1, datetime('now'))
            """,
            (789012, 111222),
        )

        # Verify
        row = await bot.db.fetch_one(
            """
            SELECT * FROM rate_limit_cache
            WHERE user_id = ? AND channel_id = ?
            """,
            (789012, 111222),
        )

        assert row is not None
        assert row["message_count"] == 1

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_update_rate_limit_count(self) -> None:
        """Test incrementing rate limit count."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Insert entry
        await bot.db.execute(
            """
            INSERT INTO rate_limit_cache
            (user_id, channel_id, message_count, window_start)
            VALUES (?, ?, 1, datetime('now'))
            """,
            (789012, 111222),
        )

        # Update count
        await bot.db.execute(
            """
            UPDATE rate_limit_cache
            SET message_count = message_count + 1
            WHERE user_id = ? AND channel_id = ?
            """,
            (789012, 111222),
        )

        # Verify
        row = await bot.db.fetch_one(
            """
            SELECT message_count FROM rate_limit_cache
            WHERE user_id = ? AND channel_id = ?
            """,
            (789012, 111222),
        )

        assert row["message_count"] == 2

        await bot.db.close()

    @pytest.mark.asyncio
    async def test_reset_rate_limit_window(self) -> None:
        """Test resetting rate limit window."""
        config = Config("assets/config.toml")
        bot = DoryBot(config)

        await bot.db.connect()
        await bot.db.apply_migrations()

        # Insert entry with high count
        await bot.db.execute(
            """
            INSERT INTO rate_limit_cache
            (user_id, channel_id, message_count, window_start)
            VALUES (?, ?, 10, datetime('now', '-1 hour'))
            """,
            (789012, 111222),
        )

        # Reset
        await bot.db.execute(
            """
            UPDATE rate_limit_cache
            SET message_count = 1, window_start = datetime('now')
            WHERE user_id = ? AND channel_id = ?
            """,
            (789012, 111222),
        )

        # Verify
        row = await bot.db.fetch_one(
            """
            SELECT message_count FROM rate_limit_cache
            WHERE user_id = ? AND channel_id = ?
            """,
            (789012, 111222),
        )

        assert row["message_count"] == 1

        await bot.db.close()


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the automod cog loads without errors."""
    config = Config("assets/config.toml")
    bot = DoryBot(config)

    await bot.db.connect()
    await bot.db.apply_migrations()

    # Load the cog
    await bot.load_extension("bot.cogs.automod")

    # Verify cog is loaded
    assert "AutoMod" in bot.cogs

    await bot.db.close()


@pytest.mark.asyncio
async def test_automod_cog_in_bot_startup() -> None:
    """Test that automod cog loads during bot startup."""
    config = Config("assets/config.toml")
    bot = DoryBot(config)

    # Run setup_hook which loads all cogs
    await bot.setup_hook()

    # Verify automod cog is loaded
    assert "AutoMod" in bot.cogs

    await bot.db.close()
