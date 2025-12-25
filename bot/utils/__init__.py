"""Shared utility functions and helper modules for the Dory bot.

This package contains reusable utilities that are used across multiple cogs
and bot components. These utilities provide common functionality like permission
checking, embed creation, and general-purpose helper functions that don't belong
to any specific cog.

Modules:
    checks: Custom permission decorators and check functions for commands.
        Includes checks like is_moderator(), is_admin(), and decorators that
        prevent privilege escalation (e.g., moderators can't moderate other
        moderators). These complement discord.py's built-in permission checks.

    embeds: Reusable Discord embed templates and factory functions for
        creating consistent, styled embeds throughout the bot. Includes
        templates for welcome messages, moderation actions, error messages,
        and audit log entries with consistent colors and formatting.

    helpers: General-purpose utility functions used across the bot including:
        - String formatting and template variable substitution
        - Time/duration parsing and formatting
        - User mention and ID extraction from strings
        - Rate limiting and cooldown helpers
        - Logging utilities

Design Principles:
    - DRY (Don't Repeat Yourself): Extract common patterns into utilities
    - Single Responsibility: Each utility has one clear purpose
    - Type Safety: Use type hints for better IDE support and maintainability
    - Documentation: All utilities have comprehensive docstrings with examples

Usage Example:
    >>> from bot.utils.embeds import create_welcome_embed
    >>> from bot.utils.checks import is_moderator
    >>>
    >>> # Create a styled welcome embed
    >>> embed = create_welcome_embed(member, guild)
    >>> await channel.send(embed=embed)
    >>>
    >>> # Use custom permission check in a command
    >>> @commands.command()
    >>> @is_moderator()
    >>> async def my_command(ctx):
    >>>     await ctx.send("You're a moderator!")
"""
