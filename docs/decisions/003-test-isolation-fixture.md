# ADR 003: Test Isolation with Pytest Fixtures

**Date**: 2025-01
**Status**: Accepted
**Deciders**: Development team
**Context**: Database locking errors in CI pipeline

## Decision

Use pytest fixtures with monkeypatching to provide each integration test with an isolated temporary database.

## Context and Problem Statement

When running tests in CI, we encountered failures:
- `sqlite3.OperationalError: database is locked`
- `sqlite3.IntegrityError: UNIQUE constraint failed`

**Root cause**: All tests were sharing the same `data/dory.db` file, causing:
- Race conditions when tests ran in parallel
- Data pollution between tests
- Incomplete cleanup leaving stale data

## Decision Drivers

- **Reliability**: Tests must pass consistently in CI
- **Isolation**: Each test should have clean state
- **Speed**: Don't slow down test suite significantly
- **Simplicity**: Minimal changes to existing tests
- **Selectivity**: Only apply to integration tests, not unit tests

## Options Considered

### Option 1: Manual Database Cleanup

Add `rm -f data/dory.db` before tests in Makefile and CI.

**Pros**:
- Simple to implement
- No code changes

**Cons**:
- Only cleans once at start (tests still conflict)
- Doesn't work for parallel tests
- Fragile (easy to forget)
- Still had locking issues in practice

**Verdict**: Rejected - didn't solve the problem

### Option 2: Unique Database per Test (Manual)

Each test creates its own database file.

**Pros**:
- True isolation
- No shared state

**Cons**:
- Boilerplate in every test
- Manual cleanup required
- Easy to forget or mess up

**Verdict**: Rejected - too much manual work

### Option 3: Pytest Fixture with Temporary Files (CHOSEN)

Create a pytest fixture that:
- Creates a temporary directory for each test
- Monkeypatches `Database.__init__` to use temp path
- Auto-cleans up after test

**Pros**:
- Automatic isolation
- No test code changes needed
- Temporary directories auto-cleanup
- Can be selective (only integration tests)

**Cons**:
- More complex setup
- Uses monkeypatching (can be tricky)

**Verdict**: Best balance of automation and correctness

## Decision Outcome

**Chosen option**: Pytest fixture with monkeypatching

### Implementation

```python
# tests/conftest.py

@pytest.fixture(scope="function")
async def isolated_database(monkeypatch, request):
    """Create a unique temporary database for each integration test."""

    # Only apply to integration tests
    test_path = str(request.fspath)
    if "integration" not in test_path:
        yield None
        return

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_dory.db"

        # Monkeypatch Database.__init__ to use temp path
        from bot.core.database import Database
        original_init = Database.__init__

        def patched_init(self, db_path_param=None):
            original_init(self, str(db_path))

        monkeypatch.setattr(Database, "__init__", patched_init)

        yield db_path
        # Auto-cleanup when context exits

@pytest.fixture(autouse=True)
async def auto_isolated_database(isolated_database):
    """Automatically apply database isolation to integration tests."""
    yield
```

### Key Design Choices

**1. Selective Application**

Check if test is in `integration/` directory:
```python
if "integration" not in test_path:
    yield None
    return
```

**Why**: Unit tests need to test actual database path behavior, shouldn't be patched.

**2. Monkeypatching**

Patch `Database.__init__` instead of passing path explicitly:
```python
monkeypatch.setattr(Database, "__init__", patched_init)
```

**Why**: Existing tests do `bot = DoryBot(config)`, which creates `Database()` internally. No test changes needed.

**3. Temporary Directories**

Use `tempfile.TemporaryDirectory()`:
```python
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "test_dory.db"
```

**Why**: Auto-cleanup when context exits, no leftover files.

**4. Auto-use Wrapper**

Create wrapper fixture with `autouse=True`:
```python
@pytest.fixture(autouse=True)
async def auto_isolated_database(isolated_database):
    yield
```

**Why**: Applies to all tests automatically, but the inner fixture decides whether to actually patch.

## Consequences

### Positive

- ✅ **Reliability**: All 49 tests pass consistently
- ✅ **No locking errors**: Each test has its own database
- ✅ **No pollution**: Tests can't affect each other
- ✅ **Auto-cleanup**: No leftover test databases
- ✅ **Transparent**: Tests don't need to know about fixture
- ✅ **Fast**: Temporary files are fast

### Negative

- ⚠️ **Complexity**: Monkeypatching can be hard to debug
- ⚠️ **Hidden behavior**: Tests don't explicitly request isolation
- ⚠️ **Path-based detection**: Relies on directory naming convention

### Neutral

- 📝 **Unit tests unaffected**: They still test real path behavior
- 📝 **Integration tests isolated**: Each gets clean database

## Bug Encountered and Fixed

### First Attempt: Auto-use for All Tests

Initially used `autouse=True` on the main fixture, applying to ALL tests:

```python
@pytest.fixture(autouse=True)  # ❌ Applied to everything
async def isolated_database(monkeypatch):
    # Always patches Database.__init__
```

**Problem**: This broke 4 unit tests that specifically tested database path behavior:
- `test_connect_creates_connection` - Expected db at specific path
- `test_repr_shows_status` - Checked path in repr string
- `test_db_path_created_if_missing` - Tested directory creation
- `test_default_db_path` - Verified default is `data/dory.db`

These tests failed because they were getting temp paths instead of their custom paths.

### Fix: Selective Application

Added check to only patch integration tests:

```python
test_path = str(request.fspath)
if "integration" not in test_path:
    yield None  # Don't patch unit tests
    return
```

**Result**: All 49 tests pass, both unit and integration.

## Validation

Success criteria:
- ✅ No database locking errors in CI
- ✅ No UNIQUE constraint failures
- ✅ All 49 tests pass locally
- ✅ All 49 tests pass in CI
- ✅ Unit tests can verify path behavior
- ✅ Integration tests get clean databases

All criteria met.

## Related Documents

- [Pitfall 001: Database Locking in Tests](../pitfalls/001-database-locking.md)
- [Pitfall 003: Test Pollution and Monkeypatching](../pitfalls/003-test-pollution.md)

## Notes

### Why not pytest-xdist for parallel tests?

We could use pytest-xdist to run tests in parallel, but:
- Our test suite is small (49 tests, ~0.4 seconds)
- Parallel overhead would be slower than sequential
- This fixture enables parallelization in the future

### Why not database transactions with rollback?

SQLite doesn't handle concurrent transactions well:
- File-level locking, not row-level
- Async transactions are tricky
- Temporary databases are simpler and more reliable

### Future Improvements

If we add more databases or complexity:
- Factory fixture that returns configured database
- Explicit fixture invocation instead of autouse
- Separate fixture files per test type

For now, the current approach works well.

## Update Log

- **2025-01**: Initial implementation with autouse on all tests
- **2025-01**: Fixed to only apply to integration tests
- **2025-01**: All tests passing in CI
