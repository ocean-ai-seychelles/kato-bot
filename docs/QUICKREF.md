# Quick Reference: Key Learnings

This document provides a quick lookup of important patterns, decisions, and pitfalls to reference during development.

## 🎯 Quick Decision Lookup

### Need to choose a tool or approach?

| Scenario | Choice | Why | Doc |
|----------|--------|-----|-----|
| Deployment | Docker Compose | 24/7 uptime, portability, auto-restart | [ADR-001](decisions/001-why-docker.md) |
| Linting | Ruff | 40x faster, single tool | [ADR-002](decisions/002-why-ruff.md) |
| Database | SQLite | Simple, file-based, good for single instance | [ARCH-001](architecture/001-database-design.md) |
| Test isolation | Temp DB per test | Prevents locking, no pollution | [ADR-003](decisions/003-test-isolation-fixture.md) |

## ⚠️ Common Pitfalls to Avoid

### Database

```python
# ❌ DON'T: Insert child before parent
await db.execute("INSERT INTO reaction_roles (guild_id, ...) VALUES (?)")
# Foreign key fails!

# ✅ DO: Insert parent first
await db.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
await db.execute("INSERT INTO reaction_roles (guild_id, ...) VALUES (?)")
```
**See**: [Pitfall 002: Foreign Key Constraints](pitfalls/002-foreign-key-constraints.md)

### Testing

```python
# ❌ DON'T: Share database between tests
# All tests use data/kato.db → locking errors

# ✅ DO: Use isolated_database fixture
# Each integration test gets unique temp database automatically
```
**See**: [Pitfall 001: Database Locking](pitfalls/001-database-locking.md)

### Pytest Fixtures

```python
# ❌ DON'T: Use autouse if it modifies global state
@pytest.fixture(autouse=True)
def patch_everything(monkeypatch):
    # This breaks unit tests!

# ✅ DO: Be selective with patches
@pytest.fixture(autouse=True)
def selective_patch(monkeypatch, request):
    if "integration" not in str(request.fspath):
        yield
        return
    # Only patch integration tests
```
**See**: [Pitfall 003: Test Pollution](pitfalls/003-test-pollution.md)

## 🏗️ Architecture Patterns

### Cog Structure

```python
from discord.ext import commands

class FeatureCog(commands.Cog):
    def __init__(self, bot: KatoBot) -> None:
        self.bot = bot
        self.config = bot.config

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Sync config to database on startup
        await self._sync_from_config()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Use raw events for persistence

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def admin_command(self, ctx):
        # Admin-only command

async def setup(bot: KatoBot) -> None:
    await bot.add_cog(FeatureCog(bot))
```
**See**: [ARCH-002: Cog Architecture](architecture/002-cog-architecture.md)

### Database Access

```python
# Query single row
row = await self.bot.db.fetch_one(
    "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?",
    (message_id, emoji),
)
role_id = row["role_id"] if row else None

# Query multiple rows
rows = await self.bot.db.fetch_all(
    "SELECT * FROM reaction_roles WHERE guild_id = ?",
    (guild_id,),
)

# Execute without result
await self.bot.db.execute(
    "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
    (guild_id, message_id, emoji, role_id),
)
```
**See**: [ARCH-001: Database Design](architecture/001-database-design.md)

## 🧪 Testing Patterns

### Integration Test Template

```python
import pytest
from bot.core.bot import KatoBot
from bot.core.config import Config

class TestFeature:
    @pytest.mark.asyncio
    async def test_feature(self) -> None:
        """Test description."""
        # Setup
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        await bot.db.connect()
        await bot.db.apply_migrations()

        # No need to insert guild_config manually
        # Cog's sync method handles it with INSERT OR IGNORE

        # Test
        result = await cog.some_method()

        # Assert
        assert result == expected

        # Cleanup
        await bot.db.close()
```

**Note**: Database isolation happens automatically via fixture.

### Unit Test Template

```python
import pytest
from bot.core.database import Database

class TestDatabase:
    @pytest.mark.asyncio
    async def test_database_behavior(self, tmp_path) -> None:
        """Test description."""
        # Use tmp_path for custom paths
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Test
        await db.connect()
        assert db_path.exists()

        # Cleanup
        await db.close()
```

**Note**: Unit tests use real paths, not temp databases.

## 📋 Pre-Launch Checklist

Before deploying new features:

- [ ] All tests pass locally (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Code formatted (`make format`)
- [ ] Pre-commit hooks installed (`make pre-commit-install`)
- [ ] CI pipeline passes on GitHub
- [ ] Coverage >= 35% (check CI output)
- [ ] Tested with real Discord server
- [ ] Database migration created if schema changed
- [ ] Documentation updated

## 🚀 Deployment Commands

```bash
# Local testing
make run

# Deploy to VPS (first time)
git clone https://github.com/your-org/kato-bot.git
cd kato-bot
echo "DISCORD_TOKEN=your_token" > assets/.env
docker-compose up -d --build

# Update deployed bot
git pull
docker-compose up -d --build

# View logs
docker-compose logs -f

# Restart bot
docker-compose restart
```

## 📊 Current Project State

**Completed Features**:
- ✅ Phase 1: Core infrastructure (config, database, bot class)
- ✅ Phase 2: Welcome system with template support
- ✅ Phase 3: Reaction role system
- ✅ Docker deployment infrastructure
- ✅ CI/CD pipeline with Ruff and pytest
- ✅ Phase 4: Auto-moderation (spam, caps, mentions, banned words)
- ✅ Phase 5: Manual moderation (kick, ban, timeout, warnings)
- ✅ Phase 6: Audit logging (message edits/deletes, member joins/leaves)
- ✅ Phase 7: Admin commands (status, reload, syncconfig, cogs)

**Test Coverage**: 38.35% (204 tests passing)

**All Features Complete!**

## 🔗 Quick Links

- [Main README](../README.md)
- [Architecture Decisions](./README.md#architecture)
- [Deployment Guide](../DEPLOYMENT.md)
- [All Pitfalls](./README.md#pitfalls)

## 💡 Bayesian Priors

When making new decisions, consult:

1. **Similar past decisions**: What did we choose before and why?
2. **Related pitfalls**: What mistakes did we make in similar situations?
3. **Architecture patterns**: What patterns have worked well?
4. **Test patterns**: How did we solve similar testing challenges?

**Update this document** when new patterns emerge or beliefs change based on experience.
