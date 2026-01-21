"""Auto-moderation cog for automatic message filtering.

This cog provides automatic moderation features including:
    - Spam detection (rate limiting)
    - Excessive caps detection
    - Mass mention detection
    - Banned word filtering

All violations are logged to the database and optionally to a mod-log channel.

Example:
    >>> await bot.load_extension('bot.cogs.automod')

"""

import logging
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands

from bot.core.bot import DoryBot
from bot.utils.automod import (
    calculate_caps_percentage,
    count_mentions,
    is_moderator,
    matches_banned_word,
    sanitize_content_for_log,
)
from bot.utils.embeds import create_error_embed, create_info_embed, create_success_embed
from bot.utils.moderation import format_duration

logger = logging.getLogger(__name__)


class AutoModCog(commands.Cog, name="AutoMod"):
    """Cog for automatic message moderation.

    This cog monitors messages and takes automatic action against:
        - Spam (too many messages in a short time)
        - Excessive caps (messages with high percentage of uppercase)
        - Mass mentions (messages with many user/role mentions)
        - Banned words (configurable word list with regex support)

    Attributes:
        bot: The DoryBot instance.

    """

    def __init__(self, bot: DoryBot) -> None:
        """Initialize the auto-moderation cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("AutoMod cog initialized")

    async def _ensure_guild_config(self, guild_id: int) -> None:
        """Ensure guild_config exists for foreign key constraint.

        Args:
            guild_id: The guild ID to ensure exists.

        """
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Sync banned words from config to database on startup."""
        logger.info("AutoMod cog syncing banned words from config...")
        await self._sync_banned_words()
        logger.info("AutoMod cog ready")

    async def _sync_banned_words(self) -> None:
        """Sync banned words from config.toml to database."""
        guild_id = self.bot.config.get("server", "guild_id")
        if not guild_id:
            return

        await self._ensure_guild_config(guild_id)

        # Get words from config
        config_words = self.bot.config.get("automod", "banned_words", "words") or []

        # Insert each word if not exists (not regex by default)
        for word in config_words:
            if word:  # Skip empty strings
                await self.bot.db.execute(
                    """
                    INSERT OR IGNORE INTO banned_words (guild_id, word, is_regex)
                    VALUES (?, ?, 0)
                    """,
                    (guild_id, word),
                )

    # =========================================================================
    # MESSAGE LISTENER
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Check incoming messages for auto-mod violations.

        Args:
            message: The incoming Discord message.

        """
        # Early exits
        if message.author.bot:
            return
        if not message.guild:
            return
        if not self.bot.config.get("automod", "enabled", default=True):
            return
        if is_moderator(message.author):
            return

        # Run checks (stop on first violation)
        if await self._check_spam(message):
            return
        if await self._check_banned_words(message):
            return
        if await self._check_caps(message):
            return
        if await self._check_mass_mentions(message):
            return

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Re-check edited messages for auto-mod violations.

        Args:
            before: The message before editing.
            after: The message after editing.

        """
        # Only re-check if content changed
        if before.content == after.content:
            return

        # Re-run checks on edited message
        await self.on_message(after)

    # =========================================================================
    # CHECK METHODS
    # =========================================================================

    async def _check_spam(self, message: discord.Message) -> bool:
        """Check for spam (rate limiting).

        Args:
            message: The message to check.

        Returns:
            True if violation was detected and handled, False otherwise.

        """
        if not self.bot.config.get("automod", "spam", "enabled", default=True):
            return False

        max_msgs = self.bot.config.get("automod", "spam", "max_messages", default=5)
        window_secs = self.bot.config.get(
            "automod", "spam", "time_window_seconds", default=10
        )
        action = self.bot.config.get("automod", "spam", "action", default="timeout")

        # Get or create rate limit entry
        row = await self.bot.db.fetch_one(
            """
            SELECT message_count, window_start
            FROM rate_limit_cache
            WHERE user_id = ? AND channel_id = ?
            """,
            (message.author.id, message.channel.id),
        )

        now = datetime.now(UTC)
        window = timedelta(seconds=window_secs)

        if row:
            window_start = datetime.fromisoformat(row["window_start"])
            # Handle timezone-naive timestamps from SQLite
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=UTC)

            if now - window_start < window:
                # Within window - increment
                new_count = row["message_count"] + 1
                await self.bot.db.execute(
                    """
                    UPDATE rate_limit_cache
                    SET message_count = ?
                    WHERE user_id = ? AND channel_id = ?
                    """,
                    (new_count, message.author.id, message.channel.id),
                )

                if new_count > max_msgs:
                    await self._take_action(
                        message,
                        action,
                        "spam",
                        f"Spam detected: {new_count} messages in {window_secs} seconds",
                    )
                    return True
            else:
                # Window expired - reset
                await self.bot.db.execute(
                    """
                    UPDATE rate_limit_cache
                    SET message_count = 1, window_start = ?
                    WHERE user_id = ? AND channel_id = ?
                    """,
                    (now.isoformat(), message.author.id, message.channel.id),
                )
        else:
            # New entry
            await self.bot.db.execute(
                """
                INSERT INTO rate_limit_cache
                (user_id, channel_id, message_count, window_start)
                VALUES (?, ?, 1, ?)
                """,
                (message.author.id, message.channel.id, now.isoformat()),
            )

        return False

    async def _check_caps(self, message: discord.Message) -> bool:
        """Check for excessive caps.

        Args:
            message: The message to check.

        Returns:
            True if violation was detected and handled, False otherwise.

        """
        if not self.bot.config.get("automod", "caps", "enabled", default=True):
            return False

        threshold = self.bot.config.get(
            "automod", "caps", "threshold_percentage", default=70
        )
        min_length = self.bot.config.get("automod", "caps", "min_length", default=10)
        action = self.bot.config.get("automod", "caps", "action", default="delete")

        content = message.content

        # Check minimum length
        if len(content) < min_length:
            return False

        caps_percentage = calculate_caps_percentage(content)

        if caps_percentage >= threshold:
            await self._take_action(
                message,
                action,
                "caps",
                f"Excessive caps: {caps_percentage:.0f}% uppercase",
            )
            return True

        return False

    async def _check_mass_mentions(self, message: discord.Message) -> bool:
        """Check for mass mentions.

        Args:
            message: The message to check.

        Returns:
            True if violation was detected and handled, False otherwise.

        """
        if not self.bot.config.get("automod", "mass_mentions", "enabled", default=True):
            return False

        max_mentions = self.bot.config.get(
            "automod", "mass_mentions", "max_mentions", default=5
        )
        action = self.bot.config.get(
            "automod", "mass_mentions", "action", default="delete"
        )

        user_mentions, role_mentions = count_mentions(message)
        total_mentions = user_mentions + role_mentions

        if total_mentions > max_mentions:
            await self._take_action(
                message,
                action,
                "mentions",
                f"Mass mentions: {total_mentions} mentions (max {max_mentions})",
            )
            return True

        return False

    async def _check_banned_words(self, message: discord.Message) -> bool:
        """Check for banned words.

        Args:
            message: The message to check.

        Returns:
            True if violation was detected and handled, False otherwise.

        """
        if not self.bot.config.get("automod", "banned_words", "enabled", default=True):
            return False

        action = self.bot.config.get(
            "automod", "banned_words", "action", default="delete"
        )

        # Get banned words from database
        rows = await self.bot.db.fetch_all(
            "SELECT word, is_regex FROM banned_words WHERE guild_id = ?",
            (message.guild.id,),
        )

        content = message.content

        for row in rows:
            word = row["word"]
            is_regex = bool(row["is_regex"])

            if matches_banned_word(content, word, is_regex):
                await self._take_action(
                    message,
                    action,
                    "banned_word",
                    f"Banned word detected: '{word}'",
                )
                return True

        return False

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    async def _take_action(
        self,
        message: discord.Message,
        action: str,
        violation_type: str,
        reason: str,
    ) -> None:
        """Take moderation action for a violation.

        Args:
            message: The offending message.
            action: The action to take ('delete', 'timeout', 'warn').
            violation_type: Type of violation (spam, caps, mentions, banned_word).
            reason: Human-readable reason for the action.

        """
        # Map violation_type to database enum
        db_violation_type = {
            "spam": "spam",
            "caps": "caps",
            "mentions": "mentions",
            "banned_word": "banned_word",
        }.get(violation_type, violation_type)

        # Map action to database enum
        db_action = {
            "delete": "deleted",
            "timeout": "timeout",
            "warn": "warned",
            "none": "none",
        }.get(action, "none")

        # Log to database
        await self._log_violation(
            message.guild.id,
            message.author.id,
            message.channel.id,
            db_violation_type,
            message.content,
            db_action,
        )

        # Execute action
        if action == "delete":
            try:
                await message.delete()
                logger.info(
                    f"Deleted message from {message.author} for {violation_type}"
                )
            except discord.Forbidden:
                logger.warning("Missing permissions to delete message")
            except discord.NotFound:
                pass  # Message already deleted

        elif action == "timeout":
            timeout_duration = self.bot.config.get(
                "automod", "spam", "timeout_duration", default=300
            )
            try:
                await message.author.timeout(
                    datetime.now(UTC) + timedelta(seconds=timeout_duration),
                    reason=reason,
                )
                await message.delete()
                duration_str = format_duration(timeout_duration)
                logger.info(f"Timed out {message.author} for {duration_str}")
            except discord.Forbidden:
                logger.warning("Missing permissions to timeout member")
            except discord.NotFound:
                pass

        elif action == "warn":
            # Insert warning
            await self._ensure_guild_config(message.guild.id)
            await self.bot.db.execute(
                """
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, severity)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    message.guild.id,
                    message.author.id,
                    self.bot.user.id,
                    f"[AutoMod] {reason}",
                ),
            )
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            logger.info(f"Warned {message.author} for {violation_type}")

        # Notify user via DM
        await self._notify_user(message.author, violation_type, action, reason)

        # Post to mod-log
        await self._post_to_mod_log(message, violation_type, action, reason)

    async def _log_violation(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        violation_type: str,
        content: str,
        action_taken: str,
    ) -> None:
        """Log a violation to the database.

        Args:
            guild_id: The guild ID.
            user_id: The user ID.
            channel_id: The channel ID.
            violation_type: Type of violation.
            content: The message content.
            action_taken: The action taken.

        """
        await self._ensure_guild_config(guild_id)

        sanitized_content = sanitize_content_for_log(content)

        await self.bot.db.execute(
            """
            INSERT INTO automod_violations
            (guild_id, user_id, channel_id, violation_type,
             message_content, action_taken)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                channel_id,
                violation_type,
                sanitized_content,
                action_taken,
            ),
        )

    async def _notify_user(
        self,
        user: discord.Member,
        violation_type: str,
        action: str,
        reason: str,
    ) -> bool:
        """Attempt to DM a user about an auto-mod action.

        Args:
            user: The user to notify.
            violation_type: Type of violation.
            action: The action taken.
            reason: The reason for the action.

        Returns:
            True if DM was sent successfully, False otherwise.

        """
        action_text = {
            "delete": "Your message was deleted",
            "timeout": "You have been timed out",
            "warn": "You have received a warning",
        }.get(action, "Action was taken")

        try:
            embed = discord.Embed(
                title=f"Auto-Moderation: {violation_type.replace('_', ' ').title()}",
                description=f"{action_text} in **{user.guild.name}**.",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text="Please follow the server rules.")

            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _post_to_mod_log(
        self,
        message: discord.Message,
        violation_type: str,
        action: str,
        reason: str,
    ) -> None:
        """Post auto-mod action to mod-log channel.

        Args:
            message: The offending message.
            violation_type: Type of violation.
            action: The action taken.
            reason: The reason for the action.

        """
        mod_log_id = self.bot.config.get("channels", "mod_log")
        if not mod_log_id:
            return

        channel = message.guild.get_channel(mod_log_id)
        if not channel:
            return

        color = {
            "spam": discord.Color.red(),
            "caps": discord.Color.orange(),
            "mentions": discord.Color.orange(),
            "banned_word": discord.Color.red(),
        }.get(violation_type, discord.Color.greyple())

        embed = discord.Embed(
            title=f"Auto-Mod: {violation_type.replace('_', ' ').title()}",
            color=color,
            timestamp=datetime.now(UTC),
        )

        embed.add_field(
            name="User",
            value=f"{message.author} ({message.author.id})",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=f"<#{message.channel.id}>",
            inline=True,
        )
        embed.add_field(
            name="Action",
            value=action.title(),
            inline=True,
        )
        embed.add_field(name="Reason", value=reason, inline=False)

        # Truncate content for display
        content_preview = sanitize_content_for_log(message.content, max_length=500)
        embed.add_field(name="Message Content", value=content_preview, inline=False)

        embed.set_thumbnail(url=message.author.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post to mod-log channel")

    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================

    @commands.command(name="addword")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def addword(self, ctx: commands.Context, *, word: str) -> None:
        """Add a banned word (literal match).

        This command requires administrator permission.

        Args:
            ctx: The command context.
            word: The word to ban.

        Example:
            !addword badword

        """
        await self._ensure_guild_config(ctx.guild.id)

        try:
            await self.bot.db.execute(
                "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 0)",
                (ctx.guild.id, word.lower()),
            )

            embed = create_success_embed(
                title="Banned Word Added",
                description=f"Added `{word}` to the banned words list.",
            )
            logger.info(f"{ctx.author} added banned word: {word}")
        except Exception:
            embed = create_error_embed(
                title="Word Already Exists",
                description=f"`{word}` is already in the banned words list.",
            )

        await ctx.send(embed=embed)

    @commands.command(name="addregex")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def addregex(self, ctx: commands.Context, *, pattern: str) -> None:
        r"""Add a banned word pattern (regex match).

        This command requires administrator permission.

        Args:
            ctx: The command context.
            pattern: The regex pattern to ban.

        Example:
            !addregex test\d+

        """
        # Validate regex
        import re

        try:
            re.compile(pattern)
        except re.error as e:
            embed = create_error_embed(
                title="Invalid Regex",
                description=f"The pattern `{pattern}` is not valid regex.",
                error_details=str(e),
            )
            await ctx.send(embed=embed)
            return

        await self._ensure_guild_config(ctx.guild.id)

        try:
            await self.bot.db.execute(
                "INSERT INTO banned_words (guild_id, word, is_regex) VALUES (?, ?, 1)",
                (ctx.guild.id, pattern),
            )

            embed = create_success_embed(
                title="Banned Regex Added",
                description=f"Added regex `{pattern}` to banned words.",
            )
            logger.info(f"{ctx.author} added banned regex: {pattern}")
        except Exception:
            embed = create_error_embed(
                title="Pattern Already Exists",
                description=f"Pattern `{pattern}` is already banned.",
            )

        await ctx.send(embed=embed)

    @commands.command(name="removeword")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def removeword(self, ctx: commands.Context, *, word: str) -> None:
        """Remove a banned word or pattern.

        This command requires administrator permission.

        Args:
            ctx: The command context.
            word: The word or pattern to remove.

        Example:
            !removeword badword

        """
        result = await self.bot.db.execute(
            "DELETE FROM banned_words WHERE guild_id = ? AND word = ?",
            (ctx.guild.id, word),
        )

        if result.rowcount > 0:
            embed = create_success_embed(
                title="Banned Word Removed",
                description=f"Removed `{word}` from the banned words list.",
            )
            logger.info(f"{ctx.author} removed banned word: {word}")
        else:
            embed = create_error_embed(
                title="Word Not Found",
                description=f"`{word}` was not found in the banned words list.",
            )

        await ctx.send(embed=embed)

    @commands.command(name="listwords")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def listwords(self, ctx: commands.Context) -> None:
        """List all banned words.

        This command requires administrator permission.

        Args:
            ctx: The command context.

        Example:
            !listwords

        """
        rows = await self.bot.db.fetch_all(
            "SELECT word, is_regex FROM banned_words WHERE guild_id = ? ORDER BY word",
            (ctx.guild.id,),
        )

        if not rows:
            embed = create_info_embed(
                title="Banned Words",
                description="No banned words configured.",
            )
            await ctx.send(embed=embed)
            return

        # Build list
        word_list = []
        for row in rows:
            word = row["word"]
            is_regex = bool(row["is_regex"])
            prefix = "[regex] " if is_regex else ""
            word_list.append(f"• {prefix}`{word}`")

        embed = create_info_embed(
            title="Banned Words",
            description="\n".join(word_list),
        )
        embed.set_footer(text=f"Total: {len(rows)} words/patterns")
        await ctx.send(embed=embed)

    @commands.command(name="automod")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def automod_status(self, ctx: commands.Context) -> None:
        """Show auto-moderation status and configuration.

        This command requires administrator permission.

        Args:
            ctx: The command context.

        Example:
            !automod

        """
        enabled = self.bot.config.get("automod", "enabled", default=True)

        status_emoji = "✅" if enabled else "❌"
        embed = discord.Embed(
            title=f"Auto-Moderation Status {status_emoji}",
            color=discord.Color.green() if enabled else discord.Color.red(),
        )

        # Spam settings
        spam_enabled = self.bot.config.get(
            "automod", "spam", "enabled", default=True
        )
        spam_max = self.bot.config.get(
            "automod", "spam", "max_messages", default=5
        )
        spam_window = self.bot.config.get(
            "automod", "spam", "time_window_seconds", default=10
        )
        spam_action = self.bot.config.get(
            "automod", "spam", "action", default="timeout"
        )
        embed.add_field(
            name=f"Spam Detection {'✅' if spam_enabled else '❌'}",
            value=f"Max {spam_max} msgs / {spam_window}s\nAction: {spam_action}",
            inline=True,
        )

        # Caps settings
        caps_enabled = self.bot.config.get(
            "automod", "caps", "enabled", default=True
        )
        caps_threshold = self.bot.config.get(
            "automod", "caps", "threshold_percentage", default=70
        )
        caps_min = self.bot.config.get(
            "automod", "caps", "min_length", default=10
        )
        caps_action = self.bot.config.get(
            "automod", "caps", "action", default="delete"
        )
        caps_status = "✅" if caps_enabled else "❌"
        embed.add_field(
            name=f"Caps Detection {caps_status}",
            value=(
                f"Threshold: {caps_threshold}%\n"
                f"Min length: {caps_min}\n"
                f"Action: {caps_action}"
            ),
            inline=True,
        )

        # Mass mentions settings
        mentions_enabled = self.bot.config.get(
            "automod", "mass_mentions", "enabled", default=True
        )
        mentions_max = self.bot.config.get(
            "automod", "mass_mentions", "max_mentions", default=5
        )
        mentions_action = self.bot.config.get(
            "automod", "mass_mentions", "action", default="delete"
        )
        mentions_status = "✅" if mentions_enabled else "❌"
        embed.add_field(
            name=f"Mass Mentions {mentions_status}",
            value=f"Max mentions: {mentions_max}\nAction: {mentions_action}",
            inline=True,
        )

        # Banned words settings
        words_enabled = self.bot.config.get(
            "automod", "banned_words", "enabled", default=True
        )
        words_action = self.bot.config.get(
            "automod", "banned_words", "action", default="delete"
        )

        # Count banned words
        row = await self.bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM banned_words WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        word_count = row["count"] if row else 0

        embed.add_field(
            name=f"Banned Words {'✅' if words_enabled else '❌'}",
            value=f"Words: {word_count}\nAction: {words_action}",
            inline=True,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @addword.error
    @addregex.error
    @removeword.error
    @listwords.error
    @automod_status.error
    async def automod_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for auto-mod commands.

        Args:
            ctx: The command context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            embed = create_error_embed(
                title="Permission Denied",
                description="You need administrator permission to use this command.",
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = create_error_embed(
                title="Missing Argument",
                description=f"Missing required argument: `{error.param.name}`",
            )
        elif isinstance(error, commands.NoPrivateMessage):
            embed = create_error_embed(
                title="Server Only",
                description="This command can only be used in a server.",
            )
        else:
            logger.error(f"Error in automod command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )

        await ctx.send(embed=embed)


async def setup(bot: DoryBot) -> None:
    """Load the AutoMod cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(AutoModCog(bot))
    logger.info("AutoMod cog loaded")
