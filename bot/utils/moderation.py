"""Moderation utility functions for the Kato bot.

This module provides helper functions for moderation commands including:
    - Duration parsing and formatting
    - Permission hierarchy checks
    - Common moderation utilities

Example:
    >>> from bot.utils.moderation import parse_duration, can_moderate
    >>> duration = parse_duration("1h30m")
    >>> can_mod, error = can_moderate(moderator, target)

"""

import re
from datetime import timedelta

import discord

# Regex pattern for parsing duration strings
# Supports: 1w2d3h4m5s, 1week, 2days, 3hours, 4minutes, 5seconds
DURATION_PATTERN = re.compile(
    r"(?:(\d+)\s*(?:w(?:eeks?|k)?))?\s*"
    r"(?:(\d+)\s*(?:d(?:ays?)?))?\s*"
    r"(?:(\d+)\s*(?:h(?:(?:ou)?rs?)?))?\s*"
    r"(?:(\d+)\s*(?:m(?:in(?:ute)?s?)?))?\s*"
    r"(?:(\d+)\s*(?:s(?:ec(?:ond)?s?)?))?",
    re.IGNORECASE,
)

# Discord API maximum timeout duration (28 days)
MAX_TIMEOUT_SECONDS = 28 * 24 * 60 * 60


def parse_duration(duration_str: str) -> timedelta | None:
    """Parse a duration string into a timedelta object.

    Supports various formats for specifying time durations:
        - Seconds: 30s, 30sec, 30second, 30seconds
        - Minutes: 5m, 5min, 5minute, 5minutes
        - Hours: 1h, 1hr, 1hour, 1hours
        - Days: 1d, 1day, 1days
        - Weeks: 1w, 1wk, 1week, 1weeks
        - Combined: 1h30m, 2d12h, 1w2d3h4m5s

    Args:
        duration_str: The duration string to parse.

    Returns:
        A timedelta object representing the duration, or None if parsing fails.

    Examples:
        >>> parse_duration("30s")
        datetime.timedelta(seconds=30)
        >>> parse_duration("1h30m")
        datetime.timedelta(seconds=5400)
        >>> parse_duration("invalid")
        None

    """
    if not duration_str or not duration_str.strip():
        return None

    match = DURATION_PATTERN.fullmatch(duration_str.strip())
    if not match:
        return None

    weeks, days, hours, minutes, seconds = match.groups()

    # Calculate total seconds
    total_seconds = (
        int(weeks or 0) * 604800  # 7 * 24 * 60 * 60
        + int(days or 0) * 86400  # 24 * 60 * 60
        + int(hours or 0) * 3600  # 60 * 60
        + int(minutes or 0) * 60
        + int(seconds or 0)
    )

    # Return None if no time was specified
    if total_seconds == 0:
        return None

    return timedelta(seconds=total_seconds)


def format_duration(seconds: int) -> str:
    """Format a duration in seconds to a human-readable string.

    Converts a number of seconds into a string representation using the
    largest appropriate time units (weeks, days, hours, minutes, seconds).

    Args:
        seconds: The duration in seconds to format.

    Returns:
        A human-readable duration string.

    Examples:
        >>> format_duration(30)
        '30 seconds'
        >>> format_duration(3600)
        '1 hour'
        >>> format_duration(5400)
        '1 hour 30 minutes'
        >>> format_duration(90061)
        '1 day 1 hour 1 minute 1 second'

    """
    if seconds <= 0:
        return "0 seconds"

    parts = []

    # Calculate each time unit
    weeks, remainder = divmod(seconds, 604800)
    days, remainder = divmod(remainder, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    # Build the string with proper pluralization
    if weeks:
        parts.append(f"{weeks} week{'s' if weeks != 1 else ''}")
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return " ".join(parts)


def can_moderate(
    moderator: discord.Member,
    target: discord.Member,
) -> tuple[bool, str | None]:
    """Check if a moderator can take action against a target member.

    This function implements permission hierarchy checks to ensure that:
        - Users cannot moderate themselves
        - Users cannot moderate the bot
        - Users cannot moderate the server owner
        - Users cannot moderate members with equal or higher roles

    Args:
        moderator: The member attempting to perform the moderation action.
        target: The member being moderated.

    Returns:
        A tuple of (can_moderate, error_message).
        If can_moderate is True, error_message will be None.
        If can_moderate is False, error_message explains why.

    Examples:
        >>> can_mod, error = can_moderate(ctx.author, member)
        >>> if not can_mod:
        ...     await ctx.send(error)
        ...     return

    """
    # Cannot moderate self
    if moderator.id == target.id:
        return False, "You cannot moderate yourself."

    # Cannot moderate the bot itself
    if target.id == moderator.guild.me.id:
        return False, "I cannot moderate myself."

    # Cannot moderate server owner
    if target.id == moderator.guild.owner_id:
        return False, "You cannot moderate the server owner."

    # Cannot moderate members with equal or higher top role
    if target.top_role >= moderator.top_role:
        return (
            False,
            f"You cannot moderate **{target.display_name}** "
            f"(they have an equal or higher role).",
        )

    # Check if the bot can moderate the target
    bot_member = moderator.guild.me
    if target.top_role >= bot_member.top_role:
        return (
            False,
            f"I cannot moderate **{target.display_name}** "
            f"(my role is not high enough).",
        )

    return True, None
