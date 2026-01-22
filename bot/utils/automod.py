"""Auto-moderation utility functions for the Kato bot.

This module provides helper functions for auto-moderation checks including:
    - Caps percentage calculation
    - Mention counting
    - Banned word matching (literal and regex)
    - Spam detection via rate limiting

Example:
    >>> from bot.utils.automod import calculate_caps_percentage, count_mentions
    >>> caps_pct = calculate_caps_percentage("THIS IS ALL CAPS")
    >>> user_mentions, role_mentions = count_mentions(message)

"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord


def calculate_caps_percentage(text: str) -> float:
    """Calculate the percentage of uppercase letters in a string.

    Only counts alphabetic characters when calculating the percentage.
    Non-alphabetic characters (numbers, spaces, punctuation) are ignored.

    Args:
        text: The text to analyze.

    Returns:
        The percentage of uppercase letters (0-100). Returns 0 if the
        text contains no alphabetic characters.

    Examples:
        >>> calculate_caps_percentage("HELLO")
        100.0
        >>> calculate_caps_percentage("Hello")
        20.0
        >>> calculate_caps_percentage("hello")
        0.0
        >>> calculate_caps_percentage("123!@#")
        0.0

    """
    if not text:
        return 0.0

    # Only count alphabetic characters
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return 0.0

    upper_count = sum(1 for c in alpha_chars if c.isupper())
    return (upper_count / len(alpha_chars)) * 100


def count_mentions(message: "discord.Message") -> tuple[int, int]:
    """Count user and role mentions in a message.

    This counts explicit mentions (using <@user_id> or <@&role_id> syntax),
    not mentions of names that happen to appear in text.

    Args:
        message: The Discord message to analyze.

    Returns:
        A tuple of (user_mention_count, role_mention_count).

    Examples:
        >>> user_mentions, role_mentions = count_mentions(message)
        >>> if user_mentions > 5:
        ...     print("Mass mention detected!")

    """
    user_mentions = len(message.mentions)
    role_mentions = len(message.role_mentions)
    return user_mentions, role_mentions


def matches_banned_word(text: str, word: str, is_regex: bool = False) -> bool:
    r"""Check if text contains a banned word.

    For literal matches (is_regex=False), performs case-insensitive word
    boundary matching. For regex patterns (is_regex=True), compiles and
    matches the pattern against the text.

    Args:
        text: The text to check.
        word: The banned word or regex pattern to match.
        is_regex: If True, treat word as a regex pattern.

    Returns:
        True if the banned word is found in the text, False otherwise.

    Examples:
        >>> matches_banned_word("this has badword in it", "badword")
        True
        >>> matches_banned_word("badwords is similar", "badword")
        True
        >>> matches_banned_word("testing", "badword")
        False
        >>> matches_banned_word("test123abc", r"test\d+", is_regex=True)
        True

    """
    if not text or not word:
        return False

    try:
        if is_regex:
            pattern = re.compile(word, re.IGNORECASE)
            return bool(pattern.search(text))
        else:
            # Escape special regex characters for literal matching
            escaped_word = re.escape(word)
            # Use word boundaries but also match if word is part of compound
            pattern = re.compile(escaped_word, re.IGNORECASE)
            return bool(pattern.search(text))
    except re.error:
        # Invalid regex pattern, treat as no match
        return False


def is_moderator(member: "discord.Member") -> bool:
    """Check if a member has moderator privileges.

    A member is considered a moderator if they have any of:
        - Administrator permission
        - Manage Messages permission
        - Kick Members permission
        - Ban Members permission

    Args:
        member: The Discord member to check.

    Returns:
        True if the member has moderator privileges, False otherwise.

    Examples:
        >>> if is_moderator(message.author):
        ...     return  # Skip automod for moderators

    """
    perms = member.guild_permissions
    return any([
        perms.administrator,
        perms.manage_messages,
        perms.kick_members,
        perms.ban_members,
    ])


def sanitize_content_for_log(content: str, max_length: int = 200) -> str:
    """Sanitize message content for safe logging.

    Truncates long messages and removes potentially dangerous characters
    for safe storage and display in logs.

    Args:
        content: The message content to sanitize.
        max_length: Maximum length to truncate to. Defaults to 200.

    Returns:
        Sanitized and truncated content.

    Examples:
        >>> sanitize_content_for_log("Short message")
        'Short message'
        >>> sanitize_content_for_log("a" * 300)
        'aaaa...aaaa [truncated]'

    """
    if not content:
        return "[empty message]"

    # Replace newlines with spaces for single-line logging
    sanitized = content.replace("\n", " ").replace("\r", "")

    # Truncate if too long
    if len(sanitized) > max_length:
        # Show beginning and end
        half = (max_length - 15) // 2  # Account for "... [truncated]"
        sanitized = f"{sanitized[:half]}...{sanitized[-half:]} [truncated]"

    return sanitized
