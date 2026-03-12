"""Custom bot class for Kato moderation bot.

This module defines the KatoBot class, which extends discord.ext.commands.Bot
with integrated configuration and database management. The bot automatically
loads cogs on startup and provides access to configuration and database
connections to all cogs.

Example:
    >>> from bot.core.config import Config
    >>> from bot.core.bot import KatoBot
    >>> import os
    >>>
    >>> config = Config("assets/config.toml")
    >>> bot = KatoBot(config)
    >>> bot.run(os.getenv("DISCORD_TOKEN"))

"""

import logging

import discord
from discord.ext import commands

from bot.core.config import Config
from bot.core.database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class KatoBot(commands.Bot):
    """Custom Bot class for Kato moderation bot.

    This class extends discord.ext.commands.Bot with:
        - Integrated configuration management
        - Database connection and initialization
        - Automatic cog loading on startup
        - Proper cleanup on shutdown

    Attributes:
        config: Configuration object loaded from TOML file.
        db: Database connection manager.

    Example:
        >>> config = Config("assets/config.toml")
        >>> bot = KatoBot(config)
        >>> await bot.start(token)

    """

    def __init__(self, config: Config) -> None:
        """Initialize bot with configuration.

        This sets up the bot with the required intents, command prefix, and
        stores references to the configuration and database objects.

        Args:
            config: Configuration object loaded from TOML file.

        """
        # Configure required intents
        intents = discord.Intents.default()
        intents.members = True  # For on_member_join
        intents.message_content = True  # For auto-moderation
        intents.reactions = True  # For reaction roles
        intents.moderation = True  # For ban/kick events

        super().__init__(command_prefix="!", intents=intents)

        self.config = config
        self.db = Database()

        logger.info("KatoBot initialized with config from %s", config.path)

    async def setup_hook(self) -> None:
        """Async initialization hook called before bot connects to Discord.

        This method:
            1. Connects to the database
            2. Applies database migrations
            3. Loads all cogs

        This runs automatically when the bot starts.
        """
        logger.info("Running setup hook...")

        # Initialize database
        await self.db.connect()
        logger.info("✓ Database connected")

        await self.db.apply_migrations()
        logger.info("✓ Database migrations applied")

        # Load cogs
        # Onboarding must be loaded before welcome (welcome uses onboarding view)
        # Interest roles must be loaded after onboarding (uses onboarding verification)
        await self.load_extension("bot.cogs.onboarding")
        logger.info("✓ Onboarding cog loaded")

        await self.load_extension("bot.cogs.interest_roles")
        logger.info("✓ Interest roles cog loaded")

        await self.load_extension("bot.cogs.welcome")
        logger.info("✓ Welcome cog loaded")

        await self.load_extension("bot.cogs.reaction_roles")
        logger.info("✓ Reaction roles cog loaded")

        await self.load_extension("bot.cogs.moderation")
        logger.info("✓ Moderation cog loaded")

        await self.load_extension("bot.cogs.automod")
        logger.info("✓ AutoMod cog loaded")

        await self.load_extension("bot.cogs.logging")
        logger.info("✓ Logging cog loaded")

        await self.load_extension("bot.cogs.admin")
        logger.info("✓ Admin cog loaded")

        await self.load_extension("bot.cogs.coc")
        logger.info("✓ CoC cog loaded")

        await self.load_extension("bot.cogs.livestream")
        logger.info("✓ Livestream cog loaded")

        logger.info("✓ Setup complete")

    async def on_ready(self) -> None:
        """Event handler called when bot is connected and ready.

        This logs connection information and bot statistics.
        """
        logger.info("=" * 50)
        logger.info("Bot is ready!")
        logger.info(f"Logged in as: {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        logger.info("=" * 50)

    async def close(self) -> None:
        """Cleanup when bot is shutting down.

        This ensures the database connection is properly closed before
        the bot disconnects from Discord.
        """
        logger.info("Shutting down bot...")

        if self.db:
            await self.db.close()
            logger.info("✓ Database connection closed")

        await super().close()
        logger.info("✓ Bot shutdown complete")
