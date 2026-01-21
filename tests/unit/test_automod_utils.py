"""Unit tests for auto-moderation utility functions.

This module tests the helper functions in bot/utils/automod.py including:
    - Caps percentage calculation
    - Banned word matching (literal and regex)
    - Content sanitization

Usage:
    uv run pytest tests/unit/test_automod_utils.py -v

"""

import pytest

from bot.utils.automod import (
    calculate_caps_percentage,
    matches_banned_word,
    sanitize_content_for_log,
)


class TestCalculateCapsPercentage:
    """Tests for the calculate_caps_percentage function."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            # All caps
            ("HELLO", 100.0),
            ("ALL CAPS HERE", 100.0),
            # No caps
            ("hello", 0.0),
            ("all lowercase", 0.0),
            # Mixed case
            ("Hello", 20.0),  # 1 out of 5 letters
            ("HeLLo", 60.0),  # 3 out of 5 letters
            ("Hello World", 20.0),  # 2 out of 10 letters (H, W)
        ],
    )
    def test_caps_calculation(self, text: str, expected: float) -> None:
        """Test that caps percentage is calculated correctly."""
        result = calculate_caps_percentage(text)
        assert result == pytest.approx(expected, rel=0.01)

    def test_empty_string(self) -> None:
        """Test that empty string returns 0."""
        result = calculate_caps_percentage("")
        assert result == 0.0

    def test_no_alphabetic_characters(self) -> None:
        """Test that string with no letters returns 0."""
        result = calculate_caps_percentage("123!@#")
        assert result == 0.0

    def test_only_numbers_and_spaces(self) -> None:
        """Test string with only numbers and spaces."""
        result = calculate_caps_percentage("123 456 789")
        assert result == 0.0

    def test_unicode_letters(self) -> None:
        """Test that unicode letters are counted correctly."""
        # German umlauts
        result = calculate_caps_percentage("ÜBER")
        assert result == 100.0

        result = calculate_caps_percentage("über")
        assert result == 0.0


class TestMatchesBannedWord:
    """Tests for the matches_banned_word function."""

    @pytest.mark.parametrize(
        "text,word,expected",
        [
            # Exact match
            ("badword", "badword", True),
            ("this has badword in it", "badword", True),
            # Case insensitive
            ("BADWORD", "badword", True),
            ("BadWord", "badword", True),
            # Partial match (substring)
            ("badwords is similar", "badword", True),
            ("mybadwordhere", "badword", True),
            # No match
            ("testing", "badword", False),
            ("good word here", "badword", False),
        ],
    )
    def test_literal_matching(self, text: str, word: str, expected: bool) -> None:
        """Test literal (non-regex) word matching."""
        result = matches_banned_word(text, word, is_regex=False)
        assert result is expected

    @pytest.mark.parametrize(
        "text,pattern,expected",
        [
            # Basic regex
            (r"test123", r"test\d+", True),
            ("test", r"test\d+", False),
            # Word boundary
            ("bad word", r"\bbad\b", True),
            ("badword", r"\bbad\b", False),
            # Character classes
            ("a1b2c3", r"[a-z]\d", True),
            ("abc", r"[a-z]\d", False),
        ],
    )
    def test_regex_matching(self, text: str, pattern: str, expected: bool) -> None:
        """Test regex pattern matching."""
        result = matches_banned_word(text, pattern, is_regex=True)
        assert result is expected

    def test_empty_text(self) -> None:
        """Test that empty text returns False."""
        result = matches_banned_word("", "badword")
        assert result is False

    def test_empty_word(self) -> None:
        """Test that empty word returns False."""
        result = matches_banned_word("test text", "")
        assert result is False

    def test_invalid_regex_returns_false(self) -> None:
        """Test that invalid regex patterns return False instead of raising."""
        # Invalid regex pattern (unmatched bracket)
        result = matches_banned_word("test", "[invalid", is_regex=True)
        assert result is False

    def test_special_characters_in_literal(self) -> None:
        """Test that special regex characters are escaped in literal mode."""
        # These characters have special meaning in regex
        result = matches_banned_word("price is $100", "$100", is_regex=False)
        assert result is True

        text = "test (parentheses)"
        result = matches_banned_word(text, "(parentheses)", is_regex=False)
        assert result is True


class TestSanitizeContentForLog:
    """Tests for the sanitize_content_for_log function."""

    def test_short_message(self) -> None:
        """Test that short messages are unchanged."""
        result = sanitize_content_for_log("Short message")
        assert result == "Short message"

    def test_long_message_truncated(self) -> None:
        """Test that long messages are truncated."""
        long_text = "a" * 300
        result = sanitize_content_for_log(long_text, max_length=200)
        assert len(result) <= 210  # Allow some buffer for truncation text
        assert "[truncated]" in result

    def test_newlines_replaced(self) -> None:
        """Test that newlines are replaced with spaces."""
        result = sanitize_content_for_log("line1\nline2\nline3")
        assert "\n" not in result
        assert "line1 line2 line3" == result

    def test_carriage_returns_removed(self) -> None:
        """Test that carriage returns are removed."""
        result = sanitize_content_for_log("line1\r\nline2")
        assert "\r" not in result
        assert "\n" not in result

    def test_empty_message(self) -> None:
        """Test that empty message returns placeholder."""
        result = sanitize_content_for_log("")
        assert result == "[empty message]"

    def test_none_message(self) -> None:
        """Test that None message returns placeholder."""
        result = sanitize_content_for_log(None)
        assert result == "[empty message]"

    def test_custom_max_length(self) -> None:
        """Test custom max_length parameter."""
        text = "a" * 100
        result = sanitize_content_for_log(text, max_length=50)
        assert len(result) <= 60  # Allow buffer


class TestIsModerator:
    """Tests for the is_moderator function."""

    def test_is_moderator_with_administrator(self) -> None:
        """Test that administrator permission returns True."""
        from unittest.mock import MagicMock

        from bot.utils.automod import is_moderator

        member = MagicMock()
        member.guild_permissions.administrator = True
        member.guild_permissions.manage_messages = False
        member.guild_permissions.kick_members = False
        member.guild_permissions.ban_members = False

        assert is_moderator(member) is True

    def test_is_moderator_with_manage_messages(self) -> None:
        """Test that manage_messages permission returns True."""
        from unittest.mock import MagicMock

        from bot.utils.automod import is_moderator

        member = MagicMock()
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_messages = True
        member.guild_permissions.kick_members = False
        member.guild_permissions.ban_members = False

        assert is_moderator(member) is True

    def test_is_moderator_with_kick_members(self) -> None:
        """Test that kick_members permission returns True."""
        from unittest.mock import MagicMock

        from bot.utils.automod import is_moderator

        member = MagicMock()
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_messages = False
        member.guild_permissions.kick_members = True
        member.guild_permissions.ban_members = False

        assert is_moderator(member) is True

    def test_is_moderator_with_ban_members(self) -> None:
        """Test that ban_members permission returns True."""
        from unittest.mock import MagicMock

        from bot.utils.automod import is_moderator

        member = MagicMock()
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_messages = False
        member.guild_permissions.kick_members = False
        member.guild_permissions.ban_members = True

        assert is_moderator(member) is True

    def test_is_moderator_with_no_permissions(self) -> None:
        """Test that no permissions returns False."""
        from unittest.mock import MagicMock

        from bot.utils.automod import is_moderator

        member = MagicMock()
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_messages = False
        member.guild_permissions.kick_members = False
        member.guild_permissions.ban_members = False

        assert is_moderator(member) is False


class TestCountMentions:
    """Tests for the count_mentions function."""

    def test_count_mentions_basic(self) -> None:
        """Test counting mentions from a message."""
        from unittest.mock import MagicMock

        from bot.utils.automod import count_mentions

        message = MagicMock()
        message.mentions = [MagicMock(), MagicMock(), MagicMock()]  # 3 users
        message.role_mentions = [MagicMock()]  # 1 role

        user_mentions, role_mentions = count_mentions(message)

        assert user_mentions == 3
        assert role_mentions == 1

    def test_count_mentions_no_mentions(self) -> None:
        """Test counting when no mentions."""
        from unittest.mock import MagicMock

        from bot.utils.automod import count_mentions

        message = MagicMock()
        message.mentions = []
        message.role_mentions = []

        user_mentions, role_mentions = count_mentions(message)

        assert user_mentions == 0
        assert role_mentions == 0

    def test_count_mentions_only_users(self) -> None:
        """Test counting when only user mentions."""
        from unittest.mock import MagicMock

        from bot.utils.automod import count_mentions

        message = MagicMock()
        message.mentions = [MagicMock() for _ in range(5)]
        message.role_mentions = []

        user_mentions, role_mentions = count_mentions(message)

        assert user_mentions == 5
        assert role_mentions == 0

    def test_count_mentions_only_roles(self) -> None:
        """Test counting when only role mentions."""
        from unittest.mock import MagicMock

        from bot.utils.automod import count_mentions

        message = MagicMock()
        message.mentions = []
        message.role_mentions = [MagicMock() for _ in range(3)]

        user_mentions, role_mentions = count_mentions(message)

        assert user_mentions == 0
        assert role_mentions == 3
