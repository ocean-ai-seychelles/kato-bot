"""Livestream announcement cog for OCEAN AI.

Provides commands to announce when you're going live or schedule an
upcoming stream. Automatically pings a configured role or @everyone.

Commands:
    !stream now [title]                    - Announce going live right now
    !stream schedule <date> <time> [title] - Announce an upcoming stream
    !stream cancel [reason]                - Post a cancellation notice

Date formats:  today, tomorrow, YYYY-MM-DD
Time formats:  HH:MM (24h), H:MMam/pm, Hpm  (assumed UTC)

Example:
    >>> await bot.load_extension('bot.cogs.livestream')

"""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import create_error_embed, create_success_embed

logger = logging.getLogger(__name__)

# Accepted date/time parse formats
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
_TIME_FORMATS = ["%H:%M", "%I:%M%p", "%I%p"]


def _parse_date(value: str, tz: ZoneInfo) -> datetime | None:
    """Parse a date string into a datetime at midnight in the given timezone.

    Args:
        value: Date string — today, tomorrow, YYYY-MM-DD, DD/MM/YYYY.
        tz: Timezone to use for "today" / "tomorrow" and naive date strings.

    Returns:
        datetime at midnight in tz, or None if unparseable.

    """
    v = value.strip().lower()
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    if v == "today":
        return today
    if v == "tomorrow":
        return today + timedelta(days=1)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def _parse_time(value: str) -> tuple[int, int] | None:
    """Parse a time string into (hour, minute).

    Args:
        value: Time string (HH:MM, H:MMam, Hpm, etc.).

    Returns:
        (hour, minute) tuple in 24h, or None if unparseable.

    """
    v = value.strip().upper().replace(" ", "")
    for fmt in _TIME_FORMATS:
        try:
            parsed = datetime.strptime(v, fmt)
            return parsed.hour, parsed.minute
        except ValueError:
            continue
    return None


def _build_stream_embed(
    *,
    live: bool,
    title: str,
    scheduled_ts: int | None,
    author: discord.Member,
) -> discord.Embed:
    """Build the announcement embed.

    Args:
        live: True if going live now, False if scheduled.
        title: Stream title/topic.
        scheduled_ts: Unix timestamp for scheduled start (None if live now).
        author: The person who ran the command.

    Returns:
        A styled Discord embed.

    """
    if live:
        now_ts = int(datetime.now(UTC).timestamp())
        embed = discord.Embed(
            title="🔴  LIVE NOW",
            description=f"**{title}**" if title else "Stream is starting now!",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Started",
            value=f"<t:{now_ts}:R>",
            inline=True,
        )
    else:
        embed = discord.Embed(
            title="📅  Upcoming Stream",
            description=f"**{title}**" if title else "A stream has been scheduled.",
            color=discord.Color.og_blurple(),
        )
        embed.add_field(
            name="When",
            value=f"<t:{scheduled_ts}:F>  (<t:{scheduled_ts}:R>)",
            inline=False,
        )

    embed.set_footer(
        text=f"Posted by {author.display_name}",
        icon_url=author.avatar.url if author.avatar else None,
    )
    return embed


_NOT_CONFIGURED = "Set `livestream.announce_channel` in `assets/config.toml`."
_NO_PERMS = "I can't send messages in {channel}."


class LivestreamCog(commands.Cog, name="Livestream"):
    """Cog for livestream announcements.

    Provides commands to announce going live now or schedule upcoming
    streams with automatic pings.

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the livestream cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Livestream cog initialized")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_announce_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Return the configured announcement channel, or None."""
        channel_id = self.bot.config.get("livestream", "announce_channel", default=0)
        if not channel_id:
            return None
        return guild.get_channel(channel_id)

    def _get_timezone(self) -> ZoneInfo:
        """Return the configured timezone, falling back to UTC."""
        tz_name = self.bot.config.get("livestream", "timezone", default="UTC")
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            logger.warning(
                "Unknown timezone %r in config, falling back to UTC", tz_name
            )
            return ZoneInfo("UTC")

    def _get_mention_string(self, guild: discord.Guild) -> str:
        """Return the mention string to prepend to announcements."""
        raw = self.bot.config.get("livestream", "mention", default="@everyone")
        if raw in ("@everyone", "@here"):
            return raw
        try:
            role_id = int(raw)
            role = guild.get_role(role_id)
            return role.mention if role else "@everyone"
        except (ValueError, TypeError):
            return "@everyone"

    # ------------------------------------------------------------------
    # Command group
    # ------------------------------------------------------------------

    @commands.group(name="stream", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def stream(self, ctx: commands.Context) -> None:
        """Livestream announcement commands.

        Subcommands:
            now [title]                    - Go live right now
            schedule <date> <time> [title] - Announce an upcoming stream
            cancel [reason]                - Post a cancellation notice

        """
        embed = create_error_embed(
            title="Missing subcommand",
            description=(
                "**Usage:**\n"
                "`!stream now [title]`\n"
                "`!stream schedule <date> <time> [title]`\n"
                "`!stream cancel [reason]`\n\n"
                "**Date formats:** `today`, `tomorrow`, `YYYY-MM-DD`\n"
                "**Time formats:** `18:00`, `6:30pm`, `6pm`  *(UTC)*"
            ),
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # !stream now
    # ------------------------------------------------------------------

    @stream.command(name="now")
    @commands.has_permissions(administrator=True)
    async def stream_now(self, ctx: commands.Context, *, title: str = "") -> None:
        """Announce that you're going live right now.

        Args:
            ctx: Command context.
            title: Optional stream title/topic.

        Example:
            !stream now Intro to Transformers

        """
        channel = self._get_announce_channel(ctx.guild)
        if not channel:
            await ctx.send(
                embed=create_error_embed(
                    title="Channel not configured",
                    description=_NOT_CONFIGURED,
                )
            )
            return

        mention = self._get_mention_string(ctx.guild)
        embed = _build_stream_embed(
            live=True,
            title=title,
            scheduled_ts=None,
            author=ctx.author,
        )

        try:
            await channel.send(content=mention, embed=embed)
            logger.info(f"Go-live announcement posted by {ctx.author} in {channel}")
            if channel != ctx.channel:
                await ctx.send(
                    embed=create_success_embed(
                        title="Announced!",
                        description=(
                            f"Go-live announcement posted in {channel.mention}."
                        ),
                    )
                )
        except discord.Forbidden:
            await ctx.send(
                embed=create_error_embed(
                    title="Missing permissions",
                    description=_NO_PERMS.format(channel=channel.mention),
                )
            )

    # ------------------------------------------------------------------
    # !stream schedule
    # ------------------------------------------------------------------

    @stream.command(name="schedule")
    @commands.has_permissions(administrator=True)
    async def stream_schedule(
        self,
        ctx: commands.Context,
        date: str,
        time: str,
        *,
        title: str = "",
    ) -> None:
        """Announce an upcoming stream.

        Args:
            ctx: Command context.
            date: Date of the stream (today / tomorrow / YYYY-MM-DD).
            time: Start time in UTC (18:00 / 6:30pm / 6pm).
            title: Optional stream title/topic.

        Example:
            !stream schedule tomorrow 18:00 Reinforcement Learning deep dive

        """
        tz = self._get_timezone()
        tz_label = str(tz)

        parsed_date = _parse_date(date, tz)
        if not parsed_date:
            await ctx.send(
                embed=create_error_embed(
                    title="Invalid date",
                    description=(
                        f"Could not parse `{date}`.\n"
                        "**Accepted:** `today`, `tomorrow`, "
                        "`YYYY-MM-DD`, `DD/MM/YYYY`"
                    ),
                )
            )
            return

        parsed_time = _parse_time(time)
        if not parsed_time:
            await ctx.send(
                embed=create_error_embed(
                    title="Invalid time",
                    description=(
                        f"Could not parse `{time}`.\n"
                        "**Accepted:** `18:00`, `6:30pm`, `6pm`\n"
                        f"*(interpreted as {tz_label})*"
                    ),
                )
            )
            return

        hour, minute = parsed_time
        stream_dt = parsed_date.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        if stream_dt <= datetime.now(tz):
            time_str = stream_dt.strftime(f"%Y-%m-%d %H:%M {tz_label}")
            await ctx.send(
                embed=create_error_embed(
                    title="Date is in the past",
                    description=f"`{time_str}` has already passed.",
                )
            )
            return

        channel = self._get_announce_channel(ctx.guild)
        if not channel:
            await ctx.send(
                embed=create_error_embed(
                    title="Channel not configured",
                    description=_NOT_CONFIGURED,
                )
            )
            return

        mention = self._get_mention_string(ctx.guild)
        ts = int(stream_dt.timestamp())
        embed = _build_stream_embed(
            live=False,
            title=title,
            scheduled_ts=ts,
            author=ctx.author,
        )

        try:
            await channel.send(content=mention, embed=embed)
            logger.info(
                "Stream scheduled for %s by %s in %s",
                stream_dt.isoformat(),
                ctx.author,
                channel,
            )
            if channel != ctx.channel:
                await ctx.send(
                    embed=create_success_embed(
                        title="Scheduled!",
                        description=(
                            f"Stream announcement posted in {channel.mention}.\n"
                            f"**When:** <t:{ts}:F>"
                        ),
                    )
                )
        except discord.Forbidden:
            await ctx.send(
                embed=create_error_embed(
                    title="Missing permissions",
                    description=_NO_PERMS.format(channel=channel.mention),
                )
            )

    # ------------------------------------------------------------------
    # !stream cancel
    # ------------------------------------------------------------------

    @stream.command(name="cancel")
    @commands.has_permissions(administrator=True)
    async def stream_cancel(self, ctx: commands.Context, *, reason: str = "") -> None:
        """Post a stream cancellation notice.

        Args:
            ctx: Command context.
            reason: Optional reason for the cancellation.

        Example:
            !stream cancel Sorry, unexpected schedule conflict

        """
        channel = self._get_announce_channel(ctx.guild)
        if not channel:
            await ctx.send(
                embed=create_error_embed(
                    title="Channel not configured",
                    description=_NOT_CONFIGURED,
                )
            )
            return

        mention = self._get_mention_string(ctx.guild)
        embed = discord.Embed(
            title="❌  Stream Cancelled",
            description=reason if reason else "Today's stream has been cancelled.",
            color=discord.Color.dark_gray(),
        )
        embed.set_footer(
            text=f"Posted by {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None,
        )

        try:
            await channel.send(content=mention, embed=embed)
            logger.info(f"Stream cancellation posted by {ctx.author} in {channel}")
            if channel != ctx.channel:
                await ctx.send(
                    embed=create_success_embed(
                        title="Cancellation posted",
                        description=(f"Cancellation notice sent to {channel.mention}."),
                    )
                )
        except discord.Forbidden:
            await ctx.send(
                embed=create_error_embed(
                    title="Missing permissions",
                    description=_NO_PERMS.format(channel=channel.mention),
                )
            )

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    @stream.error
    @stream_now.error
    @stream_schedule.error
    @stream_cancel.error
    async def stream_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handle errors from stream commands.

        Args:
            ctx: Command context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=create_error_embed(
                    title="Permission Denied",
                    description=(
                        "You need administrator permissions to use this command."
                    ),
                )
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=create_error_embed(
                    title="Missing argument",
                    description=(
                        f"Missing: `{error.param.name}`\n"
                        "Use `!stream` with no arguments to see usage."
                    ),
                )
            )
        else:
            logger.error(f"Error in stream command: {error}")
            await ctx.send(
                embed=create_error_embed(
                    title="Command Error",
                    description="An unexpected error occurred.",
                    error_details=str(error),
                )
            )


async def setup(bot: KatoBot) -> None:
    """Load the Livestream cog."""
    await bot.add_cog(LivestreamCog(bot))
    logger.info("Livestream cog loaded")
