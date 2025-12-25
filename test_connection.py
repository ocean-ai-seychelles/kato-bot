"""Test script to verify bot can connect to Discord server.

This script tests the bot's ability to:
    - Load configuration and environment variables
    - Initialize the bot
    - Connect to Discord
    - See guild information

This does NOT perform any bot actions - it just connects, logs info, and disconnects.

Usage:
    uv run test_connection.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from bot.core.bot import DoryBot
from bot.core.config import Config

# Load environment variables
load_dotenv("assets/.env")


async def test_connection() -> None:
    """Test bot connection to Discord."""
    # Get Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print(
            "Error: DISCORD_TOKEN not found in environment variables.",
            file=sys.stderr,
        )
        print(
            "Please ensure assets/.env contains DISCORD_TOKEN=your_token_here",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load configuration
    config = Config("assets/config.toml")
    print(f"✓ Configuration loaded from {config.path}")

    # Create bot
    bot = DoryBot(config)
    print("✓ Bot instance created")

    # Track if we've displayed info
    info_displayed = False

    @bot.event
    async def on_ready():
        """Called when bot is connected and ready."""
        nonlocal info_displayed
        if info_displayed:
            return

        print("✓ Successfully authenticated with Discord")
        print("✓ Database connected and migrations applied")
        print("✓ Connected to Discord\n")

        # Display guild information
        print(f"{'=' * 50}")
        print(f"Bot User: {bot.user}")
        print(f"Bot ID: {bot.user.id}")
        print(f"Connected to {len(bot.guilds)} guild(s):")

        for guild in bot.guilds:
            print(f"\n  Guild: {guild.name}")
            print(f"  Guild ID: {guild.id}")
            print(f"  Members: {guild.member_count}")
            print(f"  Owner: {guild.owner}")

            # Check if this is the configured guild
            config_guild_id = config.get("server", "guild_id")
            if config_guild_id and guild.id == config_guild_id:
                print("  ✓ This is your configured guild!")

                # Show some channel info
                print(f"\n  Text Channels ({len(guild.text_channels)}):")
                for channel in guild.text_channels[:5]:  # Show first 5
                    print(f"    - {channel.name} (ID: {channel.id})")
                if len(guild.text_channels) > 5:
                    print(f"    ... and {len(guild.text_channels) - 5} more")

                # Show some role info
                print(f"\n  Roles ({len(guild.roles)}):")
                for role in guild.roles[:5]:  # Show first 5
                    print(f"    - {role.name} (ID: {role.id})")
                if len(guild.roles) > 5:
                    print(f"    ... and {len(guild.roles) - 5} more")
            elif not config_guild_id or config_guild_id == 0:
                print(
                    f"  ⚠ Update config.toml with guild_id = {guild.id} to configure this server"
                )

        print(f"{'=' * 50}\n")
        print("Closing connection...")
        info_displayed = True

        # Close the bot after displaying info
        await bot.close()

    try:
        # Start the bot (this will run until closed)
        await bot.start(token)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()
        print("✓ Connection closed successfully")


def main() -> None:
    """Run the connection test."""
    print("Testing Discord bot connection...\n")
    asyncio.run(test_connection())
    print("\n✓ Connection test completed successfully!")


if __name__ == "__main__":
    main()
