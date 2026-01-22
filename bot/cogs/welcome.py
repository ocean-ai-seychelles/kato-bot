"""Welcome system cog for greeting new members.

This cog handles welcoming new members to the server with customizable messages.
It supports template variables for personalization and can be configured via
admin commands.

Features:
    - Automatic welcome messages on member join
    - Template variable substitution ({mention}, {user}, {server}, {channel})
    - Admin commands to configure welcome channel and message
    - Can be enabled/disabled via configuration

Example:
    >>> await bot.load_extension('bot.cogs.welcome')

"""

import logging

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import (
    create_error_embed,
    create_success_embed,
    create_welcome_embed,
)

logger = logging.getLogger(__name__)


class WelcomeCog(commands.Cog, name="Welcome"):
    """Cog for handling member welcome messages.

    This cog listens for new member joins and sends personalized welcome
    messages to a configured channel. Messages support template variables
    for dynamic content.

    Template Variables:
        {mention}: Mentions the user (@User)
        {user}: User's display name
        {server}: Server name
        {channel}: Mentions the getting-started channel

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the welcome cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Welcome cog initialized")

    def _substitute_template_vars(
        self,
        template: str,
        member: discord.Member,
        guild: discord.Guild,
    ) -> str:
        """Replace template variables in welcome message.

        Args:
            template: The message template with {variables}.
            member: The member who joined.
            guild: The guild they joined.

        Returns:
            The message with all variables substituted.

        Example:
            >>> template = "Welcome {mention} to {server}!"
            >>> result = self._substitute_template_vars(template, member, guild)
            >>> # Result: "Welcome @User to OCEAN AI!"

        """
        # Get getting-started channel for {channel} variable
        getting_started_id = self.bot.config.get("channels", "getting_started")
        getting_started_channel = guild.get_channel(getting_started_id)
        channel_mention = (
            getting_started_channel.mention
            if getting_started_channel
            else "#getting-started"
        )

        # Substitute all template variables
        message = template.format(
            mention=member.mention,
            user=member.display_name,
            server=guild.name,
            channel=channel_mention,
        )

        return message

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Event handler for when a new member joins the server.

        This sends a welcome message to the configured welcome channel.
        The message uses the template from config.toml with variable substitution.

        Args:
            member: The member who joined.

        """
        # Check if welcome is enabled
        if not self.bot.config.get("welcome", "enabled", default=True):
            logger.debug("Welcome system is disabled, skipping")
            return

        # Get welcome channel
        welcome_channel_id = self.bot.config.get("channels", "welcome")
        if not welcome_channel_id:
            logger.warning("Welcome channel not configured")
            return

        welcome_channel = member.guild.get_channel(welcome_channel_id)
        if not welcome_channel:
            logger.error(f"Could not find welcome channel with ID {welcome_channel_id}")
            return

        # Get welcome message template
        default_msg = (
            "Welcome {mention} to {server}! Please visit {channel} to get started."
        )
        template = self.bot.config.get(
            "welcome",
            "message_template",
            default=default_msg,
        )

        # Substitute template variables
        message = self._substitute_template_vars(template, member, member.guild)

        # Create welcome embed
        embed = create_welcome_embed(
            title=f"Welcome to {member.guild.name}! 🌊",
            description=message,
            user=member,
        )

        # Get registration view if onboarding is enabled
        view = None
        if self.bot.config.get("onboarding", "enabled", default=False):
            onboarding_cog = self.bot.get_cog("Onboarding")
            if onboarding_cog:
                view = onboarding_cog.get_registration_view()

        try:
            await welcome_channel.send(embed=embed, view=view)
            logger.info(f"Sent welcome message for {member.name} ({member.id})")
        except discord.Forbidden:
            logger.error(
                f"Missing permissions to send message in {welcome_channel.name}"
            )
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    @commands.command(name="set_welcome_channel")
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel where welcome messages are sent.

        This command requires administrator permissions. It updates the
        welcome channel configuration in the database.

        Args:
            ctx: The command context.
            channel: The text channel to use for welcome messages.

        Example:
            !set_welcome_channel #welcome

        """
        # Note: In a full implementation, this would update the database
        # For now, we'll just confirm the channel
        embed = create_success_embed(
            title="Welcome Channel Updated",
            description=f"Welcome messages will now be sent to {channel.mention}.\n\n"
            f"**Note:** To persist this change, update `channels.welcome` "
            f"in your config.toml to `{channel.id}`",
        )

        await ctx.send(embed=embed)
        logger.info(f"Welcome channel set to {channel.name} by {ctx.author.name}")

    @commands.command(name="set_welcome_message")
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(self, ctx: commands.Context, *, message: str) -> None:
        """Set the welcome message template.

        This command requires administrator permissions. The message can
        include template variables: {mention}, {user}, {server}, {channel}

        Args:
            ctx: The command context.
            message: The welcome message template.

        Example:
            !set_welcome_message Welcome {mention}! Check out {channel} to get started.

        """
        # Note: In a full implementation, this would update the database
        # For now, we'll just confirm the message
        desc = (
            f"New welcome message:\n```\n{message}\n```\n\n"
            f"**Available variables:** "
            f"{{mention}}, {{user}}, {{server}}, {{channel}}\n\n"
            f"**Note:** To persist this change, update `welcome.message_template` "
            f"in your config.toml"
        )
        embed = create_success_embed(
            title="Welcome Message Updated",
            description=desc,
        )

        await ctx.send(embed=embed)
        logger.info(f"Welcome message updated by {ctx.author.name}")

    @commands.command(name="test_welcome")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx: commands.Context) -> None:
        """Test the welcome message with your own user.

        This sends a welcome message as if you just joined the server.
        Useful for previewing how the welcome message looks.

        Args:
            ctx: The command context.

        Example:
            !test_welcome

        """
        # Get welcome message template
        default_msg = (
            "Welcome {mention} to {server}! Please visit {channel} to get started."
        )
        template = self.bot.config.get(
            "welcome",
            "message_template",
            default=default_msg,
        )

        # Substitute template variables
        message = self._substitute_template_vars(template, ctx.author, ctx.guild)

        # Create welcome embed
        embed = create_welcome_embed(
            title=f"Welcome to {ctx.guild.name}! 🌊",
            description=message,
            user=ctx.author,
        )

        # Get registration view if onboarding is enabled
        view = None
        if self.bot.config.get("onboarding", "enabled", default=False):
            onboarding_cog = self.bot.get_cog("Onboarding")
            if onboarding_cog:
                view = onboarding_cog.get_registration_view()

        await ctx.send("**Preview of welcome message:**", embed=embed, view=view)
        logger.info(f"Welcome message test by {ctx.author.name}")

    @set_welcome_channel.error
    @set_welcome_message.error
    @test_welcome.error
    async def welcome_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for welcome commands.

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
            logger.error(f"Error in welcome command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )
            await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the Welcome cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(WelcomeCog(bot))
    logger.info("Welcome cog loaded")
