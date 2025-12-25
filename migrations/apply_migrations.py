"""Standalone migration runner for Dory bot database.

This script can be run independently to apply database migrations without
starting the bot. Useful for database maintenance and initial setup.

Usage:
    python migrations/apply_migrations.py [--db-path PATH]

Example:
    # Apply migrations to default database
    python migrations/apply_migrations.py

    # Apply migrations to custom database
    python migrations/apply_migrations.py --db-path /path/to/custom.db

"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.core.database import Database


async def apply_migrations(db_path: str) -> None:
    """Apply all pending migrations to the database.

    Args:
        db_path: Path to the SQLite database file.

    """
    print(f"Applying migrations to database: {db_path}")

    db = Database(db_path)

    try:
        await db.connect()
        print("✓ Connected to database")

        await db.apply_migrations()
        print("✓ Migrations applied successfully")

        # Verify schema by checking if tables exist
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        print(f"✓ Database contains {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")

    except Exception as e:
        print(f"✗ Error applying migrations: {e}", file=sys.stderr)
        raise
    finally:
        await db.close()
        print("✓ Database connection closed")


def main() -> None:
    """Parse arguments and run migration script."""
    parser = argparse.ArgumentParser(
        description="Apply database migrations for Dory bot"
    )
    parser.add_argument(
        "--db-path",
        default="data/dory.db",
        help="Path to the SQLite database file (default: data/dory.db)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(apply_migrations(args.db_path))
    except KeyboardInterrupt:
        print("\n✗ Migration interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
