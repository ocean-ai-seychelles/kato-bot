# Pitfall 003: Test Pollution and Monkeypatching

**Date**: 2025-01
**Severity**: Medium (broke 4 unit tests)
**Status**: Resolved
**Component**: Test infrastructure

## Problem

After implementing database isolation fixture to fix locking issues, 4 unit tests started failing:

```
FAILED tests/unit/test_database.py::TestDatabaseConnection::test_connect_creates_connection
FAILED tests/unit/test_database.py::TestDatabaseConnection::test_repr_shows_status
FAILED tests/unit/test_database.py::TestDatabaseInitialization::test_db_path_created_if_missing
FAILED tests/unit/test_database.py::TestDatabaseInitialization::test_default_db_path
```

**Error examples**:
```python
# Expected
assert db.db_path == Path("data/kato.db")

# Got
assert db.db_path == Path("/var/folders/m3/.../tmp_xyz/test_kato.db")
```

## Root Cause

### The Over-Eager Fixture

**First implementation** of database isolation:

```python
@pytest.fixture(autouse=True)  # ← Applied to ALL tests
async def isolated_database(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kato.db"

        # Monkey-patch Database.__init__ to ALWAYS use temp path
        def patched_init(self, db_path_param=None):
            original_init(self, str(db_path))  # ← Ignores db_path_param!

        monkeypatch.setattr(Database, "__init__", patched_init)
        yield db_path
```

**Problem**: This patched `Database.__init__` for EVERY test, including unit tests.

### Why Unit Tests Failed

**Unit tests were testing path behavior**:

```python
def test_default_db_path(self):
    """Test that Database uses default path when none specified."""
    db = Database()  # Should use "data/kato.db"
    assert db.db_path == Path("data/kato.db")
```

**With fixture active**:
1. Test calls `Database()`
2. Fixture's patched `__init__` runs
3. **Always** uses temp path, ignoring default
4. Test fails because path is temp dir, not "data/kato.db"

**Another example**:
```python
def test_connect_creates_connection(self, tmp_path):
    """Test that connecting creates database file at specified path."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)  # ← Passed explicit path
    await db.connect()
    assert db_path.exists()  # ← But fixture used DIFFERENT temp path!
```

### The Pollution Chain

```
1. Fixture runs (autouse=True)
   ↓
2. Monkeypatch Database.__init__ globally
   ↓
3. ALL tests now use temp database
   ↓
4. Unit tests that verify path behavior fail
   ↓
5. Integration tests work (wanted temp paths)
```

**Collateral damage**: Trying to fix integration tests broke unit tests.

## Why This Happened

### Misunderstanding autouse

```python
@pytest.fixture(autouse=True)
```

This means: **Run for EVERY test in scope, without explicit request.**

**Thought it meant**: "Make this fixture available automatically"
**Actually means**: "Apply this fixture to every test"

### Not Considering Test Variety

**Integration tests** need:
- Isolated databases
- Don't care about specific paths
- Want automatic cleanup

**Unit tests** need:
- Real path behavior
- To verify default paths
- To test path creation logic

**Single fixture can't satisfy both.**

## Failed Fix Attempts

### Attempt 1: Make Fixture Optional

```python
@pytest.fixture  # Remove autouse
async def isolated_database(monkeypatch):
    # ...
```

**Problem**: Now integration tests need to explicitly request it:
```python
async def test_reaction_roles(isolated_database):  # ← Boilerplate
    # ...
```

Would need to modify all 10+ integration tests.

### Attempt 2: Separate Fixtures

Create `isolated_database` for integration, `real_database` for unit tests.

**Problem**: Still need tests to request them explicitly.

## Solution

### Selective Auto-Application

**Modified fixture to detect test type**:

```python
@pytest.fixture(scope="function")
async def isolated_database(monkeypatch, request):
    """Only patch integration tests, not unit tests."""

    # Check test file path
    test_path = str(request.fspath)
    if "integration" not in test_path:
        yield None  # ← Don't patch, just return
        return

    # Only reached for integration tests
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kato.db"

        def patched_init(self, db_path_param=None):
            original_init(self, str(db_path))

        monkeypatch.setattr(Database, "__init__", patched_init)
        yield db_path

@pytest.fixture(autouse=True)
async def auto_isolated_database(isolated_database):
    """Auto-apply, but inner fixture decides whether to actually patch."""
    yield
```

**How it works**:

1. `auto_isolated_database` runs for ALL tests (autouse=True)
2. It calls `isolated_database`
3. `isolated_database` checks test path:
   - If `"integration"` in path → patch Database
   - If not → do nothing
4. Unit tests get normal Database behavior
5. Integration tests get isolated databases

## Why This Works

### Convention Over Configuration

Uses directory structure to determine test type:
- `tests/unit/` → Unit tests, don't patch
- `tests/integration/` → Integration tests, do patch

**Benefits**:
- No markers needed (`@pytest.mark.integration`)
- No explicit fixture requests needed
- Self-documenting (test location indicates type)

### Transparent to Tests

Neither unit nor integration tests need to change:

```python
# Integration test - gets patched automatically
async def test_reaction_roles():  # ← No fixture parameter
    bot = KatoBot(config)  # Gets temp database

# Unit test - not patched
def test_default_path():  # ← No fixture parameter
    db = Database()  # Gets real default path
```

### Monkeypatch is Scoped

`monkeypatch` fixture is function-scoped:
- Patch applies only to current test
- Reverts after test completes
- No leakage between tests

## Lessons Learned

### autouse is Powerful and Dangerous

```python
@pytest.fixture(autouse=True)
```

**When to use**: Fixtures that should ALWAYS run (logging setup, etc.)
**When NOT to use**: Fixtures that modify global state selectively

**This case**: Needed autouse for convenience, but with logic to be selective.

### Monkeypatching Needs Boundaries

When monkeypatching:
1. **Know the scope**: Function? Module? Session?
2. **Consider side effects**: What else uses this?
3. **Test the tests**: Verify fixture works for all test types

### Test Types Need Different Infrastructure

**Unit tests**: Test individual components in isolation
**Integration tests**: Test components together with real infrastructure

**Can't treat them the same.**

### Directory Structure as API

Using directory structure to determine behavior:
```
tests/
├── unit/          # Real paths, no patching
└── integration/   # Temp paths, isolated databases
```

**Benefits**:
- Self-documenting
- Convention-based
- Easy to understand

**Drawbacks**:
- Have to remember convention
- Renaming directories breaks it

**For this project**: Benefits outweigh drawbacks.

## Prevention

### For Future Fixtures

Checklist when creating autouse fixtures:

1. ✅ **Does this need to run for ALL tests?**
   - If yes: Make sure it's truly universal
   - If no: Consider selective application

2. ✅ **Does this modify global state?**
   - If yes: Ensure proper scoping and cleanup
   - If no: Safe to apply broadly

3. ✅ **Are there different test types?**
   - If yes: Add logic to handle each type
   - If no: Simple autouse is fine

4. ✅ **Can this break existing tests?**
   - Always run full test suite after adding
   - Check both unit and integration tests

### Testing Fixtures

**Good practice**: Test the fixture itself

```python
def test_isolated_database_patches_integration_tests():
    """Verify fixture patches integration tests."""
    # Mock request from integration test
    # Verify Database.__init__ is patched

def test_isolated_database_ignores_unit_tests():
    """Verify fixture doesn't patch unit tests."""
    # Mock request from unit test
    # Verify Database.__init__ is NOT patched
```

We didn't do this (yet), but learned we should.

## Impact

**Before fix**:
- ✅ Integration tests passing (10 tests)
- ❌ Unit tests failing (4 tests)
- ❌ Total: 45/49 passing

**After fix**:
- ✅ Integration tests passing (10 tests)
- ✅ Unit tests passing (49 tests)
- ✅ Total: 49/49 passing

## Related Documents

- [Pitfall 001: Database Locking in Tests](001-database-locking.md)
- [Decision 003: Test Isolation with Fixtures](../decisions/003-test-isolation-fixture.md)

## Code Location

- Fixture implementation: [tests/conftest.py](../../tests/conftest.py)

## Pytest Documentation

- [Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Monkeypatch](https://docs.pytest.org/en/stable/monkeypatch.html)
- [autouse fixtures](https://docs.pytest.org/en/stable/fixture.html#autouse-fixtures-fixtures-you-don-t-have-to-request)
