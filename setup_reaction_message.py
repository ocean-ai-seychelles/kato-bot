"""Helper script to post the reaction role message in #getting-started.

This script will:
1. Post a welcome message in the getting-started channel
2. Add a ✅ reaction to it
3. Display the message ID for you to add to config.toml

Usage:
    uv run setup_reaction_message.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from bot.core.bot import DoryBot
from bot.core.config import Config

# Load environment variables
load_dotenv("assets/.env")


async def setup_reaction_message() -> None:
    """Post reaction role message and get its ID."""
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

    # Track if we've posted the message
    message_posted = False

    @bot.event
    async def on_ready():
        """Called when bot is connected and ready."""
        nonlocal message_posted
        if message_posted:
            return

        print("Connected to Discord!\n")

        # Get the guild
        guild_id = config.get("server", "guild_id")
        guild = bot.get_guild(guild_id)

        if not guild:
            print(f"Error: Could not find guild with ID {guild_id}", file=sys.stderr)
            await bot.close()
            return

        # Get the getting-started channel
        getting_started_id = config.get("channels", "getting_started")
        channel = guild.get_channel(getting_started_id)

        if not channel:
            print(
                f"Error: Could not find getting-started channel with ID {getting_started_id}",
                file=sys.stderr,
            )
            await bot.close()
            return

        print(f"Found channel: #{channel.name}")

        # Create the welcome message
        welcome_message = """**Welcome to OCEAN AI!** 🌊

React with ✅ below to gain access to all learning channels:
• #learn-python
• #free-ml-lectures
• #software-eng
• #math
• #robotics

Let's learn together!"""

        try:
            # Post the message
            message = await channel.send(welcome_message)
            print(f"\n✓ Message posted in #{channel.name}")

            # Add the reaction
            await message.add_reaction("✅")
            print("✓ Added ✅ reaction")

            # Pin the message
            await message.pin()
            print("✓ Pinned the message")

            print(f"\n{'=' * 70}")
            print("SUCCESS! Message has been posted and pinned.")
            print(f"{'=' * 70}\n")

            print(f"Message ID: {message.id}\n")

            print("Next steps:")
            print("-" * 70)
            print("1. Add this to assets/config.toml:")
            print(f"   reaction_roles.message_id = {message.id}")
            print("\n2. Update the reaction roles mapping:")
            print(
                f'   mappings = [{{ emoji = "✅", role_id = {config.get("roles", "initial")} }}]'
            )
            print(f"\n{'=' * 70}\n")

        except Exception as e:
            print(f"\nError posting message: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()

        message_posted = True
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
    """Run the reaction message setup."""
    print("Setting up reaction role message in #getting-started...\n")
    asyncio.run(setup_reaction_message())
    print("Done!")


if __name__ == "__main__":
    main()
