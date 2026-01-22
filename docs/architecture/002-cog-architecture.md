# Discord.py Cogs Architecture

**Date**: 2025-01 (Phase 1-3)
**Status**: Active
**Context**: Need a modular way to organize bot features (welcome, reaction roles, moderation, etc.)

## Problem

As the bot grows, we need:
- **Modularity**: Features organized into logical units
- **Separation of concerns**: Welcome logic separate from moderation
- **Hot-reloading**: Ability to reload features without restarting bot (future)
- **Testability**: Easy to test individual features in isolation
- **Discoverability**: Clear structure for finding feature code

## Design Decision: Discord.py Cogs

**Pattern**: Each feature is a separate Cog class loaded by the bot

```
bot/cogs/
├── __init__.py
├── welcome.py           # Welcome system cog
├── reaction_roles.py    # Reaction role system cog
└── moderation.py        # Future: moderation commands
```

### Cog Structure

```python
from discord.ext import commands

class WelcomeCog(commands.Cog):
    def __init__(self, bot: KatoBot) -> None:
        self.bot = bot
        self.config = bot.config

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        # Event handler

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx: commands.Context, channel: discord.TextChannel):
        # Admin command

async def setup(bot: KatoBot) -> None:
    await bot.add_cog(WelcomeCog(bot))
```

### Loading Cogs

In `bot/core/bot.py`:

```python
async def setup_hook(self) -> None:
    await self.db.connect()
    await self.db.apply_migrations()

    # Load cogs
    await self.load_extension("bot.cogs.welcome")
    await self.load_extension("bot.cogs.reaction_roles")
```

## Key Patterns

### 1. Raw Events for Persistence

**Decision**: Use `on_raw_*` events for reactions, not `on_reaction_add`

```python
@commands.Cog.listener()
async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
    # Works even if message not in cache
    # Persists across bot restarts
```

**Rationale**:
- `on_reaction_add` only fires for cached messages (recent messages)
- `on_raw_reaction_add` works for any message, even old ones
- Reaction role messages are typically pinned/old
- More reliable for production use

**Trade-off**: Raw events require fetching objects manually (channel, member, etc.)

### 2. Database Access Pattern

Cogs access the database through `self.bot.db`:

```python
async def _get_reaction_role_mapping(self, message_id: int, emoji: str) -> int | None:
    row = await self.bot.db.fetch_one(
        "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?",
        (message_id, emoji),
    )
    return row["role_id"] if row else None
```

**Benefits**:
- Single database connection shared across cogs
- No need to manage connections in each cog
- Testable (can mock `bot.db`)

### 3. Config Sync Pattern

**Pattern**: Sync config to database on bot startup

```python
@commands.Cog.listener()
async def on_ready(self) -> None:
    guild_id = self.bot.config.get("server", "guild_id")
    await self._sync_reaction_roles_from_config(guild_id)
```

**Why**:
- Config (`assets/config.toml`) is the source of truth
- Database stores runtime state
- On startup, database is updated to match config
- Prevents config/database drift

### 4. Admin Commands Pattern

**Pattern**: All admin commands require `administrator` permission

```python
@commands.command()
@commands.has_permissions(administrator=True)
async def add_reaction_role(
    self,
    ctx: commands.Context,
    message_id: int,
    emoji: str,
    role: discord.Role
):
    # Admin-only command
```

**Security**: Ensures only server admins can modify bot behavior

## File Organization

```
bot/
├── cogs/
│   ├── __init__.py
│   ├── welcome.py          # Member join/leave events, welcome messages
│   └── reaction_roles.py   # Reaction role assignment system
├── core/
│   ├── bot.py              # Main KatoBot class, loads cogs
│   ├── config.py           # Config loader
│   └── database.py         # Database abstraction
└── utils/
    └── embeds.py           # Shared embed utilities
```

## Cog Lifecycle

1. **Bot startup**: `KatoBot.setup_hook()` runs
2. **Cog loading**: `await bot.load_extension("bot.cogs.welcome")`
3. **Cog initialization**: `WelcomeCog.__init__()` called
4. **Event registration**: Discord.py registers `@commands.Cog.listener()` methods
5. **Ready event**: `on_ready()` called, cog syncs config to database
6. **Runtime**: Cog responds to events and commands
7. **Shutdown**: `bot.close()` cleans up

## Testing Cogs

### Unit Tests
Test individual methods in isolation:

```python
async def test_get_reaction_role_mapping_returns_role_id():
    bot = KatoBot(config)
    cog = ReactionRolesCog(bot)
    await bot.db.connect()
    # ... test cog methods
```

### Integration Tests
Test cog with actual database:

```python
async def test_reaction_roles_synced_on_ready():
    bot = KatoBot(config)
    cog = ReactionRolesCog(bot)
    await bot.db.connect()
    await bot.db.apply_migrations()
    await cog.on_ready()
    # Verify database state
```

See [Decision 003: Test Isolation](../decisions/003-test-isolation-fixture.md)

## Consequences

### Positive
- ✅ Clear separation of concerns
- ✅ Easy to find feature code
- ✅ Testable in isolation
- ✅ Can disable features by not loading cogs
- ✅ Discord.py standard pattern (good documentation)

### Negative
- ⚠️ Cogs share global bot state (can cause coupling)
- ⚠️ Hot-reloading requires careful implementation
- ⚠️ Each cog needs boilerplate (setup function, init)

### Trade-offs Accepted
- Chose modularity over simplicity (cogs vs single file)
- Chose Discord.py conventions over custom architecture
- Chose raw events over cached events (reliability vs convenience)

## Related Documents

- [Decision 003: Test Isolation with Fixtures](../decisions/003-test-isolation-fixture.md)
- [Pitfall 002: Foreign Key Constraint Failures](../pitfalls/002-foreign-key-constraints.md)

## Future Enhancements

- Hot-reload commands for development (`!reload moderation`)
- Cog dependencies (if moderation needs audit logging cog)
- Shared utilities between cogs (moved to `bot/utils/`)
