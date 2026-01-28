"""Code of Conduct cog for posting community rules.

This cog provides admin commands to post and manage the community Code of Conduct
as a formatted embed in a dedicated channel.

Features:
    - Post CoC embed to a configured channel
    - Edit existing CoC message instead of duplicating
    - Preview CoC embed before posting
    - Configurable via config.toml

Example:
    >>> await bot.load_extension('bot.cogs.coc')

"""

import logging

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import create_error_embed, create_success_embed

logger = logging.getLogger(__name__)

# Code of Conduct content - extracted from community_cod.md
COC_RULES = [
    {
        "name": "1. Respect and Inclusivity",
        "value": (
            "Treat all members with kindness and dignity. We have zero tolerance "
            "for harassment, hate speech, discrimination, or slurs based on race, "
            "ethnicity, nationality, religion, gender, sexual orientation, "
            "disability, or any other characteristic."
        ),
    },
    {
        "name": "2. Embrace All Learning Levels",
        "value": (
            'Never dismiss someone\'s question as "too basic" or mock someone '
            "for not knowing something. If you know the answer, share it "
            "generously. If you're asking the question, ask boldly."
        ),
    },
    {
        "name": "3. Cultural Sensitivity",
        "value": (
            "Be mindful of our diverse backgrounds and perspectives. Avoid "
            "stereotypes and assumptions about others' cultures or experiences."
        ),
    },
    {
        "name": "4. Accuracy and Misinformation",
        "value": (
            "When sharing information, cite sources when possible and acknowledge "
            "uncertainty when appropriate. If you spot incorrect information, "
            "offer gentle, educational corrections. We're all learning together."
        ),
    },
    {
        "name": "5. Productive Disagreement",
        "value": (
            "Healthy debate is welcome but always remain respectful. If conflicts "
            "arise, try to resolve them directly and respectfully, or involve a "
            "moderator if needed."
        ),
    },
    {
        "name": "6. Privacy and Safety",
        "value": (
            "Don't share others' personal information without consent. Be "
            "thoughtful about what you share about yourself. Report any "
            "concerning behaviour to moderators."
        ),
    },
    {
        "name": "7. No Spam or Self-promotion",
        "value": (
            "Relevant resources are always welcome, but excessive self-promotion, "
            "advertising, or spam will be removed. When in doubt, ask a "
            "moderator first."
        ),
    },
    {
        "name": "8. Inappropriate Content",
        "value": (
            "Do not share, post, or link to:\n"
            "• Sexually explicit content, pornography, or sexual imagery\n"
            "• Graphic violence or gore\n"
            "• Content glorifying self-harm, substance abuse, or danger\n"
            "• Illegal content or instructions for illegal activities\n"
            "• Content designed to shock, disturb, or harass others\n\n"
            "This applies to text, images, videos, links, and profiles."
        ),
    },
    {
        "name": "9. Keep it Professional",
        "value": (
            "While we encourage friendly connections, keep conversations "
            "appropriate for a diverse, public educational space. Flirting, "
            "romantic advances, or overly personal conversations should be taken "
            "to private messages (and always respect boundaries)."
        ),
    },
    {
        "name": "Moderators and Enforcement",
        "value": (
            'We use "Kato" an AI assistant built by our team, to monitor chats '
            "and detect potential rule violations. We've built a keyword detection "
            "tool into Kato to be able to flag and warn violators of the code of "
            "conduct.\n\n"
            "**Consequences:** First-time violations typically result in a warning. "
            "Repeated or severe violations may lead to temporary bans or permanent "
            "removal from the community depending on severity."
        ),
    },
]


class CoCCog(commands.Cog, name="CoC"):
    """Cog for managing the community Code of Conduct.

    This cog provides commands to post and manage the Code of Conduct
    embed in a dedicated channel.

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the CoC cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("CoC cog initialized")

    def _build_coc_embed(self) -> discord.Embed:
        """Build the Code of Conduct embed.

        Returns:
            A formatted Discord embed containing all CoC rules.

        """
        embed = discord.Embed(
            title="OCEAN AI Community Code of Conduct",
            description=(
                "Welcome to the OCEAN AI Discord Community! "
                "Please read and follow our community rules to help maintain "
                "a welcoming and productive environment for everyone."
            ),
            color=discord.Color.blue(),
        )

        for rule in COC_RULES:
            embed.add_field(name=rule["name"], value=rule["value"], inline=False)

        embed.set_footer(text="Questions or Concerns? Ask an admin")

        return embed

    @commands.command(name="post_coc")
    @commands.has_permissions(administrator=True)
    async def post_coc(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """Post the Code of Conduct to a channel.

        If no channel is specified, uses the configured coc.channel_id.
        If a coc.message_id exists, edits the existing message instead of
        posting a duplicate.

        Args:
            ctx: The command context.
            channel: Optional target channel. Uses config if not specified.

        Example:
            !post_coc #rules

        """
        # Determine target channel
        if channel is None:
            channel_id = self.bot.config.get("coc", "channel_id", default=0)
            if not channel_id:
                embed = create_error_embed(
                    title="No Channel Specified",
                    description=(
                        "Please specify a channel or configure `coc.channel_id` "
                        "in config.toml."
                    ),
                )
                await ctx.send(embed=embed)
                return
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                embed = create_error_embed(
                    title="Channel Not Found",
                    description=f"Could not find channel with ID {channel_id}.",
                )
                await ctx.send(embed=embed)
                return

        # Build the embed
        coc_embed = self._build_coc_embed()

        # Check if we should edit an existing message
        message_id = self.bot.config.get("coc", "message_id", default=0)
        if message_id:
            try:
                existing_message = await channel.fetch_message(message_id)
                await existing_message.edit(embed=coc_embed)
                embed = create_success_embed(
                    title="Code of Conduct Updated",
                    description=f"Updated the CoC message in {channel.mention}.",
                )
                await ctx.send(embed=embed)
                logger.info(
                    f"CoC message updated in {channel.name} by {ctx.author.name}"
                )
                return
            except discord.NotFound:
                logger.info("Configured message_id not found, posting new message")
            except discord.Forbidden:
                embed = create_error_embed(
                    title="Permission Denied",
                    description=f"Cannot edit message in {channel.mention}.",
                )
                await ctx.send(embed=embed)
                return

        # Post new message
        try:
            message = await channel.send(embed=coc_embed)
            embed = create_success_embed(
                title="Code of Conduct Posted",
                description=(
                    f"Posted CoC to {channel.mention}.\n\n"
                    f"**Note:** To enable editing instead of reposting, update "
                    f"`coc.message_id` in config.toml to `{message.id}`"
                ),
            )
            await ctx.send(embed=embed)
            logger.info(
                f"CoC message posted to {channel.name} (ID: {message.id}) "
                f"by {ctx.author.name}"
            )
        except discord.Forbidden:
            embed = create_error_embed(
                title="Permission Denied",
                description=f"Cannot send messages to {channel.mention}.",
            )
            await ctx.send(embed=embed)

    @commands.command(name="preview_coc")
    @commands.has_permissions(administrator=True)
    async def preview_coc(self, ctx: commands.Context) -> None:
        """Preview the Code of Conduct embed in the current channel.

        This sends the CoC embed to the current channel for preview purposes.
        Useful for checking the formatting before posting to the rules channel.

        Args:
            ctx: The command context.

        Example:
            !preview_coc

        """
        coc_embed = self._build_coc_embed()
        await ctx.send("**Preview of Code of Conduct:**", embed=coc_embed)
        logger.info(f"CoC preview requested by {ctx.author.name}")

    @post_coc.error
    @preview_coc.error
    async def coc_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for CoC commands.

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
        elif isinstance(error, commands.ChannelNotFound):
            embed = create_error_embed(
                title="Channel Not Found",
                description="Could not find the specified channel.",
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BadArgument):
            embed = create_error_embed(
                title="Invalid Argument",
                description=f"Invalid argument provided.\n\n"
                f"Use `!help {ctx.command.name}` for usage information.",
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Error in CoC command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )
            await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the CoC cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(CoCCog(bot))
    logger.info("CoC cog loaded")
