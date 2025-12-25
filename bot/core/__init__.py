"""Core bot infrastructure and foundational components.

This package contains the essential building blocks for the Dory moderation bot,
including the custom bot class, configuration management, and database layer.
All other bot components depend on the infrastructure provided here.

Modules:
    bot: Custom DoryBot class that extends discord.ext.commands.Bot with
        database and configuration integration, cog loading, and async
        initialization via setup_hook().

    config: TOML-based configuration loader with validation and nested key
        access. Handles loading server-specific settings like channel IDs,
        role IDs, moderation rules, and auto-moderation thresholds.

    database: Async SQLite database layer using aiosqlite. Provides database
        connection management, schema initialization via migrations, and
        helper methods for common CRUD operations.

Design Principles:
    - Async-first: All I/O operations use asyncio to prevent blocking
    - Configuration-driven: Settings externalized to TOML files
    - Migration-based schema: Database schema versioned and applied via migrations
    - Separation of concerns: Each module has a single, well-defined responsibility

Example:
    >>> from bot.core.config import Config
    >>> from bot.core.bot import DoryBot
    >>>
    >>> config = Config("assets/config.toml")
    >>> bot = DoryBot(config)
    >>> bot.run(token)

"""
