"""Interest roles system for topic-based channel access.

This cog allows KYC-verified members to select topic interests via a dropdown
menu. Selected interests grant roles that provide access to corresponding
channels.

Features:
    - Multi-select dropdown for interest selection
    - KYC verification required before selecting
    - Role-based channel access (standard Discord pattern)
    - Persistent selector messages across bot restarts
    - Admin commands for management

Example:
    >>> await bot.load_extension('bot.cogs.interest_roles')

"""

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import (
    create_error_embed,
    create_info_embed,
    create_success_embed,
)

if TYPE_CHECKING:
    from bot.cogs.onboarding import OnboardingCog

logger = logging.getLogger(__name__)


class InterestSelect(discord.ui.Select):
    """Multi-select dropdown for choosing topic interests.

    Allows members to select up to 25 interests. Pre-selects interests
    based on the member's current roles.

    Attributes:
        bot: The bot instance.
        cog: The InterestRolesCog instance.

    """

    def __init__(
        self,
        bot: KatoBot,
        cog: "InterestRolesCog",
        options: list[discord.SelectOption],
        current_interests: list[str],
    ) -> None:
        """Initialize the interest select menu.

        Args:
            bot: The bot instance.
            cog: The InterestRolesCog instance.
            options: List of SelectOption objects for the dropdown.
            current_interests: List of interest keys the user currently has.

        """
        # Set default values based on current interests
        for option in options:
            option.default = option.value in current_interests

        super().__init__(
            placeholder="Select your interests...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="interest_roles:select",
        )
        self.bot = bot
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle interest selection changes.

        Calculates the diff between old and new selections, applies role
        changes, and updates the database.

        Args:
            interaction: The interaction from the select menu.

        """
        # Defer immediately to avoid 3-second timeout when processing multiple roles
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        member = interaction.user

        # Get current interests from database
        current_interests = await self.cog._get_member_interests(guild_id, user_id)
        new_interests = set(self.values)

        # Calculate diff
        to_add = new_interests - current_interests
        to_remove = current_interests - new_interests

        # Get interest definitions for role mapping
        interest_defs = await self.cog._get_interest_definitions(guild_id)
        interest_map = {i["interest_key"]: i for i in interest_defs}

        roles_added = []
        roles_removed = []
        errors = []

        # Add new roles
        for interest_key in to_add:
            if interest_key not in interest_map:
                continue
            role_id = interest_map[interest_key]["role_id"]
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Interest role selection")
                    roles_added.append(interest_map[interest_key]["label"])
                except discord.Forbidden:
                    errors.append(f"Cannot assign {role.name} (missing permissions)")
                    logger.error(f"Missing permissions to assign role {role.name}")
            else:
                errors.append(f"Role not found for {interest_key}")
                logger.warning(f"Role {role_id} not found for interest {interest_key}")

        # Remove old roles
        for interest_key in to_remove:
            if interest_key not in interest_map:
                continue
            role_id = interest_map[interest_key]["role_id"]
            role = interaction.guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Interest role deselection")
                    roles_removed.append(interest_map[interest_key]["label"])
                except discord.Forbidden:
                    errors.append(f"Cannot remove {role.name} (missing permissions)")
                    logger.error(f"Missing permissions to remove role {role.name}")

        # Update database
        await self.cog._update_member_interests(guild_id, user_id, new_interests)

        # Build response message
        response_parts = []
        if roles_added:
            response_parts.append(f"**Added:** {', '.join(roles_added)}")
        if roles_removed:
            response_parts.append(f"**Removed:** {', '.join(roles_removed)}")
        if errors:
            response_parts.append(f"**Errors:** {', '.join(errors)}")
        if not roles_added and not roles_removed and not errors:
            response_parts.append("No changes made.")

        description = "\n".join(response_parts)
        if new_interests:
            description += f"\n\n**Your interests:** {len(new_interests)} selected"

        embed = create_success_embed(
            title="Interests Updated",
            description=description,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(
            f"Updated interests for {member.name}: "
            f"added {len(to_add)}, removed {len(to_remove)}"
        )


class InterestSelectView(discord.ui.View):
    """Persistent view containing the interest select menu.

    This view is used for both ephemeral responses and persistent
    selector messages posted by admins.

    Attributes:
        bot: The bot instance.
        cog: The InterestRolesCog instance.

    """

    def __init__(
        self,
        bot: KatoBot,
        cog: "InterestRolesCog",
        options: list[discord.SelectOption] | None = None,
        current_interests: list[str] | None = None,
    ) -> None:
        """Initialize the interest select view.

        Args:
            bot: The bot instance.
            cog: The InterestRolesCog instance.
            options: List of SelectOption objects. If None, view is for
                persistent registration (populated on interaction).
            current_interests: List of interest keys the user currently has.

        """
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.cog = cog

        # Add select menu if options provided (for ephemeral use)
        if options:
            self.add_item(
                InterestSelect(bot, cog, options, current_interests or [])
            )


class PersistentInterestView(discord.ui.View):
    """Persistent view for selector messages with dynamic option loading.

    This view handles interactions on persistent messages by loading
    options dynamically when a user interacts.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the persistent view.

        Args:
            bot: The bot instance.

        """
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Select Interests",
        style=discord.ButtonStyle.primary,
        custom_id="interest_roles:open_selector",
        emoji="🎯",
    )
    async def open_selector(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle button click to open the interest selector.

        Args:
            interaction: The button interaction.
            button: The button that was clicked.

        """
        cog: InterestRolesCog = self.bot.get_cog("InterestRoles")
        if not cog:
            embed = create_error_embed(
                title="System Error",
                description="Interest roles system is not available.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check KYC verification
        is_verified = await cog._verify_member(
            interaction.guild.id, interaction.user.id
        )
        if not is_verified:
            embed = create_error_embed(
                title="Verification Required",
                description=(
                    "You must complete KYC verification before selecting interests.\n\n"
                    "Use `!register` to begin the verification process."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get interest options and current selections
        options = await cog._get_interest_options(interaction.guild.id)
        if not options:
            embed = create_info_embed(
                title="No Interests Available",
                description="No interests are currently configured.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        current_interests = await cog._get_member_interests(
            interaction.guild.id, interaction.user.id
        )

        # Create view with populated options
        view = InterestSelectView(
            self.bot, cog, options, list(current_interests)
        )

        embed = create_info_embed(
            title="Select Your Interests",
            description=(
                "Choose the topics you're interested in. "
                "You'll gain access to channels for your selected interests.\n\n"
                "You can change your selections at any time."
            ),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class InterestRolesCog(commands.Cog, name="InterestRoles"):
    """Cog for managing interest-based role assignments.

    This cog provides a dropdown-based system for members to select
    topic interests. Requires KYC verification before selection.

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the interest roles cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Interest roles cog initialized")

    async def _verify_member(self, guild_id: int, user_id: int) -> bool:
        """Check if a member has completed KYC verification.

        Uses the OnboardingCog's verification check.

        Args:
            guild_id: The guild ID.
            user_id: The user ID.

        Returns:
            True if the member is verified, False otherwise.

        """
        onboarding_cog: OnboardingCog = self.bot.get_cog("Onboarding")
        if not onboarding_cog:
            logger.warning("Onboarding cog not found, cannot verify member")
            return False
        return await onboarding_cog.is_member_verified(guild_id, user_id)

    async def _get_interest_definitions(self, guild_id: int) -> list[dict]:
        """Get all interest definitions for a guild.

        Args:
            guild_id: The guild ID.

        Returns:
            List of interest definition dictionaries.

        """
        rows = await self.bot.db.fetch_all(
            """
            SELECT interest_key, label, description, emoji, role_id, channel_id
            FROM interest_roles
            WHERE guild_id = ?
            ORDER BY display_order, label
            """,
            (guild_id,),
        )
        return [dict(row) for row in rows] if rows else []

    async def _get_interest_options(
        self, guild_id: int
    ) -> list[discord.SelectOption]:
        """Get interest definitions as SelectOption objects.

        Args:
            guild_id: The guild ID.

        Returns:
            List of SelectOption objects for the dropdown.

        """
        interests = await self._get_interest_definitions(guild_id)
        options = []
        for interest in interests:
            label = interest["label"]
            if interest["emoji"]:
                label = f"{interest['emoji']} {label}"
            desc = interest["description"][:100] if interest["description"] else None
            options.append(
                discord.SelectOption(
                    label=label[:100],  # Discord limit
                    value=interest["interest_key"],
                    description=desc,
                )
            )
        return options

    async def _get_member_interests(self, guild_id: int, user_id: int) -> set[str]:
        """Get the interest keys a member has selected.

        Args:
            guild_id: The guild ID.
            user_id: The user ID.

        Returns:
            Set of interest key strings.

        """
        rows = await self.bot.db.fetch_all(
            """
            SELECT interest_key FROM member_interests
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        return {row["interest_key"] for row in rows} if rows else set()

    async def _update_member_interests(
        self, guild_id: int, user_id: int, interests: set[str]
    ) -> None:
        """Update a member's selected interests in the database.

        Replaces all existing selections with the new set.

        Args:
            guild_id: The guild ID.
            user_id: The user ID.
            interests: Set of interest key strings.

        """
        # Ensure guild_config exists
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

        # Delete existing selections
        await self.bot.db.execute(
            "DELETE FROM member_interests WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )

        # Insert new selections
        for interest_key in interests:
            await self.bot.db.execute(
                """
                INSERT INTO member_interests (guild_id, user_id, interest_key)
                VALUES (?, ?, ?)
                """,
                (guild_id, user_id, interest_key),
            )

    async def _sync_interests_from_config(self, guild_id: int) -> int:
        """Sync interest definitions from config.toml to database.

        Args:
            guild_id: The guild ID.

        Returns:
            Number of interests synced.

        """
        interests = self.bot.config.get("interest_roles", "interests", default=[])

        if not interests:
            logger.warning("No interest_roles.interests found in config.toml")
            return 0

        # Ensure guild_config exists
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (guild_id,),
        )

        # Clear existing interests for this guild
        await self.bot.db.execute(
            "DELETE FROM interest_roles WHERE guild_id = ?",
            (guild_id,),
        )

        # Insert interests from config
        for i, interest in enumerate(interests):
            key = interest.get("key")
            label = interest.get("label")
            role_id = interest.get("role_id")
            channel_id = interest.get("channel_id")

            if not all([key, label, role_id, channel_id]):
                logger.warning(f"Incomplete interest config: {interest}")
                continue

            await self.bot.db.execute(
                """
                INSERT INTO interest_roles
                (guild_id, interest_key, label, description, emoji,
                 role_id, channel_id, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    key,
                    label,
                    interest.get("description"),
                    interest.get("emoji"),
                    role_id,
                    channel_id,
                    i,
                ),
            )
            logger.info(f"Synced interest: {label} ({key})")

        return len(interests)

    async def _register_persistent_views(self) -> None:
        """Register persistent views for all selector messages.

        Called on bot startup to re-register button handlers.

        """
        # Register the persistent view for button handling
        self.bot.add_view(PersistentInterestView(self.bot))
        logger.info("Persistent interest view registered")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Sync interests and register persistent views on startup."""
        guild_id = self.bot.config.get("server", "guild_id")
        if guild_id:
            count = await self._sync_interests_from_config(guild_id)
            logger.info(f"Synced {count} interests from config")

        await self._register_persistent_views()

    @commands.command(name="interests")
    async def interests(self, ctx: commands.Context) -> None:
        """Open the interest selection dropdown.

        This command allows verified members to select topic interests.
        Requires KYC verification to be completed first.

        Args:
            ctx: The command context.

        Example:
            !interests

        """
        # Check KYC verification
        is_verified = await self._verify_member(ctx.guild.id, ctx.author.id)
        if not is_verified:
            embed = create_error_embed(
                title="Verification Required",
                description=(
                    "You must complete KYC verification before selecting interests.\n\n"
                    "Use `!register` to begin the verification process."
                ),
            )
            await ctx.send(embed=embed)
            return

        # Get interest options
        options = await self._get_interest_options(ctx.guild.id)
        if not options:
            embed = create_info_embed(
                title="No Interests Available",
                description="No interests are currently configured.",
            )
            await ctx.send(embed=embed)
            return

        # Get current selections
        current_interests = await self._get_member_interests(
            ctx.guild.id, ctx.author.id
        )

        # Create view with options
        view = InterestSelectView(self.bot, self, options, list(current_interests))

        embed = create_info_embed(
            title="Select Your Interests",
            description=(
                "Choose the topics you're interested in. "
                "You'll gain access to channels for your selected interests.\n\n"
                "You can change your selections at any time."
            ),
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name="post_interests")
    @commands.has_permissions(administrator=True)
    async def post_interests(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ) -> None:
        """Post a permanent interest selector in a channel.

        This command requires administrator permissions. Posts a message
        with a button that opens the interest selector.

        Args:
            ctx: The command context.
            channel: The channel to post in (defaults to current channel).

        Example:
            !post_interests #interests

        """
        target_channel = channel or ctx.channel

        # Check that interests are configured
        options = await self._get_interest_options(ctx.guild.id)
        if not options:
            embed = create_error_embed(
                title="No Interests Configured",
                description=(
                    "No interests are currently configured.\n\n"
                    "Add interests to `config.toml` and run `!sync_interests`."
                ),
            )
            await ctx.send(embed=embed)
            return

        # Create the persistent view
        view = PersistentInterestView(self.bot)

        embed = create_info_embed(
            title="Select Your Interests",
            description=(
                "Click the button below to choose your topic interests.\n\n"
                "Selected interests will grant you access to dedicated channels "
                "for those topics. You can change your selections at any time.\n\n"
                "**Note:** KYC verification is required before selecting interests."
            ),
        )

        message = await target_channel.send(embed=embed, view=view)

        # Track the message in database
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (ctx.guild.id,),
        )
        await self.bot.db.execute(
            """
            INSERT INTO interest_selector_messages (guild_id, channel_id, message_id)
            VALUES (?, ?, ?)
            """,
            (ctx.guild.id, target_channel.id, message.id),
        )

        if channel and channel != ctx.channel:
            confirm = create_success_embed(
                title="Interest Selector Posted",
                description=f"Interest selector posted in {channel.mention}.",
            )
            await ctx.send(embed=confirm)

        logger.info(
            f"Posted interest selector in #{target_channel.name} by {ctx.author.name}"
        )

    @commands.command(name="list_interests")
    @commands.has_permissions(administrator=True)
    async def list_interests(self, ctx: commands.Context) -> None:
        """List all configured interests for this server.

        This command requires administrator permissions.

        Args:
            ctx: The command context.

        Example:
            !list_interests

        """
        interests = await self._get_interest_definitions(ctx.guild.id)

        if not interests:
            embed = create_info_embed(
                title="Interests",
                description=(
                    "No interests are configured.\n\n"
                    "Add interests to `config.toml` and run `!sync_interests`."
                ),
            )
            await ctx.send(embed=embed)
            return

        description = "**Configured Interests:**\n\n"
        for interest in interests:
            emoji = interest["emoji"] or ""
            role = ctx.guild.get_role(interest["role_id"])
            role_name = role.mention if role else f"Unknown ({interest['role_id']})"
            key = interest["interest_key"]
            label = interest["label"]
            description += f"{emoji} **{label}** (`{key}`)\n"
            description += f"   Role: {role_name}\n"
            if interest["description"]:
                description += f"   {interest['description']}\n"
            description += "\n"

        embed = create_info_embed(
            title=f"Interests ({len(interests)})",
            description=description,
        )
        await ctx.send(embed=embed)

    @commands.command(name="sync_interests")
    @commands.has_permissions(administrator=True)
    async def sync_interests(self, ctx: commands.Context) -> None:
        """Reload interests from config.toml.

        This command requires administrator permissions. It reloads
        interest definitions from config.toml and updates the database.

        Args:
            ctx: The command context.

        Example:
            !sync_interests

        """
        count = await self._sync_interests_from_config(ctx.guild.id)

        embed = create_success_embed(
            title="Interests Synced",
            description=(
                f"Synced {count} interests from config.toml.\n\n"
                "Use `!list_interests` to view the current configuration."
            ),
        )
        await ctx.send(embed=embed)
        logger.info(f"Interests synced by {ctx.author.name}")

    @commands.command(name="member_interests")
    @commands.has_permissions(administrator=True)
    async def member_interests(
        self, ctx: commands.Context, member: discord.Member
    ) -> None:
        """Show a member's selected interests.

        This command requires administrator permissions.

        Args:
            ctx: The command context.
            member: The member to check.

        Example:
            !member_interests @user

        """
        interests = await self._get_member_interests(ctx.guild.id, member.id)

        if not interests:
            embed = create_info_embed(
                title="Member Interests",
                description=f"{member.mention} has not selected any interests.",
            )
            await ctx.send(embed=embed)
            return

        # Get labels for the interests
        all_interests = await self._get_interest_definitions(ctx.guild.id)
        interest_map = {i["interest_key"]: i for i in all_interests}

        interest_list = []
        for key in interests:
            if key in interest_map:
                emoji = interest_map[key]["emoji"] or ""
                interest_list.append(f"{emoji} {interest_map[key]['label']}")
            else:
                interest_list.append(f"Unknown: {key}")

        embed = create_info_embed(
            title="Member Interests",
            description=(
                f"**{member.mention}'s interests:**\n\n"
                + "\n".join(f"• {i}" for i in interest_list)
            ),
        )
        await ctx.send(embed=embed)

    @interests.error
    @post_interests.error
    @list_interests.error
    @sync_interests.error
    @member_interests.error
    async def interest_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for interest role commands.

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
                description=(
                    f"Missing required argument: `{error.param.name}`\n\n"
                    f"Use `!help {ctx.command.name}` for usage information."
                ),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = create_error_embed(
                title="Member Not Found",
                description="Could not find the specified member.",
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Error in interest role command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )
            await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the InterestRoles cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(InterestRolesCog(bot))
    logger.info("Interest roles cog loaded")
