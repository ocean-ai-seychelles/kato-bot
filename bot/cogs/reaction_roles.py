"""Reaction role system cog for role assignment via reactions.

This cog handles automatic role assignment when users react to specific messages.
It supports multiple emoji-to-role mappings and persists across bot restarts by
using raw reaction events.

Features:
    - Automatic role assignment on reaction add
    - Automatic role removal on reaction remove
    - Database-backed reaction-role mappings
    - Admin commands to manage reaction roles
    - Works even when bot is offline (raw events)

Example:
    >>> await bot.load_extension('bot.cogs.reaction_roles')

"""

import logging

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import create_error_embed, create_info_embed, create_success_embed

logger = logging.getLogger(__name__)


class ReactionRolesCog(commands.Cog, name="ReactionRoles"):
    """Cog for handling reaction-based role assignment.

    This cog listens for reaction events on configured messages and assigns
    or removes roles based on the emoji used. Uses raw events to work even
    when the bot was offline when reactions were added.

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the reaction roles cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Reaction roles cog initialized")

    async def _get_reaction_role_mapping(
        self, message_id: int, emoji: str
    ) -> int | None:
        """Get the role ID for a given message and emoji.

        Args:
            message_id: The message ID to check.
            emoji: The emoji string to look up.

        Returns:
            The role ID if a mapping exists, None otherwise.

        """
        row = await self.bot.db.fetch_one(
            """
            SELECT role_id FROM reaction_roles
            WHERE message_id = ? AND emoji = ?
            """,
            (message_id, emoji),
        )
        return row["role_id"] if row else None

    async def _sync_reaction_roles_from_config(self, guild_id: int) -> None:
        """Sync reaction role mappings from config.toml to database.

        This reads the [reaction_roles] section from config and ensures
        the database has the correct mappings.

        Args:
            guild_id: The guild ID to sync for.

        """
        # Get config values
        message_id = self.bot.config.get("reaction_roles", "message_id")
        mappings = self.bot.config.get("reaction_roles", "mappings", default=[])

        if not message_id or not mappings:
            logger.warning("No reaction role configuration found in config.toml")
            return

        # Ensure guild_config exists (to satisfy foreign key constraint)
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

        # Clear existing mappings for this message
        await self.bot.db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ?",
            (message_id,),
        )

        # Insert new mappings
        for mapping in mappings:
            emoji = mapping.get("emoji")
            role_id = mapping.get("role_id")

            if not emoji or not role_id:
                logger.warning(f"Invalid reaction role mapping: {mapping}")
                continue

            await self.bot.db.execute(
                """
                INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, message_id, emoji, role_id),
            )
            logger.info(
                f"Synced reaction role: {emoji} -> role {role_id} "
                f"on message {message_id}"
            )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Sync reaction roles from config when bot starts.

        This ensures the database has the latest mappings from config.toml.
        """
        guild_id = self.bot.config.get("server", "guild_id")
        if guild_id:
            await self._sync_reaction_roles_from_config(guild_id)
            logger.info("Reaction roles synced from config")

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        """Event handler for when a reaction is added to any message.

        Uses raw events to work even when the message isn't in cache.
        Assigns the configured role when a user reacts with the mapped emoji.

        Args:
            payload: The reaction event payload.

        """
        # Ignore bot reactions
        if payload.member and payload.member.bot:
            return

        # Check if this is a reaction role message
        role_id = await self._get_reaction_role_mapping(
            payload.message_id, str(payload.emoji)
        )

        if not role_id:
            return  # Not a reaction role message

        # Get the guild and role
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.error(f"Could not find guild {payload.guild_id}")
            return

        role = guild.get_role(role_id)
        if not role:
            logger.error(f"Could not find role {role_id} in guild {guild.name}")
            return

        # Get the member (might be None if using raw event)
        member = payload.member or guild.get_member(payload.user_id)
        if not member:
            logger.error(
                f"Could not find member {payload.user_id} in guild {guild.name}"
            )
            return

        # Add the role
        try:
            await member.add_roles(role, reason="Reaction role assignment")
            logger.info(
                f"Assigned role {role.name} to {member.name} "
                f"via reaction {payload.emoji}"
            )
        except discord.Forbidden:
            logger.error(f"Missing permissions to assign role {role.name}")
        except Exception as e:
            logger.error(f"Error assigning role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        """Event handler for when a reaction is removed from any message.

        Uses raw events to work even when the message isn't in cache.
        Removes the configured role when a user removes their reaction.

        Args:
            payload: The reaction event payload.

        """
        # Check if this is a reaction role message
        role_id = await self._get_reaction_role_mapping(
            payload.message_id, str(payload.emoji)
        )

        if not role_id:
            return  # Not a reaction role message

        # Get the guild and role
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.error(f"Could not find guild {payload.guild_id}")
            return

        role = guild.get_role(role_id)
        if not role:
            logger.error(f"Could not find role {role_id} in guild {guild.name}")
            return

        # Get the member
        member = guild.get_member(payload.user_id)
        if not member:
            logger.error(
                f"Could not find member {payload.user_id} in guild {guild.name}"
            )
            return

        # Remove the role
        try:
            await member.remove_roles(role, reason="Reaction role removal")
            logger.info(
                f"Removed role {role.name} from {member.name} "
                f"via reaction removal {payload.emoji}"
            )
        except discord.Forbidden:
            logger.error(f"Missing permissions to remove role {role.name}")
        except Exception as e:
            logger.error(f"Error removing role: {e}")

    @commands.command(name="add_reaction_role")
    @commands.has_permissions(administrator=True)
    async def add_reaction_role(
        self,
        ctx: commands.Context,
        message_id: str,
        emoji: str,
        role: discord.Role,
    ) -> None:
        """Add a new reaction role mapping.

        This command requires administrator permissions. It creates a mapping
        between an emoji on a specific message and a role to assign.

        Args:
            ctx: The command context.
            message_id: The ID of the message to watch for reactions.
            emoji: The emoji to react with (e.g., ✅, 🎮, etc.).
            role: The role to assign when reacted.

        Example:
            !add_reaction_role 1234567890 ✅ @member

        """
        try:
            msg_id = int(message_id)
        except ValueError:
            embed = create_error_embed(
                title="Invalid Message ID",
                description="Message ID must be a number.",
            )
            await ctx.send(embed=embed)
            return

        # Check if mapping already exists
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (msg_id, emoji),
        )

        if existing:
            embed = create_error_embed(
                title="Mapping Already Exists",
                description=f"A reaction role for {emoji} on message {msg_id} "
                f"already exists.\n\n"
                f"Use `!remove_reaction_role {msg_id} {emoji}` to remove it first.",
            )
            await ctx.send(embed=embed)
            return

        # Add the mapping
        await self.bot.db.execute(
            """
            INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)
            """,
            (ctx.guild.id, msg_id, emoji, role.id),
        )

        embed = create_success_embed(
            title="Reaction Role Added",
            description=f"Successfully added reaction role mapping:\n\n"
            f"**Message ID:** {msg_id}\n"
            f"**Emoji:** {emoji}\n"
            f"**Role:** {role.mention}\n\n"
            f"Users who react with {emoji} will receive the {role.mention} role.",
        )
        await ctx.send(embed=embed)
        logger.info(
            f"Added reaction role: {emoji} -> {role.name} on message {msg_id} "
            f"by {ctx.author.name}"
        )

    @commands.command(name="remove_reaction_role")
    @commands.has_permissions(administrator=True)
    async def remove_reaction_role(
        self, ctx: commands.Context, message_id: str, emoji: str
    ) -> None:
        """Remove a reaction role mapping.

        This command requires administrator permissions. It removes the mapping
        between an emoji and a role.

        Args:
            ctx: The command context.
            message_id: The ID of the message.
            emoji: The emoji to remove.

        Example:
            !remove_reaction_role 1234567890 ✅

        """
        try:
            msg_id = int(message_id)
        except ValueError:
            embed = create_error_embed(
                title="Invalid Message ID",
                description="Message ID must be a number.",
            )
            await ctx.send(embed=embed)
            return

        # Check if mapping exists
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (msg_id, emoji),
        )

        if not existing:
            embed = create_error_embed(
                title="Mapping Not Found",
                description=f"No reaction role mapping found for {emoji} "
                f"on message {msg_id}.",
            )
            await ctx.send(embed=embed)
            return

        # Remove the mapping
        await self.bot.db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (msg_id, emoji),
        )

        embed = create_success_embed(
            title="Reaction Role Removed",
            description=f"Successfully removed reaction role mapping:\n\n"
            f"**Message ID:** {msg_id}\n"
            f"**Emoji:** {emoji}",
        )
        await ctx.send(embed=embed)
        logger.info(
            f"Removed reaction role: {emoji} on message {msg_id} by {ctx.author.name}"
        )

    @commands.command(name="list_reaction_roles")
    @commands.has_permissions(administrator=True)
    async def list_reaction_roles(self, ctx: commands.Context) -> None:
        """List all reaction role mappings for this server.

        This command requires administrator permissions. It displays all
        configured reaction role mappings.

        Args:
            ctx: The command context.

        Example:
            !list_reaction_roles

        """
        # Fetch all mappings for this guild
        mappings = await self.bot.db.fetch_all(
            """
            SELECT message_id, emoji, role_id
            FROM reaction_roles
            WHERE guild_id = ?
            ORDER BY message_id
            """,
            (ctx.guild.id,),
        )

        if not mappings:
            embed = create_info_embed(
                title="Reaction Roles",
                description="No reaction role mappings configured.\n\n"
                "Use `!add_reaction_role <message_id> <emoji> <role>` to add one.",
            )
            await ctx.send(embed=embed)
            return

        # Build the listing
        description = "**Configured Reaction Role Mappings:**\n\n"
        current_message_id = None

        for mapping in mappings:
            msg_id = mapping["message_id"]
            emoji = mapping["emoji"]
            role_id = mapping["role_id"]

            # Get the role
            role = ctx.guild.get_role(role_id)
            role_name = role.mention if role else f"Unknown Role ({role_id})"

            # Group by message ID
            if msg_id != current_message_id:
                if current_message_id is not None:
                    description += "\n"
                description += f"**Message ID:** {msg_id}\n"
                current_message_id = msg_id

            description += f"  {emoji} → {role_name}\n"

        embed = create_info_embed(
            title="Reaction Roles",
            description=description,
        )
        await ctx.send(embed=embed)

    @commands.command(name="sync_reaction_roles")
    @commands.has_permissions(administrator=True)
    async def sync_reaction_roles(self, ctx: commands.Context) -> None:
        """Sync reaction roles from config.toml to database.

        This command requires administrator permissions. It reloads the
        reaction role mappings from config.toml and updates the database.

        Args:
            ctx: The command context.

        Example:
            !sync_reaction_roles

        """
        await self._sync_reaction_roles_from_config(ctx.guild.id)

        embed = create_success_embed(
            title="Reaction Roles Synced",
            description="Reaction role mappings have been synced from config.toml.\n\n"
            "Use `!list_reaction_roles` to view the current mappings.",
        )
        await ctx.send(embed=embed)
        logger.info(f"Reaction roles synced by {ctx.author.name}")

    @add_reaction_role.error
    @remove_reaction_role.error
    @list_reaction_roles.error
    @sync_reaction_roles.error
    async def reaction_role_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for reaction role commands.

        Args:
            ctx: The command context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            embed = create_error_embed(
                title="Permission Denied",
                description="You need administrator permissions to use this command.",
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = create_error_embed(
                title="Missing Argument",
                description=f"Missing required argument: `{error.param.name}`\n\n"
                f"Use `!help {ctx.command.name}` for usage information.",
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Error in reaction role command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )
            await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the ReactionRoles cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(ReactionRolesCog(bot))
    logger.info("Reaction roles cog loaded")
