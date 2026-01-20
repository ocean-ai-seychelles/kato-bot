# Pitfall 002: Foreign Key Constraint Failures

**Date**: 2025-01 (Phase 3)
**Severity**: Medium (broke tests and bot startup)
**Status**: Resolved
**Component**: Database schema, reaction roles

## Problem

Bot crashed on startup and tests failed with:

```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**Context**: Just implemented reaction role system with this schema:

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

## Root Cause

### The Chicken-and-Egg Problem

**Reaction roles table** has foreign key to `guild_config`:
```sql
FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
```

**Bot startup flow**:
1. Bot starts up
2. `on_ready()` event fires
3. Reaction roles cog tries to sync config to database
4. **INSERT INTO reaction_roles** with `guild_id = 123456`
5. ❌ **No row in guild_config with guild_id = 123456**
6. Foreign key constraint fails

**Tests had same issue**:
```python
async def test_sync_reaction_roles():
    await bot.db.connect()
    await bot.db.apply_migrations()

    # This fails! No guild_config row exists yet
    await bot.db.execute(
        "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
        (123456, 789012, "✅", 345678),
    )
```

### Why This Happened

**Design assumption**: Assumed `guild_config` rows would exist before reaction roles sync.

**Reality**: Nothing created `guild_config` rows automatically. They only got created if:
- Admin ran `!set_welcome` or similar commands
- Manual database initialization

**For fresh database**: No `guild_config` rows exist, so reaction role sync fails.

## Failed Approaches

### Attempt 1: Disable Foreign Keys

```python
await db.execute("PRAGMA foreign_keys = OFF")
```

**Why rejected**:
- Loses referential integrity
- Can create orphaned records
- Hides bugs instead of fixing them

### Attempt 2: Make Foreign Key Optional

```sql
-- Remove FOREIGN KEY constraint entirely
CREATE TABLE reaction_roles (
    guild_id INTEGER NOT NULL,
    -- No foreign key
);
```

**Why rejected**:
- Loses CASCADE delete behavior
- Can't clean up reaction roles when guild leaves
- Bad database design

## Solution

### Insert Guild Config First

**In sync function**:
```python
async def _sync_reaction_roles_from_config(self, guild_id: int) -> None:
    # 1. Ensure guild_config exists (satisfies foreign key)
    await self.bot.db.execute(
        "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
        (guild_id,),
    )

    # 2. Now safe to insert reaction_roles
    await self.bot.db.execute(
        "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
        (guild_id, message_id, emoji, role_id),
    )
```

**Key pattern**: `INSERT OR IGNORE`

- If row exists: Do nothing (no error)
- If row doesn't exist: Create it
- Idempotent operation (safe to run multiple times)

**In tests**:
```python
async def test_reaction_roles():
    await bot.db.connect()
    await bot.db.apply_migrations()

    # Insert guild_config first
    await bot.db.execute(
        "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
        (123456,),
    )

    # Now can insert reaction_roles
    await bot.db.execute(
        "INSERT INTO reaction_roles (...) VALUES (...)",
        (123456, ...),
    )
```

## Why This Works

### Maintains Referential Integrity

- Foreign key constraint still enforced
- Can't create orphaned reaction_roles
- CASCADE delete still works

### Idempotent

- Safe to run multiple times
- Won't create duplicate guild_config rows
- Doesn't error if row already exists

### Minimal Change

- No schema changes needed
- Just add one INSERT before dependent inserts
- Simple pattern to remember

## Lessons Learned

### Foreign Keys Require Dependency Order

When inserting data with foreign keys:
1. Insert parent table first (`guild_config`)
2. Then insert child table (`reaction_roles`)

**Can't assume parent rows exist.**

### INSERT OR IGNORE is Your Friend

For "ensure row exists" patterns:
```sql
INSERT OR IGNORE INTO parent_table (id) VALUES (?)
```

Better than:
```sql
-- Check if exists
SELECT * FROM parent_table WHERE id = ?
-- If not exists, insert
INSERT INTO parent_table (id) VALUES (?)
```

**Benefits**:
- One query instead of two
- Atomic (no race conditions)
- More efficient

### Test Your Schema Migrations

**Before this pitfall**:
- Migrations worked
- Tests worked with manual setup
- Assumed it would work on bot startup

**After this pitfall**:
- Test the FULL startup flow
- Test with fresh database (no pre-existing data)
- Don't assume parent records exist

### Document Dependency Order

In database documentation, note which tables depend on others:
```
guild_config (parent)
  ↓
  ├── reaction_roles (child)
  └── welcome_messages (child)
```

**When inserting**: Follow dependency order (parent → child)
**When deleting**: Reverse order or use CASCADE

## Prevention

### For Future Tables

When creating tables with foreign keys:

1. **Ask**: "What if the parent row doesn't exist?"
2. **Solution**: Add `INSERT OR IGNORE` before dependent inserts
3. **Test**: Try with completely fresh database
4. **Document**: Note the dependency in code comments

### Code Pattern

```python
async def sync_feature_to_database(self, guild_id: int):
    """Sync feature from config to database.

    IMPORTANT: Ensures guild_config exists before inserting dependent data.
    """
    # Step 1: Ensure parent row exists
    await self.bot.db.execute(
        "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
        (guild_id,),
    )

    # Step 2: Insert dependent data
    await self.bot.db.execute(
        "INSERT INTO dependent_table (...) VALUES (...)",
        (guild_id, ...),
    )
```

## Impact

**Before fix**:
- ❌ Bot crashed on startup
- ❌ 4 tests failing
- ❌ Reaction roles wouldn't sync

**After fix**:
- ✅ Bot starts successfully
- ✅ All tests passing
- ✅ Reaction roles sync correctly
- ✅ Foreign key integrity maintained

## Related Documents

- [Architecture 001: Database Design](../architecture/001-database-design.md)
- [Decision 003: Test Isolation with Fixtures](../decisions/003-test-isolation-fixture.md)

## Code Locations

- Fix in [bot/cogs/reaction_roles.py:93](../../bot/cogs/reaction_roles.py#L93)
- Tests in [tests/integration/test_reaction_roles.py](../../tests/integration/test_reaction_roles.py)

## SQLite Foreign Key Documentation

- [SQLite Foreign Key Support](https://www.sqlite.org/foreignkeys.html)
- [INSERT OR syntax](https://www.sqlite.org/lang_conflict.html)
