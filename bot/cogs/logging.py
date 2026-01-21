"""Audit logging cog for tracking server events.

This cog provides comprehensive audit logging including:
    - Message edits and deletions
    - Member joins and leaves
    - Moderation action tracking
    - Searchable audit history

All events are logged to the database and optionally posted to a mod-log channel.

Example:
    >>> await bot.load_extension('bot.cogs.logging')

"""

import logging
from datetime import UTC, datetime

import discord
from discord.ext import commands

from bot.core.bot import DoryBot
from bot.utils.automod import sanitize_content_for_log
from bot.utils.embeds import create_error_embed, create_info_embed

logger = logging.getLogger(__name__)


class LoggingCog(commands.Cog, name="Logging"):
    """Cog for audit logging and event tracking.

    This cog monitors server events and logs them to the database
    and mod-log channel for audit purposes.

    Attributes:
        bot: The DoryBot instance.

    """

    def __init__(self, bot: DoryBot) -> None:
        """Initialize the logging cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        # Cache for tracking message content (for edit/delete logging)
        self._message_cache: dict[int, tuple[str, int]] = {}
        logger.info("Logging cog initialized")

    async def _ensure_guild_config(self, guild_id: int) -> None:
        """Ensure guild_config exists for foreign key constraint.

        Args:
            guild_id: The guild ID to ensure exists.

        """
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

    # =========================================================================
    # MESSAGE CACHING
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Cache message content for edit/delete tracking.

        Args:
            message: The incoming message.

        """
        if message.author.bot:
            return
        if not message.guild:
            return

        # Cache the message content and author ID
        self._message_cache[message.id] = (message.content, message.author.id)

        # Limit cache size to prevent memory issues
        if len(self._message_cache) > 10000:
            # Remove oldest entries (first 1000)
            oldest_keys = list(self._message_cache.keys())[:1000]
            for key in oldest_keys:
                del self._message_cache[key]

    # =========================================================================
    # MESSAGE EDIT LOGGING
    # =========================================================================

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Log message edits to database and mod-log channel.

        Args:
            before: The message before editing.
            after: The message after editing.

        """
        # Skip if content unchanged
        if before.content == after.content:
            return

        # Skip bots and DMs
        if after.author.bot:
            return
        if not after.guild:
            return

        # Check if logging is enabled
        if not self.bot.config.get("logging", "log_message_edits", default=True):
            return

        # Log to database
        await self._log_message_event(
            guild_id=after.guild.id,
            channel_id=after.channel.id,
            message_id=after.id,
            author_id=after.author.id,
            content=before.content,
            event_type="edited",
        )

        # Post to mod-log channel
        await self._post_message_edit(before, after)

        logger.debug(f"Logged message edit from {after.author}")

    async def _post_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Post message edit to mod-log channel.

        Args:
            before: The message before editing.
            after: The message after editing.

        """
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if not mod_log_id:
            return

        channel = after.guild.get_channel(mod_log_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Message Edited",
            color=discord.Color.yellow(),
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="Author",
            value=f"{after.author} ({after.author.id})",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=f"<#{after.channel.id}>",
            inline=True,
        )
        embed.add_field(
            name="Message ID",
            value=str(after.id),
            inline=True,
        )

        # Truncate content for display
        before_content = sanitize_content_for_log(before.content, max_length=500)
        after_content = sanitize_content_for_log(after.content, max_length=500)

        embed.add_field(name="Before", value=before_content or "*empty*", inline=False)
        embed.add_field(name="After", value=after_content or "*empty*", inline=False)

        # Add jump link
        embed.add_field(
            name="Jump to Message",
            value=f"[Click here]({after.jump_url})",
            inline=False,
        )

        embed.set_thumbnail(url=after.author.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post to mod-log channel")

    # =========================================================================
    # MESSAGE DELETE LOGGING
    # =========================================================================

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletions to database and mod-log channel.

        Args:
            message: The deleted message.

        """
        # Skip bots and DMs
        if message.author.bot:
            return
        if not message.guild:
            return

        # Check if logging is enabled
        if not self.bot.config.get("logging", "log_message_deletes", default=True):
            return

        # Get content from cache if message content not available
        content = message.content
        if not content and message.id in self._message_cache:
            content, _ = self._message_cache[message.id]

        # Log to database
        await self._log_message_event(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id,
            content=content,
            event_type="deleted",
        )

        # Post to mod-log channel
        await self._post_message_delete(message, content)

        # Remove from cache
        self._message_cache.pop(message.id, None)

        logger.debug(f"Logged message deletion from {message.author}")

    async def _post_message_delete(
        self, message: discord.Message, content: str
    ) -> None:
        """Post message deletion to mod-log channel.

        Args:
            message: The deleted message.
            content: The message content (may be from cache).

        """
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if not mod_log_id:
            return

        channel = message.guild.get_channel(mod_log_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="Author",
            value=f"{message.author} ({message.author.id})",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=f"<#{message.channel.id}>",
            inline=True,
        )
        embed.add_field(
            name="Message ID",
            value=str(message.id),
            inline=True,
        )

        # Truncate content for display
        content_display = sanitize_content_for_log(content, max_length=1000)
        embed.add_field(
            name="Content",
            value=content_display or "*empty or not cached*",
            inline=False,
        )

        # Show attachments if any
        if message.attachments:
            attachment_list = "\n".join(
                f"• {att.filename}" for att in message.attachments[:5]
            )
            if len(message.attachments) > 5:
                attachment_list += f"\n• ...and {len(message.attachments) - 5} more"
            embed.add_field(name="Attachments", value=attachment_list, inline=False)

        embed.set_thumbnail(url=message.author.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post to mod-log channel")

    # =========================================================================
    # MEMBER JOIN/LEAVE LOGGING
    # =========================================================================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Log member joins to mod-log channel.

        Args:
            member: The member who joined.

        """
        if not self.bot.config.get("logging", "log_member_joins", default=True):
            return

        await self._post_member_join(member)
        logger.debug(f"Logged member join: {member}")

    async def _post_member_join(self, member: discord.Member) -> None:
        """Post member join to mod-log channel.

        Args:
            member: The member who joined.

        """
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if not mod_log_id:
            return

        channel = member.guild.get_channel(mod_log_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="Member",
            value=f"{member} ({member.id})",
            inline=True,
        )

        # Account age
        account_age = datetime.now(UTC) - member.created_at.replace(tzinfo=UTC)
        age_days = account_age.days
        if age_days < 7:
            age_warning = " (New account)"
        elif age_days < 30:
            age_warning = ""
        else:
            age_warning = ""

        embed.add_field(
            name="Account Created",
            value=f"{age_days} days ago{age_warning}",
            inline=True,
        )

        # Member count
        embed.add_field(
            name="Member Count",
            value=str(member.guild.member_count),
            inline=True,
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post to mod-log channel")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log member leaves to mod-log channel.

        Args:
            member: The member who left.

        """
        if not self.bot.config.get("logging", "log_member_leaves", default=True):
            return

        await self._post_member_leave(member)
        logger.debug(f"Logged member leave: {member}")

    async def _post_member_leave(self, member: discord.Member) -> None:
        """Post member leave to mod-log channel.

        Args:
            member: The member who left.

        """
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if not mod_log_id:
            return

        channel = member.guild.get_channel(mod_log_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Member Left",
            color=discord.Color.orange(),
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="Member",
            value=f"{member} ({member.id})",
            inline=True,
        )

        # Time in server
        if member.joined_at:
            time_in_server = datetime.now(UTC) - member.joined_at.replace(tzinfo=UTC)
            days = time_in_server.days
            if days == 0:
                duration = "Less than a day"
            elif days == 1:
                duration = "1 day"
            else:
                duration = f"{days} days"
            embed.add_field(name="Time in Server", value=duration, inline=True)

        # Roles
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        if roles:
            roles_display = ", ".join(roles[:10])
            if len(roles) > 10:
                roles_display += f" (+{len(roles) - 10} more)"
            embed.add_field(name="Roles", value=roles_display, inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post to mod-log channel")

    # =========================================================================
    # DATABASE LOGGING
    # =========================================================================

    async def _log_message_event(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        author_id: int,
        content: str,
        event_type: str,
    ) -> None:
        """Log a message event to the database.

        Args:
            guild_id: The guild ID.
            channel_id: The channel ID.
            message_id: The message ID.
            author_id: The author's user ID.
            content: The message content.
            event_type: Type of event (created, edited, deleted).

        """
        await self._ensure_guild_config(guild_id)

        sanitized_content = sanitize_content_for_log(content)

        await self.bot.db.execute(
            """
            INSERT INTO message_logs
            (guild_id, channel_id, message_id, author_id, content, event_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                message_id,
                author_id,
                sanitized_content,
                event_type,
            ),
        )

    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================

    @commands.command(name="audit")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def audit(
        self,
        ctx: commands.Context,
        member: discord.Member | discord.User,
        limit: int = 10,
    ) -> None:
        """View audit log for a user.

        This command requires kick_members permission.

        Args:
            ctx: The command context.
            member: The member to view logs for.
            limit: Maximum number of entries to show (default 10, max 25).

        Example:
            !audit @user
            !audit @user 20

        """
        # Clamp limit
        limit = max(1, min(limit, 25))

        # Fetch message logs
        message_logs = await self.bot.db.fetch_all(
            """
            SELECT event_type, channel_id, content, created_at
            FROM message_logs
            WHERE guild_id = ? AND author_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ctx.guild.id, member.id, limit),
        )

        # Fetch mod actions
        mod_actions = await self.bot.db.fetch_all(
            """
            SELECT action_type, reason, moderator_id, created_at
            FROM mod_actions
            WHERE guild_id = ? AND target_user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ctx.guild.id, member.id, limit),
        )

        # Fetch warnings
        warnings = await self.bot.db.fetch_all(
            """
            SELECT reason, severity, moderator_id, created_at
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ctx.guild.id, member.id, limit),
        )

        # Build response
        if not message_logs and not mod_actions and not warnings:
            embed = create_info_embed(
                title=f"Audit Log for {member}",
                description="No logged activity found for this user.",
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"Audit Log for {member}",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # Message events section
        if message_logs:
            msg_lines = []
            for log in message_logs[:5]:
                event = log["event_type"]
                channel = f"<#{log['channel_id']}>"
                content = log["content"][:50] + "..." if log["content"] else "*empty*"
                msg_lines.append(f"• **{event}** in {channel}: {content}")
            embed.add_field(
                name=f"Message Events ({len(message_logs)} total)",
                value="\n".join(msg_lines),
                inline=False,
            )

        # Mod actions section
        if mod_actions:
            action_lines = []
            for action in mod_actions[:5]:
                action_type = action["action_type"].upper()
                reason = action["reason"][:50] if action["reason"] else "No reason"
                action_lines.append(f"• **{action_type}**: {reason}")
            embed.add_field(
                name=f"Mod Actions ({len(mod_actions)} total)",
                value="\n".join(action_lines),
                inline=False,
            )

        # Warnings section
        if warnings:
            warn_lines = []
            severity_labels = {1: "Low", 2: "Medium", 3: "High"}
            for warn in warnings[:5]:
                severity = severity_labels.get(warn["severity"], "Unknown")
                reason = warn["reason"][:50] if warn["reason"] else "No reason"
                warn_lines.append(f"• **{severity}**: {reason}")
            embed.add_field(
                name=f"Warnings ({len(warnings)} total)",
                value="\n".join(warn_lines),
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="messagelog")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def messagelog(
        self,
        ctx: commands.Context,
        member: discord.Member | discord.User,
        limit: int = 10,
    ) -> None:
        """View detailed message log for a user.

        This command requires kick_members permission.

        Args:
            ctx: The command context.
            member: The member to view logs for.
            limit: Maximum number of entries to show (default 10, max 50).

        Example:
            !messagelog @user
            !messagelog @user 25

        """
        # Clamp limit
        limit = max(1, min(limit, 50))

        # Fetch logs
        logs = await self.bot.db.fetch_all(
            """
            SELECT event_type, channel_id, message_id, content, created_at
            FROM message_logs
            WHERE guild_id = ? AND author_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ctx.guild.id, member.id, limit),
        )

        if not logs:
            embed = create_info_embed(
                title=f"Message Log for {member}",
                description="No message events found for this user.",
            )
            await ctx.send(embed=embed)
            return

        # Build response
        embed = discord.Embed(
            title=f"Message Log for {member}",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        log_text = []
        for log in logs[:15]:
            event = log["event_type"]
            channel = f"<#{log['channel_id']}>"
            content = log["content"][:100] if log["content"] else "*empty*"
            if len(log["content"] or "") > 100:
                content += "..."
            log_text.append(f"**{event}** in {channel}\n{content}\n")

        embed.description = "\n".join(log_text)

        # Footer with total count
        total = await self.bot.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM message_logs
            WHERE guild_id = ? AND author_id = ?
            """,
            (ctx.guild.id, member.id),
        )
        total_count = total["count"] if total else len(logs)
        embed.set_footer(text=f"Showing {len(logs)} of {total_count} events")

        await ctx.send(embed=embed)

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @audit.error
    @messagelog.error
    async def logging_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for logging commands.

        Args:
            ctx: The command context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            embed = create_error_embed(
                title="Permission Denied",
                description="You need kick_members permission to use this command.",
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = create_error_embed(
                title="Missing Argument",
                description=f"Missing required argument: `{error.param.name}`",
            )
        elif isinstance(error, commands.MemberNotFound):
            embed = create_error_embed(
                title="Member Not Found",
                description="Could not find that member.",
            )
        elif isinstance(error, commands.NoPrivateMessage):
            embed = create_error_embed(
                title="Server Only",
                description="This command can only be used in a server.",
            )
        else:
            logger.error(f"Error in logging command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )

        await ctx.send(embed=embed)


async def setup(bot: DoryBot) -> None:
    """Load the Logging cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(LoggingCog(bot))
    logger.info("Logging cog loaded")
