# Pitfall 001: Database Locking in Tests

**Date**: 2025-01
**Severity**: High (blocked CI pipeline)
**Status**: Resolved
**Component**: Test suite

## Problem

CI pipeline failed with 4 tests showing database errors:

```
sqlite3.OperationalError: database is locked
sqlite3.IntegrityError: UNIQUE constraint failed: reaction_roles.message_id, reaction_roles.emoji
```

**Symptoms**:
- Tests passed locally when run with `rm -f data/dory.db && pytest`
- Tests failed in CI
- Inconsistent failures (sometimes passed, sometimes failed)
- Only affected integration tests, not unit tests

## Root Cause Analysis

### Why Database Locking Occurred

**SQLite file-level locking**: SQLite locks the entire database file during writes, not individual rows like PostgreSQL.

**Test execution flow**:
1. Test A creates `DoryBot(config)`
2. Bot creates `Database("data/dory.db")`
3. Test A connects, runs migrations, inserts data
4. Test A calls `await bot.db.close()`
5. Test B starts immediately
6. Test B tries to open same `data/dory.db` file
7. **SQLite hasn't released file lock yet** ⚠️
8. Test B fails with "database is locked"

**Why close() wasn't enough**:
```python
await bot.db.close()  # Closes connection
# But SQLite may not release file lock immediately!
# OS-level file handle can remain for milliseconds
```

### Why UNIQUE Constraint Failures Occurred

Tests were sharing the same database file, so:

```python
# Test 1 inserts:
INSERT INTO reaction_roles (message_id, emoji, role_id)
VALUES (789012, "✅", 345678)

# Test 1 "closes" but doesn't clean up data

# Test 2 inserts same data:
INSERT INTO reaction_roles (message_id, emoji, role_id)
VALUES (789012, "✅", 345678)  # ❌ UNIQUE constraint failed!
```

The UNIQUE constraint on `(message_id, emoji)` prevented duplicate inserts.

## Why It Worked Locally But Not in CI

**Locally**:
- Ran `rm -f data/dory.db` before tests manually
- Tests ran sequentially with enough time between them
- File system released locks quickly

**In CI**:
- No manual cleanup step initially
- Tests may have run in parallel or very quickly
- Different file system characteristics (Linux vs macOS)
- Network-attached storage might have slower lock release

## Initial Failed Solutions

### Attempt 1: Database Cleanup in Makefile

```makefile
test:
	rm -f data/dory.db
	uv run pytest tests/ -v
```

**Why it failed**:
- Only cleaned BEFORE tests started
- Tests still shared database during execution
- Didn't help with parallel execution or fast sequential tests

### Attempt 2: Manual Cleanup in Each Test

```python
async def test_example():
    # Test code
    await bot.db.close()
    os.remove("data/dory.db")  # Manual cleanup
```

**Why it failed**:
- Still had race conditions
- Sometimes file was locked during removal
- Boilerplate in every test

## Solution

**See**: [Decision 003: Test Isolation with Fixtures](../decisions/003-test-isolation-fixture.md)

Created pytest fixture that gives each integration test its own temporary database:

```python
@pytest.fixture(scope="function")
async def isolated_database(monkeypatch, request):
    if "integration" not in test_path:
        yield None
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_dory.db"
        # Monkeypatch Database.__init__ to use temp path
```

**Why this works**:
- Each test gets unique database file (no sharing)
- Temporary directory is process-local (no cross-test conflicts)
- Auto-cleanup when test finishes
- OS can clean up temp files aggressively

## Lessons Learned

### SQLite is Not Concurrent-Friendly

- File-level locking, not row-level
- Not suitable for high-concurrency workloads
- Fine for single-process bot, problematic for parallel tests

**Takeaway**: For production multi-instance bots, would need PostgreSQL.

### Close() != Immediate Cleanup

```python
await bot.db.close()  # Closes logical connection
# But OS-level file handle may linger
# File lock may not release instantly
```

**Takeaway**: Don't rely on immediate file lock release in tests.

### Local Success ≠ CI Success

- Different file systems (ext4 vs APFS vs network storage)
- Different timing characteristics
- Different parallelization

**Takeaway**: Always verify tests pass in CI, not just locally.

### Test Isolation is Critical

Shared state between tests is a recipe for flaky tests:
- Hard to debug (timing-dependent failures)
- Inconsistent (sometimes pass, sometimes fail)
- Breaks parallelization

**Takeaway**: Invest in proper test isolation from the start.

## Prevention

### For Future Database Tests

1. **Always use temporary databases** for integration tests
2. **Use pytest fixtures** for automatic setup/teardown
3. **Don't share database files** between tests
4. **Test in CI early** to catch environment-specific issues

### For Future Features

1. **Consider PostgreSQL** if we need multiple bot instances
2. **Design for concurrency** from the start if multi-instance is possible
3. **Document locking behavior** in database documentation

## Impact

**Before fix**:
- ❌ 4 tests failing in CI
- ❌ CI pipeline blocked
- ❌ Could not merge code
- ❌ Flaky tests

**After fix**:
- ✅ All 49 tests passing
- ✅ CI pipeline green
- ✅ Reliable test suite
- ✅ Can run tests in parallel (future)

## Related Documents

- [Decision 003: Test Isolation with Fixtures](../decisions/003-test-isolation-fixture.md)
- [Pitfall 003: Test Pollution and Monkeypatching](003-test-pollution.md)
- [Architecture 001: Database Design](../architecture/001-database-design.md)

## References

- [SQLite File Locking](https://www.sqlite.org/lockingv3.html)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Python tempfile](https://docs.python.org/3/library/tempfile.html)
