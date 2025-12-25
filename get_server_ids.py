"""Helper script to get all Discord server IDs for configuration.

This script displays all channels and roles in your Discord server with their IDs,
making it easy to populate assets/config.toml.

Usage:
    uv run get_server_ids.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from bot.core.bot import DoryBot
from bot.core.config import Config

# Load environment variables
load_dotenv("assets/.env")


async def get_server_ids() -> None:
    """Fetch and display all server IDs."""
    # Get Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print(
            "Error: DISCORD_TOKEN not found in environment variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load configuration
    config = Config("assets/config.toml")

    # Create bot
    bot = DoryBot(config)

    # Track if we've displayed info
    info_displayed = False

    @bot.event
    async def on_ready():
        """Called when bot is connected and ready."""
        nonlocal info_displayed
        if info_displayed:
            return

        print("Connected to Discord!\n")

        config_guild_id = config.get("server", "guild_id")
        target_guild = None

        # Find the configured guild
        for guild in bot.guilds:
            if guild.id == config_guild_id:
                target_guild = guild
                break

        if not target_guild:
            print("Error: Could not find configured guild", file=sys.stderr)
            await bot.close()
            return

        print(f"{'=' * 70}")
        print(f"Server: {target_guild.name}")
        print(f"Server ID: {target_guild.id}")
        print(f"{'=' * 70}\n")

        # Display all text channels
        print("TEXT CHANNELS:")
        print("-" * 70)
        for channel in target_guild.text_channels:
            category = f"[{channel.category}] " if channel.category else ""
            print(f"{category}{channel.name:40} ID: {channel.id}")

        # Display all voice channels
        if target_guild.voice_channels:
            print("\nVOICE CHANNELS:")
            print("-" * 70)
            for channel in target_guild.voice_channels:
                category = f"[{channel.category}] " if channel.category else ""
                print(f"{category}{channel.name:40} ID: {channel.id}")

        # Display all roles
        print("\nROLES:")
        print("-" * 70)
        for role in target_guild.roles:
            if role.name == "@everyone":
                continue
            color = f"(color: {role.color})" if role.color.value != 0 else ""
            print(f"{role.name:40} ID: {role.id:20} {color}")

        print(f"\n{'=' * 70}")
        print("\nConfiguration Instructions:")
        print("-" * 70)
        print("1. Copy the IDs you need from above")
        print("2. Update assets/config.toml with these IDs:")
        print("   - channels.welcome: Channel for welcome messages")
        print("   - channels.getting_started: Channel for reaction roles")
        print("   - channels.mod_log: Channel for moderation logs")
        print("   - roles.initial: Role assigned via reaction")
        print("   - roles.moderator: Moderator role")
        print("   - roles.admin: Admin role")
        print(f"{'=' * 70}\n")

        info_displayed = True
        await bot.close()

    try:
        await bot.start(token)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()


def main() -> None:
    """Run the ID fetcher."""
    print("Fetching Discord server IDs...\n")
    asyncio.run(get_server_ids())
    print("Done!")


if __name__ == "__main__":
    main()
