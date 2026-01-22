"""Main entry point for Kato Discord moderation bot.

This script loads configuration, initializes the bot, and connects to Discord.
The bot will automatically initialize the database and load all cogs on startup.

Usage:
    python main.py

Environment Variables:
    DISCORD_TOKEN: Bot token from Discord Developer Portal (stored in assets/.env)

Configuration:
    Server-specific settings are loaded from assets/config.toml
"""

import os
import sys

from dotenv import load_dotenv

from bot.core.bot import KatoBot
from bot.core.config import Config

# Load environment variables
load_dotenv("assets/.env")


def main() -> None:
    """Initialize and run the Discord bot."""
    # Get Discord token from environment
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print(
            "Error: DISCORD_TOKEN not found in environment variables.", file=sys.stderr
        )
        print(
            "Please ensure assets/.env contains DISCORD_TOKEN=your_token_here",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Load configuration
        config = Config("assets/config.toml")
        print(f"✓ Configuration loaded from {config.path}")

        # Create and run bot
        bot = KatoBot(config)
        print("Starting bot...")
        bot.run(token)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
