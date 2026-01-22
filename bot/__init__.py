"""Kato Discord Moderation Bot.

This package implements a comprehensive Discord moderation bot for the OCEAN AI
community server. The bot provides automated moderation, role management via
reaction-based assignment, welcome messages for new members, and a full suite
of manual moderation commands with permission checks.

Key Features:
    - Automated welcome messages with template variable support
    - Reaction-based role assignment for server access control
    - Auto-moderation: spam detection, banned words, excessive caps, mass mentions
    - Manual moderation commands: kick, ban, warn, timeout
    - User warning system with configurable escalation thresholds
    - Comprehensive audit logging for all moderation actions and message events
    - SQLite database for persistent data storage
    - TOML-based configuration for server-specific settings

Architecture:
    The bot follows discord.py's Cogs pattern for modularity, with functionality
    organized into separate cogs (welcome, roles, automod, moderation, logging,
    admin). Core infrastructure (bot class, database, config) is in bot.core.

Usage:
    The bot is initialized and run from main.py, which loads configuration,
    initializes the database, and loads all cogs before connecting to Discord.

See Also:
    bot.core: Core infrastructure components
    bot.cogs: Modular functionality organized by feature
    bot.utils: Shared utilities and helper functions

"""
