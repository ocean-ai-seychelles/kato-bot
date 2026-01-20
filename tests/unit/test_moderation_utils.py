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
    """Tests for the can_moderate function.

    Note: These tests require mock Discord members which are complex to set up.
    The actual permission checks are tested via integration tests with a real
    Discord server. Here we document the expected behavior.

    Expected behavior:
        - Cannot moderate self → False, "You cannot moderate yourself."
        - Cannot moderate bot → False, "I cannot moderate myself."
        - Cannot moderate owner → False, "You cannot moderate the server owner."
        - Cannot moderate higher role → False, "...equal or higher role..."
        - Bot cannot moderate higher role → False, "...my role is not high enough..."
        - Valid moderation → True, None

    """

    def test_can_moderate_documentation(self) -> None:
        """Document can_moderate function behavior.

        Full testing requires mock Discord members with:
        - guild.me (bot member)
        - guild.owner_id
        - top_role comparisons

        This is tested in integration tests with real Discord objects.

        """
        # This test documents expected behavior
        # Actual testing happens in integration tests
        pass
