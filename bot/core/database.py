"""Database connection and management for Dory bot.

This module provides an async SQLite database layer using aiosqlite. It handles
database connection management, schema initialization via migrations, and
provides helper methods for common database operations.

The database layer is designed to:
    - Use async/await for non-blocking database operations
    - Apply schema migrations automatically on startup
    - Provide connection pooling via a single shared connection
    - Support proper cleanup on shutdown

Example:
    >>> from bot.core.database import Database
    >>> db = Database("data/dory.db")
    >>> await db.connect()
    >>> await db.apply_migrations()
    >>> await db.close()

"""

from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    """Async SQLite database connection manager.

    This class manages a single database connection and provides methods for
    initializing the schema, applying migrations, and executing queries.

    Attributes:
        db_path: Path to the SQLite database file.
        connection: The aiosqlite database connection (None until connected).

    Example:
        >>> db = Database("data/dory.db")
        >>> await db.connect()
        >>> try:
        >>>     rows = await db.fetch_all("SELECT * FROM guild_config")
        >>> finally:
        >>>     await db.close()

    """

    def __init__(self, db_path: str = "data/dory.db") -> None:
        """Initialize database with file path.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                "data/dory.db". Parent directories will be created if
                they don't exist.

        """
        self.db_path = Path(db_path)
        self.connection: aiosqlite.Connection | None = None

        # Ensure the data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self) -> None:
        """Establish database connection.

        This opens an async connection to the SQLite database and enables
        foreign key constraints.

        Raises:
            RuntimeError: If already connected.

        """
        if self.connection is not None:
            raise RuntimeError("Database is already connected")

        self.connection = await aiosqlite.connect(str(self.db_path))
        # Enable foreign key constraints
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.commit()

    async def close(self) -> None:
        """Close database connection gracefully.

        This ensures all pending transactions are committed and the connection
        is properly closed. Safe to call multiple times.
        """
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    async def apply_migrations(self) -> None:
        """Apply database migrations from migrations/ directory.

        This reads SQL migration files and applies them in order if they
        haven't been applied yet. Migrations are tracked in the
        schema_migrations table.

        Raises:
            RuntimeError: If not connected to database.
            FileNotFoundError: If migrations directory doesn't exist.

        """
        if self.connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        migrations_dir = Path("migrations")
        if not migrations_dir.exists():
            # No migrations directory yet, skip
            return

        # Get list of migration files
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            # Extract version number from filename (e.g., 001_initial_schema.sql -> 1)
            version = int(migration_file.stem.split("_")[0])

            # Check if this migration has already been applied
            cursor = await self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='schema_migrations'"
            )
            table_exists = await cursor.fetchone()
            await cursor.close()

            if table_exists:
                cursor = await self.connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                )
                applied = await cursor.fetchone()
                await cursor.close()

                if applied:
                    # Migration already applied, skip
                    continue

            # Read and execute the migration
            with open(migration_file) as f:
                migration_sql = f.read()

            await self.connection.executescript(migration_sql)
            await self.connection.commit()

    async def execute(
        self, query: str, parameters: tuple[Any, ...] = ()
    ) -> aiosqlite.Cursor:
        """Execute a query that doesn't return results (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string with ? placeholders.
            parameters: Tuple of parameters to bind to the query.

        Returns:
            The cursor from the executed query.

        Raises:
            RuntimeError: If not connected to database.

        Example:
            >>> await db.execute(
            ...     "INSERT INTO warnings (guild_id, user_id, reason) VALUES (?, ?, ?)",
            ...     (12345, 67890, "Spam")
            ... )

        """
        if self.connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        cursor = await self.connection.execute(query, parameters)
        await self.connection.commit()
        return cursor

    async def fetch_one(
        self, query: str, parameters: tuple[Any, ...] = ()
    ) -> aiosqlite.Row | None:
        """Execute a query and fetch a single row.

        Args:
            query: SQL query string with ? placeholders.
            parameters: Tuple of parameters to bind to the query.

        Returns:
            A single row from the query result, or None if no results.

        Raises:
            RuntimeError: If not connected to database.

        Example:
            >>> row = await db.fetch_one(
            ...     "SELECT * FROM guild_config WHERE guild_id = ?",
            ...     (12345,)
            ... )
            >>> if row:
            ...     print(f"Welcome channel: {row['welcome_channel_id']}")

        """
        if self.connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        cursor = await self.connection.execute(query, parameters)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetch_all(
        self, query: str, parameters: tuple[Any, ...] = ()
    ) -> list[aiosqlite.Row]:
        """Execute a query and fetch all rows.

        Args:
            query: SQL query string with ? placeholders.
            parameters: Tuple of parameters to bind to the query.

        Returns:
            List of rows from the query result (empty list if no results).

        Raises:
            RuntimeError: If not connected to database.

        Example:
            >>> rows = await db.fetch_all(
            ...     "SELECT * FROM warnings WHERE user_id = ?",
            ...     (67890,)
            ... )
            >>> print(f"User has {len(rows)} warnings")

        """
        if self.connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        cursor = await self.connection.execute(query, parameters)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    def __repr__(self) -> str:
        """Return a string representation of the Database object.

        Returns:
            String showing the database file path and connection status.

        """
        status = "connected" if self.connection else "disconnected"
        return f"Database(path={self.db_path}, status={status})"
