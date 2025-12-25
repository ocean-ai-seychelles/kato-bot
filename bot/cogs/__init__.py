"""Discord.py cogs implementing modular bot functionality.

This package contains all the Discord bot cogs, which are modular command and
event handler containers organized by feature area. Each cog is a self-contained
unit that can be loaded, reloaded, or unloaded independently without restarting
the entire bot.

Cogs follow the discord.py Cogs pattern where each cog is a Python class that
subclasses commands.Cog and contains:
    - Event listeners decorated with @commands.Cog.listener()
    - Commands decorated with @commands.command() or @commands.hybrid_command()
    - Shared state and helper methods for the cog's functionality

Available Cogs:
    welcome: Handles on_member_join events and sends configurable welcome
        messages to new members with template variable substitution.

    reaction_roles: Manages reaction-based role assignment, listening for
        on_raw_reaction_add/remove events to assign/remove roles based on
        database-backed emoji-to-role mappings.

    automod: Automated moderation including spam detection, excessive caps
        checking, mass mention filtering, and banned word detection with
        configurable actions (delete, timeout, warn).

    moderation: Manual moderation commands (kick, ban, warn, timeout) with
        permission checks, plus a warning system with automatic escalation
        based on configurable thresholds.

    logging: Comprehensive audit trail logging message edits/deletes,
        member events, and all moderation actions to both database and
        a designated mod log channel.

    admin: Bot management commands for admins including cog reloading,
        status checks, and configuration synchronization.

Design Pattern:
    Each cog follows a consistent structure:
    1. Initialization with bot reference and config/database access
    2. Event listeners for Discord events (@commands.Cog.listener)
    3. Commands for user/admin interactions (@commands.command)
    4. Helper methods for internal logic
    5. Proper error handling and logging

Loading Cogs:
    Cogs are loaded in bot.core.bot.DoryBot.setup_hook() using:
    >>> await bot.load_extension('bot.cogs.welcome')
    >>> await bot.load_extension('bot.cogs.reaction_roles')
    # etc.
"""
