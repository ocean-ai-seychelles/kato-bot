"""Admin cog for bot management and configuration.

This cog provides administrative commands for managing the bot including:
    - Cog reloading for development
    - Bot status information
    - Configuration management
    - Global error handling

Example:
    >>> await bot.load_extension('bot.cogs.admin')

"""

import logging
import sys
from datetime import UTC, datetime

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import create_error_embed, create_info_embed, create_success_embed

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """Cog for bot administration and management.

    This cog provides commands for bot owners and administrators
    to manage the bot's operation.

    Attributes:
        bot: The KatoBot instance.
        start_time: When the bot started.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the admin cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        self.start_time = datetime.now(UTC)
        logger.info("Admin cog initialized")

    # =========================================================================
    # STATUS COMMAND
    # =========================================================================

    @commands.command(name="status")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def status(self, ctx: commands.Context) -> None:
        """Show bot status and statistics.

        This command requires administrator permission.

        Args:
            ctx: The command context.

        Example:
            !status

        """
        embed = discord.Embed(
            title="Kato Bot Status",
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )

        # Bot info
        embed.add_field(
            name="Bot",
            value=f"{self.bot.user.name}#{self.bot.user.discriminator}",
            inline=True,
        )
        embed.add_field(
            name="ID",
            value=str(self.bot.user.id),
            inline=True,
        )

        # Uptime
        uptime = datetime.now(UTC) - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if days > 0:
            uptime_str = f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            uptime_str = f"{hours}h {minutes}m {seconds}s"
        else:
            uptime_str = f"{minutes}m {seconds}s"

        embed.add_field(name="Uptime", value=uptime_str, inline=True)

        # Stats
        embed.add_field(
            name="Guilds",
            value=str(len(self.bot.guilds)),
            inline=True,
        )
        embed.add_field(
            name="Latency",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True,
        )

        # Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        embed.add_field(
            name="Python",
            value=py_version,
            inline=True,
        )

        # Loaded cogs
        cog_names = list(self.bot.cogs.keys())
        embed.add_field(
            name=f"Cogs ({len(cog_names)})",
            value=", ".join(cog_names) if cog_names else "None",
            inline=False,
        )

        # Database status
        db_status = "Connected" if self.bot.db.connection else "Disconnected"
        embed.add_field(
            name="Database",
            value=db_status,
            inline=True,
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    # =========================================================================
    # RELOAD COMMAND
    # =========================================================================

    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def reload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Reload a cog for development purposes.

        This command requires administrator permission.

        Args:
            ctx: The command context.
            cog_name: The name of the cog to reload (e.g., 'welcome').

        Example:
            !reload welcome
            !reload moderation

        """
        # Build the full extension path
        extension = f"bot.cogs.{cog_name.lower()}"

        try:
            await self.bot.reload_extension(extension)
            embed = create_success_embed(
                title="Cog Reloaded",
                description=f"Successfully reloaded `{cog_name}` cog.",
            )
            logger.info(f"{ctx.author} reloaded cog: {cog_name}")
        except commands.ExtensionNotLoaded:
            embed = create_error_embed(
                title="Cog Not Loaded",
                description=f"Cog `{cog_name}` is not currently loaded.",
            )
        except commands.ExtensionNotFound:
            embed = create_error_embed(
                title="Cog Not Found",
                description=f"Cog `{cog_name}` does not exist.",
            )
        except commands.ExtensionFailed as e:
            embed = create_error_embed(
                title="Reload Failed",
                description=f"Failed to reload `{cog_name}` cog.",
                error_details=str(e.original),
            )
            logger.error(f"Failed to reload {cog_name}: {e}")

        await ctx.send(embed=embed)

    # =========================================================================
    # SYNC CONFIG COMMAND
    # =========================================================================

    @commands.command(name="syncconfig")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def sync_config(self, ctx: commands.Context) -> None:
        """Reload configuration from config.toml.

        This command requires administrator permission. It reloads
        the TOML configuration file without restarting the bot.

        Args:
            ctx: The command context.

        Example:
            !syncconfig

        """
        try:
            # Reload config
            self.bot.config.reload()

            embed = create_success_embed(
                title="Configuration Reloaded",
                description="Successfully reloaded configuration from `config.toml`.",
            )
            logger.info(f"{ctx.author} reloaded configuration")
        except FileNotFoundError:
            embed = create_error_embed(
                title="Config Not Found",
                description="Could not find `assets/config.toml`.",
            )
        except Exception as e:
            embed = create_error_embed(
                title="Reload Failed",
                description="Failed to reload configuration.",
                error_details=str(e),
            )
            logger.error(f"Failed to reload config: {e}")

        await ctx.send(embed=embed)

    # =========================================================================
    # PING COMMAND
    # =========================================================================

    @commands.command(name="ping")
    @commands.guild_only()
    async def ping(self, ctx: commands.Context) -> None:
        """Check bot latency.

        Args:
            ctx: The command context.

        Example:
            !ping

        """
        latency = round(self.bot.latency * 1000)
        embed = create_info_embed(
            title="Pong!",
            description=f"Latency: **{latency}ms**",
        )
        await ctx.send(embed=embed)

    # =========================================================================
    # COGS LIST COMMAND
    # =========================================================================

    @commands.command(name="cogs")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def list_cogs(self, ctx: commands.Context) -> None:
        """List all loaded cogs and their commands.

        This command requires administrator permission.

        Args:
            ctx: The command context.

        Example:
            !cogs

        """
        embed = discord.Embed(
            title="Loaded Cogs",
            color=discord.Color.blue(),
        )

        for cog_name, cog in self.bot.cogs.items():
            commands_list = [cmd.name for cmd in cog.get_commands()]
            listeners = len(cog.get_listeners())

            value = f"Commands: {', '.join(commands_list) if commands_list else 'None'}"
            value += f"\nListeners: {listeners}"

            embed.add_field(
                name=cog_name,
                value=value,
                inline=True,
            )

        embed.set_footer(text=f"Total: {len(self.bot.cogs)} cogs")
        await ctx.send(embed=embed)

    # =========================================================================
    # INFO COMMAND
    # =========================================================================

    @commands.command(name="info")
    @commands.guild_only()
    async def info(self, ctx: commands.Context) -> None:
        """Show information about the bot.

        Args:
            ctx: The command context.

        Example:
            !info

        """
        embed = discord.Embed(
            title="Kato Bot",
            description=(
                "A Discord moderation bot for the OCEAN AI community. "
                "Named after the Kato Nwar (Seychelles Black Parrot) - "
                "a wise guardian helping members follow the community code of conduct."
            ),
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Features",
            value=(
                "- Welcome messages\n"
                "- Reaction role assignment\n"
                "- Auto-moderation (spam, caps, mentions)\n"
                "- Manual moderation (kick, ban, warn)\n"
                "- Audit logging"
            ),
            inline=False,
        )

        embed.add_field(
            name="Commands",
            value="Use `!help` to see available commands.",
            inline=False,
        )

        embed.add_field(
            name="Source",
            value="Made with discord.py",
            inline=True,
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @status.error
    @reload_cog.error
    @sync_config.error
    @list_cogs.error
    async def admin_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for admin commands.

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
            logger.error(f"Error in admin command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )

        await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the Admin cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(AdminCog(bot))
    logger.info("Admin cog loaded")
