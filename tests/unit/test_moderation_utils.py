"""Unit tests for moderation utility functions.

This module tests the helper functions in bot/utils/moderation.py including:
    - Duration parsing
    - Duration formatting
    - Permission hierarchy checks

Usage:
    uv run pytest tests/unit/test_moderation_utils.py -v

"""

from datetime import timedelta

import pytest

from bot.utils.moderation import format_duration, parse_duration


class TestParseDuration:
    """Tests for the parse_duration function."""

    @pytest.mark.parametrize(
        "input_str,expected_seconds",
        [
            # Single units
            ("30s", 30),
            ("30sec", 30),
            ("30second", 30),
            ("30seconds", 30),
            ("5m", 300),
            ("5min", 300),
            ("5minute", 300),
            ("5minutes", 300),
            ("1h", 3600),
            ("1hr", 3600),
            ("1hour", 3600),
            ("1hours", 3600),
            ("1d", 86400),
            ("1day", 86400),
            ("1days", 86400),
            ("1w", 604800),
            ("1wk", 604800),
            ("1week", 604800),
            ("1weeks", 604800),
            # Combined units
            ("1h30m", 5400),
            ("2d12h", 216000),
            ("1w2d", 777600),
            ("1h30m45s", 5445),
            ("1w2d3h4m5s", 788645),
            # With spaces
            ("1h 30m", 5400),
            ("1 hour 30 minutes", 5400),
            # Case insensitive
            ("1H30M", 5400),
            ("1HOUR", 3600),
        ],
    )
    def test_valid_durations(self, input_str: str, expected_seconds: int) -> None:
        """Test that valid duration strings are parsed correctly."""
        result = parse_duration(input_str)
        assert result == timedelta(seconds=expected_seconds)

    @pytest.mark.parametrize(
        "input_str",
        [
            "",
            "   ",
            "invalid",
            "abc",
            "1x",
            "hello world",
            "-1h",  # Negative not supported
        ],
    )
    def test_invalid_durations_return_none(self, input_str: str) -> None:
        """Test that invalid duration strings return None."""
        result = parse_duration(input_str)
        assert result is None

    def test_zero_duration_returns_none(self) -> None:
        """Test that zero duration returns None."""
        result = parse_duration("0s")
        assert result is None

    def test_large_duration(self) -> None:
        """Test parsing large duration values."""
        result = parse_duration("52w")
        assert result == timedelta(weeks=52)


class TestFormatDuration:
    """Tests for the format_duration function."""

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            # Single units
            (1, "1 second"),
            (30, "30 seconds"),
            (60, "1 minute"),
            (120, "2 minutes"),
            (3600, "1 hour"),
            (7200, "2 hours"),
            (86400, "1 day"),
            (172800, "2 days"),
            (604800, "1 week"),
            (1209600, "2 weeks"),
            # Combined units
            (61, "1 minute 1 second"),
            (3661, "1 hour 1 minute 1 second"),
            (5400, "1 hour 30 minutes"),
            (90061, "1 day 1 hour 1 minute 1 second"),
            (788645, "1 week 2 days 3 hours 4 minutes 5 seconds"),
        ],
    )
    def test_format_duration(self, seconds: int, expected: str) -> None:
        """Test that durations are formatted correctly."""
        result = format_duration(seconds)
        assert result == expected

    def test_zero_seconds(self) -> None:
        """Test formatting zero seconds."""
        result = format_duration(0)
        assert result == "0 seconds"

    def test_negative_seconds(self) -> None:
        """Test formatting negative seconds returns zero."""
        result = format_duration(-100)
        assert result == "0 seconds"


class TestCanModerate:
    """Tests for the can_moderate function using mock Discord members."""

    def test_cannot_moderate_self(self) -> None:
        """Test that users cannot moderate themselves."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        moderator = MagicMock()
        moderator.id = 12345

        target = MagicMock()
        target.id = 12345  # Same as moderator

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert error == "You cannot moderate yourself."

    def test_cannot_moderate_bot(self) -> None:
        """Test that users cannot moderate the bot itself."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999  # Bot's ID

        target = MagicMock()
        target.id = 99999  # Same as bot

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert error == "I cannot moderate myself."

    def test_cannot_moderate_server_owner(self) -> None:
        """Test that users cannot moderate the server owner."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999
        moderator.guild.owner_id = 55555

        target = MagicMock()
        target.id = 55555  # Server owner

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert error == "You cannot moderate the server owner."

    def test_cannot_moderate_higher_role(self) -> None:
        """Test that users cannot moderate members with higher roles."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        # Create mock roles with position comparison
        high_role = MagicMock()
        high_role.__ge__ = lambda self, other: True  # Always greater or equal

        low_role = MagicMock()
        low_role.__ge__ = lambda self, other: False  # Always less

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999
        moderator.guild.owner_id = 55555
        moderator.top_role = low_role

        target = MagicMock()
        target.id = 67890
        target.display_name = "HighRoleUser"
        target.top_role = high_role

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert "cannot moderate" in error
        assert "equal or higher role" in error

    def test_cannot_moderate_equal_role(self) -> None:
        """Test that users cannot moderate members with equal roles."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        # Create mock role that returns True for >= comparison
        equal_role = MagicMock()
        equal_role.__ge__ = lambda self, other: True

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999
        moderator.guild.owner_id = 55555
        moderator.top_role = equal_role

        target = MagicMock()
        target.id = 67890
        target.display_name = "EqualRoleUser"
        target.top_role = equal_role

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert "equal or higher role" in error

    def test_bot_cannot_moderate_higher_role_target(self) -> None:
        """Test that bot cannot moderate if its role is not high enough."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        # Moderator has high role but bot has low role
        mod_role = MagicMock()
        target_role = MagicMock()
        bot_role = MagicMock()

        # Target role >= moderator role should be False (mod can moderate)
        # Target role >= bot role should be True (bot cannot moderate)
        target_role.__ge__ = lambda self, other: other is bot_role

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999
        moderator.guild.owner_id = 55555
        moderator.top_role = mod_role
        moderator.guild.me.top_role = bot_role

        target = MagicMock()
        target.id = 67890
        target.display_name = "TargetUser"
        target.top_role = target_role

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is False
        assert "my role is not high enough" in error

    def test_can_moderate_valid_target(self) -> None:
        """Test that moderation is allowed when all checks pass."""
        from unittest.mock import MagicMock

        from bot.utils.moderation import can_moderate

        # Create roles where target is always lower
        target_role = MagicMock()
        target_role.__ge__ = lambda self, other: False  # Always lower

        high_role = MagicMock()

        moderator = MagicMock()
        moderator.id = 12345
        moderator.guild.me.id = 99999
        moderator.guild.owner_id = 55555
        moderator.top_role = high_role
        moderator.guild.me.top_role = high_role

        target = MagicMock()
        target.id = 67890
        target.display_name = "ValidTarget"
        target.top_role = target_role

        can_mod, error = can_moderate(moderator, target)

        assert can_mod is True
        assert error is None
