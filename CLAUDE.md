# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kato is a Discord moderation bot for OCEAN AI community. Built with discord.py 2.6+ and async SQLite. Named after "Kato Nwar" (Seychelles Black Parrot) - a wise guardian helping members follow the community code of conduct.

## Common Commands

```bash
# Development
make install              # Install dependencies (uses uv)
make run                  # Run bot locally
make test                 # Run tests with coverage
make lint                 # Ruff check
make format               # Ruff format

# Docker deployment
make docker-up            # Start bot
make docker-down          # Stop bot
make docker-logs          # View logs

# Pre-commit hooks (run automatically on commit)
make pre-commit-install   # One-time setup
```

Run a single test:
```bash
uv run pytest tests/integration/test_welcome.py -v
```

## Architecture

```
bot/
├── core/
│   ├── bot.py           # KatoBot class - entry point, cog loader
│   ├── config.py        # TOML config loader (assets/config.toml)
│   └── database.py      # Async SQLite wrapper with migration support
├── cogs/                # Feature modules (discord.py Cogs)
│   ├── welcome.py       # Member welcome messages
│   └── reaction_roles.py # Emoji-to-role assignment
└── utils/
    └── embeds.py        # Reusable embed templates
```

**Database**: SQLite via aiosqlite, raw SQL (no ORM). Schema in `migrations/001_initial_schema.sql`.

**Config**: TOML file at `assets/config.toml` is source of truth, synced to DB on startup.

## Key Patterns

### Cog Structure
```python
class FeatureCog(commands.Cog):
    def __init__(self, bot: KatoBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await self._sync_from_config()  # Sync config to DB on startup

    @commands.command()
    @commands.has_permissions(administrator=True)  # Required for admin commands
    async def command(self, ctx):
        ...
```

### Database Access
```python
# Always insert guild_config first (foreign key constraint)
await self.bot.db.execute(
    "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
    (guild_id,)
)
# Then insert child records
await self.bot.db.execute(
    "INSERT INTO reaction_roles (...) VALUES (...)",
    (...)
)
```

### Events
Use `on_raw_*` events for reliability (works across bot restarts):
- `on_raw_reaction_add` / `on_raw_reaction_remove`
- These work even when the message isn't cached

## Testing

- **Unit tests**: `tests/unit/` - no database needed
- **Integration tests**: `tests/integration/` - use `isolated_database` fixture automatically
- Coverage minimum: 38% (enforced in CI)

The `isolated_database` fixture creates a fresh temp database per test to prevent locking and pollution.

## Documentation

- `docs/QUICKREF.md` - Copy-paste patterns for common tasks
- `docs/architecture/` - Design decisions (cog architecture, database design)
- `docs/pitfalls/` - Known issues and solutions
- `DEPLOYMENT.md` - Docker, systemd, and cloud deployment options

## Environment Setup

Required files:
- `assets/.env` with `DISCORD_TOKEN=...`
- `assets/config.toml` with guild_id, channel_ids, role_ids
