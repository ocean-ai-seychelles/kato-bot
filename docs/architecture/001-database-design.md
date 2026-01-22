# Database Design and Migration System

**Date**: 2025-01 (Phase 1)
**Status**: Active
**Context**: Needed a persistent data layer for guild configs, welcome messages, reaction roles, and future moderation features.

## Problem

The bot needs to:
- Store per-guild configuration
- Track welcome messages and reaction role mappings
- Support future features (warnings, audit logs, auto-mod rules)
- Handle schema evolution gracefully
- Work reliably in async context (discord.py is async)

## Design Decisions

### SQLite with aiosqlite

**Chosen**: SQLite via aiosqlite wrapper

**Rationale**:
- **Simplicity**: File-based, no separate database server needed
- **Async support**: aiosqlite provides async/await interface
- **Portability**: Database is a single file, easy to backup
- **Good enough**: Single bot instance, not high concurrency needs
- **Zero config**: No installation or setup required

**Trade-offs**:
- ❌ Not suitable for multiple bot instances (no concurrent writes)
- ❌ Limited to ~100k writes/sec (more than we need)
- ✅ Perfect for single-guild or small-scale multi-guild bots
- ✅ Easy to migrate to PostgreSQL later if needed

### Migration System

**Pattern**: SQL files in `bot/migrations/` executed in order

```
bot/migrations/
├── 001_initial_schema.sql
├── 002_add_reaction_roles.sql
└── 003_add_audit_logging.sql (future)
```

**Features**:
- Migrations tracked in `schema_migrations` table
- Applied exactly once (INSERT OR IGNORE pattern)
- Sorted by filename for execution order
- Pure SQL for transparency

**Why not an ORM**:
- Transparency: SQL is explicit, no magic
- Simplicity: No need to learn SQLAlchemy/Tortoise
- Control: Full control over schema and queries
- Async: Some ORMs have poor async support

### Foreign Keys and Cascades

**Design**: Strict referential integrity with CASCADE deletes

```sql
CREATE TABLE reaction_roles (
    guild_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(message_id, emoji)
);
```

**Rationale**:
- When a guild config is deleted, all related data auto-deletes
- Prevents orphaned records
- Database enforces consistency, not application code

**Pitfall discovered**: See [pitfalls/002-foreign-key-constraints.md](../pitfalls/002-foreign-key-constraints.md)

### Row Factory Pattern

**Pattern**: Use `aiosqlite.Row` for dictionary-like access

```python
self.connection.row_factory = aiosqlite.Row
cursor = await self.connection.execute(query)
row = await cursor.fetchone()
role_id = row["role_id"]  # ← Dictionary access, not tuple[0]
```

**Benefits**:
- Self-documenting code
- Refactor-safe (column order doesn't matter)
- Type hints work better

## File Structure

```
bot/core/database.py       # Database class with connect/execute/migrations
bot/migrations/            # SQL migration files
data/kato.db              # SQLite database file (gitignored)
```

## Key Implementation Details

### Database Class API

```python
class Database:
    async def connect(self) -> None
    async def close(self) -> None
    async def execute(self, query: str, parameters: tuple) -> Cursor
    async def fetch_one(self, query: str, parameters: tuple) -> Row | None
    async def fetch_all(self, query: str, parameters: tuple) -> list[Row]
    async def apply_migrations(self) -> None
```

### Initialization Flow

1. Bot calls `await bot.db.connect()`
2. Database opens connection and enables foreign keys
3. `apply_migrations()` runs any pending migrations
4. Database is ready for queries

### Connection Management

- Connection opened in `KatoBot.setup_hook()` (runs before bot starts)
- Connection closed in `KatoBot.close()` (runs on shutdown)
- Single connection shared across all cogs (SQLite doesn't need pooling)

## Consequences

### Positive
- ✅ Simple, understandable data layer
- ✅ Schema versioning built-in
- ✅ Foreign key constraints prevent data corruption
- ✅ Easy to backup (copy one file)
- ✅ No external dependencies

### Negative
- ⚠️ Cannot scale to multiple bot instances without PostgreSQL migration
- ⚠️ Write-heavy workloads might need optimization
- ⚠️ No built-in query builder (manual SQL strings)

### Trade-offs Accepted
- Chose simplicity over flexibility (SQLite vs PostgreSQL)
- Chose transparency over convenience (raw SQL vs ORM)
- Chose file-based over client-server (easier ops, less scalability)

## Related Documents

- [Pitfall 002: Foreign Key Constraint Failures](../pitfalls/002-foreign-key-constraints.md)
- [Pitfall 001: Database Locking in Tests](../pitfalls/001-database-locking.md)

## Future Considerations

If the bot needs to scale:
- Migrate to PostgreSQL (similar API via asyncpg)
- Database class interface stays the same
- Change connection string and some SQL syntax
- Migrations can be rewritten or kept as-is
