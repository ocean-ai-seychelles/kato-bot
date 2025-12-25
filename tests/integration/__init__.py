"""Integration tests that run against a real Discord test server.

These tests validate the bot's behavior in a real Discord environment, ensuring
that all features work correctly with the actual Discord API. Integration tests
are more comprehensive than unit tests but require a test Discord server and
take longer to run.

Test Modules:
    test_welcome.py:
        - Member join triggers welcome message in correct channel
        - Template variables ({mention}, {user}, {server}) are substituted
        - Welcome disabled state prevents messages
        - Admin commands can update welcome channel/message

    test_reaction_roles.py:
        - Adding reaction assigns configured role to user
        - Removing reaction removes the role
        - Bot restart preserves reaction role mappings (raw events)
        - Invalid emoji/role IDs are handled gracefully
        - Multiple reaction-role mappings on same message work correctly

    test_automod.py:
        - Spam: Rapid messages trigger timeout and deletion
        - Caps: Messages with >70% caps are deleted
        - Mass mentions: Messages with >5 mentions are deleted
        - Banned words: Both literal and regex patterns are detected
        - Violations are logged to database with correct metadata
        - Normal messages are not flagged (no false positives)

    test_moderation.py:
        - Kick command removes user from server (with permissions)
        - Ban command bans user (with permissions)
        - Timeout command applies timeout with correct duration
        - Warn command increments warning count in database
        - Warning thresholds trigger automatic escalation
        - Permission checks prevent unauthorized command usage
        - Moderators cannot moderate other moderators

    test_logging.py:
        - Message deletions are logged to database and mod channel
        - Message edits capture before/after content
        - Member leaves are logged
        - Moderation actions are automatically logged
        - Audit command retrieves user history correctly

Setup Requirements:
    1. Create a Discord test server separate from production
    2. Invite the bot with appropriate permissions:
        - Manage Roles
        - Kick Members
        - Ban Members
        - Moderate Members (for timeouts)
        - Manage Messages
        - Read Message History
        - Add Reactions
    3. Create test channels: #welcome, #getting-started, #mod-log, #general
    4. Create test roles: @moderator, @admin, @initial-role
    5. Store server/channel/role IDs in tests/test_config/test_server.toml
    6. Ensure bot has higher role hierarchy than @moderator and @initial-role

Running Integration Tests:
    # All integration tests
    uv run pytest tests/integration/ -v

    # Specific test file
    uv run pytest tests/integration/test_welcome.py -v

    # Specific test function
    uv run pytest tests/integration/test_welcome.py::test_welcome_message_sent -v

Notes:
    - Integration tests make real API calls and may be rate-limited
    - Tests should clean up after themselves (delete test messages, remove roles)
    - Use pytest markers to skip integration tests in CI if needed
    - Test server should be isolated to prevent interference between test runs

"""
