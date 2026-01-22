"""Manual moderation cog for kick, ban, timeout, and warning commands.

This cog provides commands for moderators to take action against members.
All actions are logged to the database and optionally to a mod-log channel.

Features:
    - Kick members with reason
    - Ban members with reason
    - Timeout (mute) members for a duration
    - Warning system with severity levels
    - View and clear warnings
    - Automatic mod-log posting

Example:
    >>> await bot.load_extension('bot.cogs.moderation')

"""

import logging
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import create_error_embed, create_info_embed, create_success_embed
from bot.utils.moderation import can_moderate, format_duration, parse_duration

logger = logging.getLogger(__name__)

# Discord API maximum timeout duration (28 days)
MAX_TIMEOUT_DURATION = timedelta(days=28)


class ModerationCog(commands.Cog, name="Moderation"):
    """Cog for manual moderation commands.

    This cog provides kick, ban, timeout, and warning commands for moderators.
    All actions are logged to the database for audit purposes.

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the moderation cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Moderation cog initialized")

    async def _ensure_guild_config(self, guild_id: int) -> None:
        """Ensure guild_config exists for foreign key constraint.

        Args:
            guild_id: The guild ID to ensure exists.

        """
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

    async def _log_mod_action(
        self,
        guild: discord.Guild,
        action_type: str,
        moderator: discord.Member,
        target: discord.Member | discord.User,
        reason: str,
        duration_seconds: int | None = None,
    ) -> None:
        """Log a moderation action to the database and mod-log channel.

        Args:
            guild: The guild where the action occurred.
            action_type: Type of action (kick, ban, timeout, warn).
            moderator: The moderator who performed the action.
            target: The target user.
            reason: The reason for the action.
            duration_seconds: Duration for timeouts (optional).

        """
        await self._ensure_guild_config(guild.id)

        await self.bot.db.execute(
            """
            INSERT INTO mod_actions
            (guild_id, action_type, target_user_id, moderator_id,
             reason, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild.id,
                action_type,
                target.id,
                moderator.id,
                reason,
                duration_seconds,
            ),
        )

        # Post to mod-log channel if configured
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if mod_log_id:
            channel = guild.get_channel(mod_log_id)
            if channel:
                embed = self._create_mod_log_embed(
                    action_type, moderator, target, reason, duration_seconds
                )
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    logger.warning("Missing permissions to post to mod-log channel")

    def _create_mod_log_embed(
        self,
        action_type: str,
        moderator: discord.Member,
        target: discord.Member | discord.User,
        reason: str,
        duration_seconds: int | None = None,
    ) -> discord.Embed:
        """Create an embed for the mod-log channel.

        Args:
            action_type: Type of action taken.
            moderator: The moderator who performed the action.
            target: The target user.
            reason: The reason for the action.
            duration_seconds: Duration for timeouts (optional).

        Returns:
            A formatted Discord embed.

        """
        colors = {
            "warn": discord.Color.yellow(),
            "timeout": discord.Color.orange(),
            "kick": discord.Color.red(),
            "ban": discord.Color.dark_red(),
        }
        color = colors.get(action_type, discord.Color.greyple())

        embed = discord.Embed(
            title=f"Moderation Action: {action_type.upper()}",
            color=color,
            timestamp=datetime.now(UTC),
        )

        embed.add_field(name="Target", value=f"{target} ({target.id})", inline=True)
        embed.add_field(
            name="Moderator", value=f"{moderator} ({moderator.id})", inline=True
        )
        embed.add_field(name="Reason", value=reason, inline=False)

        if duration_seconds:
            embed.add_field(
                name="Duration",
                value=format_duration(duration_seconds),
                inline=True,
            )

        embed.set_thumbnail(url=target.display_avatar.url)

        return embed

    async def _notify_user(
        self,
        user: discord.Member | discord.User,
        guild: discord.Guild,
        action_type: str,
        reason: str,
        duration: str | None = None,
    ) -> bool:
        """Attempt to DM a user about a moderation action.

        Args:
            user: The user to notify.
            guild: The guild where the action occurred.
            action_type: Type of action taken.
            reason: The reason for the action.
            duration: Human-readable duration for timeouts.

        Returns:
            True if DM was sent successfully, False otherwise.

        """
        action_past_tense = {
            "kick": "kicked from",
            "ban": "banned from",
            "timeout": "timed out in",
            "warn": "warned in",
        }
        action_text = action_past_tense.get(action_type, f"{action_type}ed in")

        try:
            embed = discord.Embed(
                title=f"You have been {action_text} {guild.name}",
                color=discord.Color.red(),
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            if duration:
                embed.add_field(name="Duration", value=duration, inline=True)

            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    # =========================================================================
    # KICK COMMAND
    # =========================================================================

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str,
    ) -> None:
        """Kick a member from the server.

        This command requires kick_members permission. The action is logged
        to the database and mod-log channel.

        Args:
            ctx: The command context.
            member: The member to kick.
            reason: The reason for the kick.

        Example:
            !kick @user Spamming in channels

        """
        # Permission hierarchy check
        can_mod, error = can_moderate(ctx.author, member)
        if not can_mod:
            embed = create_error_embed(title="Cannot Kick Member", description=error)
            await ctx.send(embed=embed)
            return

        # Attempt to DM user before kick
        dm_sent = await self._notify_user(member, ctx.guild, "kick", reason)

        # Execute kick
        try:
            await member.kick(reason=f"By {ctx.author}: {reason}")
        except discord.Forbidden:
            embed = create_error_embed(
                title="Missing Permissions",
                description="I don't have permission to kick that member.",
            )
            await ctx.send(embed=embed)
            return
        except discord.HTTPException as e:
            logger.error(f"Failed to kick {member}: {e}")
            embed = create_error_embed(
                title="Kick Failed",
                description="Failed to kick the member due to a Discord error.",
                error_details=str(e),
            )
            await ctx.send(embed=embed)
            return

        # Log to database
        await self._log_mod_action(ctx.guild, "kick", ctx.author, member, reason)

        # Send confirmation
        dm_note = " (DM sent)" if dm_sent else " (Could not DM user)"
        embed = create_success_embed(
            title="Member Kicked",
            description=(
                f"**{member}** has been kicked from the server.{dm_note}\n\n"
                f"**Reason:** {reason}"
            ),
        )
        await ctx.send(embed=embed)

        logger.info(f"{ctx.author} kicked {member} for: {reason}")

    # =========================================================================
    # BAN COMMAND
    # =========================================================================

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str,
    ) -> None:
        """Ban a member from the server.

        This command requires ban_members permission. The action is logged
        to the database and mod-log channel.

        Args:
            ctx: The command context.
            member: The member to ban.
            reason: The reason for the ban.

        Example:
            !ban @user Repeated rule violations

        """
        # Permission hierarchy check
        can_mod, error = can_moderate(ctx.author, member)
        if not can_mod:
            embed = create_error_embed(title="Cannot Ban Member", description=error)
            await ctx.send(embed=embed)
            return

        # Attempt to DM user before ban
        dm_sent = await self._notify_user(member, ctx.guild, "ban", reason)

        # Execute ban
        try:
            await member.ban(reason=f"By {ctx.author}: {reason}")
        except discord.Forbidden:
            embed = create_error_embed(
                title="Missing Permissions",
                description="I don't have permission to ban that member.",
            )
            await ctx.send(embed=embed)
            return
        except discord.HTTPException as e:
            logger.error(f"Failed to ban {member}: {e}")
            embed = create_error_embed(
                title="Ban Failed",
                description="Failed to ban the member due to a Discord error.",
                error_details=str(e),
            )
            await ctx.send(embed=embed)
            return

        # Log to database
        await self._log_mod_action(ctx.guild, "ban", ctx.author, member, reason)

        # Send confirmation
        dm_note = " (DM sent)" if dm_sent else " (Could not DM user)"
        embed = create_success_embed(
            title="Member Banned",
            description=(
                f"**{member}** has been banned from the server.{dm_note}\n\n"
                f"**Reason:** {reason}"
            ),
        )
        await ctx.send(embed=embed)

        logger.info(f"{ctx.author} banned {member} for: {reason}")

    # =========================================================================
    # TIMEOUT COMMAND
    # =========================================================================

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration_str: str,
        *,
        reason: str,
    ) -> None:
        """Timeout (mute) a member for a specified duration.

        This command requires moderate_members permission. The action is logged
        to the database and mod-log channel.

        Duration format: 30s, 5m, 1h, 1d, 1w (or combined like 1h30m)

        Args:
            ctx: The command context.
            member: The member to timeout.
            duration_str: Duration string (e.g., "1h", "30m", "1d").
            reason: The reason for the timeout.

        Example:
            !timeout @user 1h Spamming in chat

        """
        # Parse duration
        duration = parse_duration(duration_str)
        if duration is None:
            embed = create_error_embed(
                title="Invalid Duration",
                description=(
                    "Could not parse duration. Use formats like:\n"
                    "`30s`, `5m`, `1h`, `1d`, `1w`, or combined like `1h30m`"
                ),
            )
            await ctx.send(embed=embed)
            return

        # Check maximum duration
        if duration > MAX_TIMEOUT_DURATION:
            embed = create_error_embed(
                title="Duration Too Long",
                description="Timeout duration cannot exceed 28 days.",
            )
            await ctx.send(embed=embed)
            return

        # Permission hierarchy check
        can_mod, error = can_moderate(ctx.author, member)
        if not can_mod:
            embed = create_error_embed(title="Cannot Timeout Member", description=error)
            await ctx.send(embed=embed)
            return

        # Calculate timeout end time
        timeout_until = datetime.now(UTC) + duration
        duration_seconds = int(duration.total_seconds())
        duration_formatted = format_duration(duration_seconds)

        # Attempt to DM user before timeout
        dm_sent = await self._notify_user(
            member, ctx.guild, "timeout", reason, duration_formatted
        )

        # Execute timeout
        try:
            await member.timeout(timeout_until, reason=f"By {ctx.author}: {reason}")
        except discord.Forbidden:
            embed = create_error_embed(
                title="Missing Permissions",
                description="I don't have permission to timeout that member.",
            )
            await ctx.send(embed=embed)
            return
        except discord.HTTPException as e:
            logger.error(f"Failed to timeout {member}: {e}")
            embed = create_error_embed(
                title="Timeout Failed",
                description="Failed to timeout the member due to a Discord error.",
                error_details=str(e),
            )
            await ctx.send(embed=embed)
            return

        # Log to database
        await self._log_mod_action(
            ctx.guild, "timeout", ctx.author, member, reason, duration_seconds
        )

        # Send confirmation
        dm_note = " (DM sent)" if dm_sent else " (Could not DM user)"
        embed = create_success_embed(
            title="Member Timed Out",
            description=(
                f"**{member}** has been timed out.{dm_note}\n\n"
                f"**Duration:** {duration_formatted}\n"
                f"**Reason:** {reason}"
            ),
        )
        await ctx.send(embed=embed)

        logger.info(
            f"{ctx.author} timed out {member} for {duration_formatted}: {reason}"
        )

    # =========================================================================
    # WARN COMMAND
    # =========================================================================

    @commands.command(name="warn")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        severity: int | None = None,
        *,
        reason: str,
    ) -> None:
        """Issue a warning to a member.

        This command requires kick_members permission. Warnings are stored
        in the database and can be viewed with !warnings.

        Args:
            ctx: The command context.
            member: The member to warn.
            severity: Warning severity 1-3 (optional, default 1).
            reason: The reason for the warning.

        Example:
            !warn @user Being disrespectful
            !warn @user 2 Repeated violations

        """
        # Handle case where severity might be part of reason
        if severity is None:
            severity = 1
        elif severity not in (1, 2, 3):
            # severity was actually part of reason, reconstruct
            reason = f"{severity} {reason}"
            severity = 1

        # Permission hierarchy check
        can_mod, error = can_moderate(ctx.author, member)
        if not can_mod:
            embed = create_error_embed(title="Cannot Warn Member", description=error)
            await ctx.send(embed=embed)
            return

        # Ensure guild config exists
        await self._ensure_guild_config(ctx.guild.id)

        # Insert warning
        await self.bot.db.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ctx.guild.id, member.id, ctx.author.id, reason, severity),
        )

        # Log to mod_actions
        await self._log_mod_action(ctx.guild, "warn", ctx.author, member, reason)

        # Get warning count
        row = await self.bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )
        warning_count = row["count"] if row else 1

        # Attempt to DM user
        dm_sent = await self._notify_user(member, ctx.guild, "warn", reason)

        # Send confirmation
        severity_labels = {1: "Low", 2: "Medium", 3: "High"}
        dm_note = " (DM sent)" if dm_sent else " (Could not DM user)"
        embed = create_success_embed(
            title="Warning Issued",
            description=(
                f"**{member}** has been warned.{dm_note}\n\n"
                f"**Severity:** {severity_labels.get(severity, 'Unknown')}\n"
                f"**Reason:** {reason}\n"
                f"**Total Warnings:** {warning_count}"
            ),
        )
        await ctx.send(embed=embed)

        logger.info(
            f"{ctx.author} warned {member} (severity {severity}): {reason}"
        )

    # =========================================================================
    # WARNINGS COMMAND
    # =========================================================================

    @commands.command(name="warnings")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def warnings(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """View warnings for a member.

        This command requires kick_members permission.

        Args:
            ctx: The command context.
            member: The member to view warnings for.

        Example:
            !warnings @user

        """
        # Fetch warnings
        rows = await self.bot.db.fetch_all(
            """
            SELECT id, reason, severity, moderator_id, created_at
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (ctx.guild.id, member.id),
        )

        if not rows:
            embed = create_info_embed(
                title=f"Warnings for {member}",
                description="This member has no warnings.",
            )
            await ctx.send(embed=embed)
            return

        # Build warnings list
        severity_labels = {1: "Low", 2: "Medium", 3: "High"}
        warning_lines = []
        for row in rows:
            moderator = ctx.guild.get_member(row["moderator_id"])
            mod_name = moderator.display_name if moderator else "Unknown"
            severity_label = severity_labels.get(row["severity"], "Unknown")
            warning_lines.append(
                f"**#{row['id']}** | {severity_label} | by {mod_name}\n"
                f"  {row['reason']}"
            )

        # Get total count
        count_row = await self.bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )
        total = count_row["count"] if count_row else len(rows)

        description = "\n\n".join(warning_lines)
        if total > 10:
            description += f"\n\n*Showing 10 of {total} warnings*"

        embed = create_info_embed(
            title=f"Warnings for {member}",
            description=description,
        )
        embed.set_footer(text=f"Total warnings: {total}")
        await ctx.send(embed=embed)

    # =========================================================================
    # CLEARWARNINGS COMMAND
    # =========================================================================

    @commands.command(name="clearwarnings")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def clearwarnings(
        self,
        ctx: commands.Context,
        member: discord.Member,
        warning_id: int | None = None,
    ) -> None:
        """Clear warnings for a member.

        This command requires administrator permission.
        If warning_id is provided, only that warning is removed.
        Otherwise, all warnings for the member are cleared.

        Args:
            ctx: The command context.
            member: The member to clear warnings for.
            warning_id: Specific warning ID to remove (optional).

        Example:
            !clearwarnings @user
            !clearwarnings @user 5

        """
        if warning_id:
            # Delete specific warning
            result = await self.bot.db.execute(
                """
                DELETE FROM warnings
                WHERE id = ? AND guild_id = ? AND user_id = ?
                """,
                (warning_id, ctx.guild.id, member.id),
            )

            # Check if warning existed
            if result.rowcount == 0:
                embed = create_error_embed(
                    title="Warning Not Found",
                    description=(
                        f"Could not find warning #{warning_id} for **{member}**."
                    ),
                )
                await ctx.send(embed=embed)
                return

            embed = create_success_embed(
                title="Warning Removed",
                description=(
                    f"Warning #{warning_id} has been removed from **{member}**."
                ),
            )
            logger.info(
                f"{ctx.author} removed warning #{warning_id} from {member}"
            )
        else:
            # Delete all warnings
            await self.bot.db.execute(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id),
            )

            embed = create_success_embed(
                title="Warnings Cleared",
                description=f"All warnings have been cleared for **{member}**.",
            )
            logger.info(f"{ctx.author} cleared all warnings for {member}")

        await ctx.send(embed=embed)

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @kick.error
    @ban.error
    @timeout.error
    @warn.error
    @warnings.error
    @clearwarnings.error
    async def moderation_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for moderation commands.

        Args:
            ctx: The command context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            embed = create_error_embed(
                title="Permission Denied",
                description="You don't have permission to use this command.",
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = create_error_embed(
                title="Missing Argument",
                description=(
                    f"Missing required argument: `{error.param.name}`\n\n"
                    f"Use `!help {ctx.command.name}` for usage information."
                ),
            )
        elif isinstance(error, commands.MemberNotFound):
            embed = create_error_embed(
                title="Member Not Found",
                description=(
                    "Could not find that member. They may have left the server."
                ),
            )
        elif isinstance(error, commands.BadArgument):
            embed = create_error_embed(
                title="Invalid Argument",
                description=str(error),
            )
        elif isinstance(error, commands.NoPrivateMessage):
            embed = create_error_embed(
                title="Server Only",
                description="This command can only be used in a server.",
            )
        else:
            logger.error(f"Error in moderation command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )

        await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the Moderation cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(ModerationCog(bot))
    logger.info("Moderation cog loaded")
