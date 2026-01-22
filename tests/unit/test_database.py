"""Unit tests for database layer.

This module tests the Database class in bot.core.database, verifying:
    - Connection lifecycle (connect, close)
    - Migration system (apply_migrations)
    - Query helpers (execute, fetch_one, fetch_all)
    - Error handling for invalid states
    - Database initialization and cleanup

These tests use temporary in-memory SQLite databases to avoid side effects.

Usage:
    uv run pytest tests/unit/test_database.py -v
"""

from pathlib import Path

import pytest

from bot.core.database import Database


class TestDatabaseConnection:
    """Test suite for Database connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_creates_connection(self, tmp_path: Path) -> None:
        """Test that connect() establishes a database connection."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        assert db.connection is None

        await db.connect()

        assert db.connection is not None
        assert db_path.exists()

        await db.close()

    @pytest.mark.asyncio
    async def test_connect_twice_raises_error(self, tmp_path: Path) -> None:
        """Test that connecting twice raises RuntimeError."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        await db.connect()

        with pytest.raises(RuntimeError) as exc_info:
            await db.connect()

        assert "already connected" in str(exc_info.value)

        await db.close()

    @pytest.mark.asyncio
    async def test_close_without_connect_is_safe(self, tmp_path: Path) -> None:
        """Test that closing without connecting doesn't raise an error."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        # Should not raise
        await db.close()

        assert db.connection is None

    @pytest.mark.asyncio
    async def test_close_sets_connection_to_none(self, tmp_path: Path) -> None:
        """Test that close() properly cleans up connection."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        await db.connect()
        assert db.connection is not None

        await db.close()
        assert db.connection is None

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        """Test that foreign key constraints are enabled."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        await db.connect()

        cursor = await db.connection.execute("PRAGMA foreign_keys")
        result = await cursor.fetchone()
        await cursor.close()

        assert result[0] == 1  # 1 means enabled

        await db.close()

    def test_repr_shows_status(self, tmp_path: Path) -> None:
        """Test that __repr__ shows connection status."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))

        repr_str = repr(db)
        assert "disconnected" in repr_str
        assert str(db_path) in repr_str


class TestDatabaseQueries:
    """Test suite for Database query helpers."""

    @pytest.mark.asyncio
    async def test_execute_without_connection_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that execute() raises error when not connected."""
        db = Database(str(tmp_path / "test.db"))

        with pytest.raises(RuntimeError) as exc_info:
            await db.execute("SELECT 1")

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_one_without_connection_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that fetch_one() raises error when not connected."""
        db = Database(str(tmp_path / "test.db"))

        with pytest.raises(RuntimeError) as exc_info:
            await db.fetch_one("SELECT 1")

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_all_without_connection_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that fetch_all() raises error when not connected."""
        db = Database(str(tmp_path / "test.db"))

        with pytest.raises(RuntimeError) as exc_info:
            await db.fetch_all("SELECT 1")

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_inserts_data(self, tmp_path: Path) -> None:
        """Test that execute() successfully inserts data."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()

        # Create test table
        await db.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")

        # Insert data
        cursor = await db.execute(
            "INSERT INTO test_table (name) VALUES (?)", ("test_name",)
        )

        assert cursor.lastrowid == 1

        await db.close()

    @pytest.mark.asyncio
    async def test_fetch_one_returns_single_row(self, tmp_path: Path) -> None:
        """Test that fetch_one() returns a single row."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()

        # Create and populate test table
        await db.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("INSERT INTO test_table (name) VALUES (?)", ("first",))
        await db.execute("INSERT INTO test_table (name) VALUES (?)", ("second",))

        # Fetch one row
        row = await db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("first",))

        assert row is not None
        assert row["name"] == "first"

        await db.close()

    @pytest.mark.asyncio
    async def test_fetch_one_returns_none_when_no_results(self, tmp_path: Path) -> None:
        """Test that fetch_one() returns None when no results found."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()

        # Create empty test table
        await db.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")

        # Fetch from empty table
        row = await db.fetch_one(
            "SELECT * FROM test_table WHERE name = ?", ("missing",)
        )

        assert row is None

        await db.close()

    @pytest.mark.asyncio
    async def test_fetch_all_returns_multiple_rows(self, tmp_path: Path) -> None:
        """Test that fetch_all() returns all matching rows."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()

        # Create and populate test table
        await db.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("INSERT INTO test_table (name) VALUES (?)", ("first",))
        await db.execute("INSERT INTO test_table (name) VALUES (?)", ("second",))
        await db.execute("INSERT INTO test_table (name) VALUES (?)", ("third",))

        # Fetch all rows
        rows = await db.fetch_all("SELECT * FROM test_table ORDER BY id")

        assert len(rows) == 3
        assert rows[0]["name"] == "first"
        assert rows[1]["name"] == "second"
        assert rows[2]["name"] == "third"

        await db.close()

    @pytest.mark.asyncio
    async def test_fetch_all_returns_empty_list_when_no_results(
        self, tmp_path: Path
    ) -> None:
        """Test that fetch_all() returns empty list when no results found."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()

        # Create empty test table
        await db.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")

        # Fetch from empty table
        rows = await db.fetch_all("SELECT * FROM test_table")

        assert rows == []

        await db.close()


class TestDatabaseMigrations:
    """Test suite for Database migration system."""

    @pytest.mark.asyncio
    async def test_apply_migrations_without_connection_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that apply_migrations() raises error when not connected."""
        db = Database(str(tmp_path / "test.db"))

        with pytest.raises(RuntimeError) as exc_info:
            await db.apply_migrations()

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_apply_migrations_with_no_migrations_dir(
        self, tmp_path: Path
    ) -> None:
        """Test that apply_migrations() handles missing migrations directory."""
        # Change to temp directory where migrations/ doesn't exist
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            db = Database(str(tmp_path / "test.db"))
            await db.connect()

            # Should not raise error
            await db.apply_migrations()

            await db.close()
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_apply_migrations_creates_schema_migrations_table(
        self, tmp_path: Path
    ) -> None:
        """Test that migrations create the schema_migrations tracking table."""
        import os

        original_cwd = os.getcwd()

        # Create migrations directory in temp location
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create a simple migration file
        migration_file = migrations_dir / "001_test_migration.sql"
        migration_file.write_text(
            """
CREATE TABLE IF NOT EXISTS test_table (
    id INTEGER PRIMARY KEY,
    name TEXT
);

-- Track this migration
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version) VALUES (1);
"""
        )

        os.chdir(tmp_path)

        try:
            db = Database(str(tmp_path / "test.db"))
            await db.connect()

            await db.apply_migrations()

            # Verify schema_migrations table exists
            row = await db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='schema_migrations'"
            )
            assert row is not None

            # Verify migration was applied
            migration_row = await db.fetch_one(
                "SELECT version FROM schema_migrations WHERE version = 1"
            )
            assert migration_row is not None

            await db.close()
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_migrations_only_applied_once(self, tmp_path: Path) -> None:
        """Test that migrations are not re-applied on subsequent runs."""
        import os

        original_cwd = os.getcwd()

        # Create migrations directory
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create a migration that would fail if run twice
        migration_file = migrations_dir / "001_test_migration.sql"
        migration_file.write_text(
            """
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

INSERT INTO test_table (name) VALUES ('unique_value');

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version) VALUES (1);
"""
        )

        os.chdir(tmp_path)

        try:
            db = Database(str(tmp_path / "test.db"))
            await db.connect()

            # Apply migrations first time
            await db.apply_migrations()

            # Apply migrations second time (should skip already applied)
            await db.apply_migrations()

            # Verify only one row in test_table (migration not re-run)
            rows = await db.fetch_all("SELECT * FROM test_table")
            assert len(rows) == 1

            await db.close()
        finally:
            os.chdir(original_cwd)


class TestDatabaseInitialization:
    """Test suite for Database initialization."""

    def test_db_path_created_if_missing(self, tmp_path: Path) -> None:
        """Test that database directory is created if it doesn't exist."""
        nested_path = tmp_path / "nested" / "data" / "test.db"

        # Directory shouldn't exist yet
        assert not nested_path.parent.exists()

        Database(str(nested_path))

        # Directory should be created
        assert nested_path.parent.exists()

    def test_default_db_path(self) -> None:
        """Test that default database path is data/kato.db."""
        db = Database()

        assert db.db_path == Path("data/kato.db")
