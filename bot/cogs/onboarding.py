"""KYC onboarding system cog for member verification.

This cog handles member onboarding through a Discord modal-based KYC form.
Unverified members have restricted access until they complete registration.

Features:
    - Modal-based KYC form with 5 fields
    - Email format validation
    - Automatic role assignment on verification
    - Admin commands to check verification status
    - Duplicate registration prevention

Example:
    >>> await bot.load_extension('bot.cogs.onboarding')

"""

import logging
import re

import discord
from discord.ext import commands

from bot.core.bot import KatoBot
from bot.utils.embeds import (
    create_error_embed,
    create_info_embed,
    create_success_embed,
)

logger = logging.getLogger(__name__)

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Name validation: letters, spaces, hyphens, apostrophes only
NAME_REGEX = re.compile(r"^[a-zA-Z\s\-']+$")

# Obvious garbage patterns to reject
GARBAGE_PATTERNS = [
    r"^(.)\1+$",  # All same character (aaaa, 1111)
    r"^(abc|xyz|qwerty|asdf|test|fake|none|null|na|n/a|user|name|sample)$",  # Common fakes
]
GARBAGE_REGEXES = [re.compile(p, re.IGNORECASE) for p in GARBAGE_PATTERNS]


def is_garbage_input(value: str) -> bool:
    """Check if input matches common garbage patterns.

    Args:
        value: The input string to check.

    Returns:
        True if the input appears to be garbage, False otherwise.

    """
    cleaned = value.strip()
    for regex in GARBAGE_REGEXES:
        if regex.match(cleaned):
            return True
    return False


def is_valid_name(name: str) -> tuple[bool, str]:
    """Validate a full name.

    Args:
        name: The name to validate.

    Returns:
        Tuple of (is_valid, error_message).

    """
    cleaned = name.strip()

    # Must have at least 2 words (first and last name)
    words = cleaned.split()
    if len(words) < 2:
        return False, "Please enter your full name (first and last name)."

    # Must contain only valid name characters
    if not NAME_REGEX.match(cleaned):
        return False, "Name should only contain letters, spaces, hyphens, and apostrophes."

    # Check for garbage in the full name or individual words
    if is_garbage_input(cleaned):
        return False, "Please enter your real name."

    # Check each word individually for common fake names
    for word in words:
        if is_garbage_input(word):
            return False, "Please enter your real name."

    return True, ""


def is_valid_id_number(id_number: str) -> tuple[bool, str]:
    """Validate an ID number (digits only).

    Args:
        id_number: The ID number to validate.

    Returns:
        Tuple of (is_valid, error_message).

    """
    cleaned = id_number.strip()

    # Must be digits only
    if not cleaned.isdigit():
        return False, "ID number must contain only digits (no letters or dashes)."

    # Must be at least 5 digits
    if len(cleaned) < 5:
        return False, "ID number must be at least 5 digits."

    # Check for all same digit (111111)
    if len(set(cleaned)) == 1:
        return False, "Please enter a valid ID number."

    # Check for sequential digits (123456 or 654321)
    if is_sequential(cleaned):
        return False, "Please enter a valid ID number."

    return True, ""


def is_sequential(digits: str) -> bool:
    """Check if a string of digits is sequential (ascending or descending).

    Args:
        digits: String of digits to check.

    Returns:
        True if sequential, False otherwise.

    """
    if len(digits) < 3:
        return False

    # Check ascending
    ascending = True
    descending = True

    for i in range(1, len(digits)):
        if int(digits[i]) != int(digits[i - 1]) + 1:
            ascending = False
        if int(digits[i]) != int(digits[i - 1]) - 1:
            descending = False

    return ascending or descending


class KYCModal(discord.ui.Modal, title="Member Registration"):
    """Modal form for KYC data collection.

    This modal collects personal information from new members
    as part of the verification process.

    Attributes:
        full_name: Text input for legal full name.
        email: Text input for email address.
        country: Text input for country of residence.
        address: Text input for full address.
        id_number: Text input for national ID or passport number.

    """

    full_name = discord.ui.TextInput(
        label="Full Name",
        placeholder="Enter your legal full name",
        required=True,
        min_length=2,
        max_length=100,
    )

    email = discord.ui.TextInput(
        label="Email Address",
        placeholder="your.email@example.com",
        required=True,
        min_length=5,
        max_length=254,
    )

    country = discord.ui.TextInput(
        label="Country",
        placeholder="Enter your country of residence",
        required=True,
        min_length=2,
        max_length=100,
    )

    address = discord.ui.TextInput(
        label="Address",
        placeholder="Enter your full address",
        required=True,
        min_length=5,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    id_number = discord.ui.TextInput(
        label="ID Number",
        placeholder="National ID or Passport number (digits only)",
        required=True,
        min_length=5,
        max_length=20,
    )

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the KYC modal.

        Args:
            bot: The bot instance.

        """
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle form submission.

        Validates the input, stores in database, and assigns verified role.

        Args:
            interaction: The interaction from the modal submit.

        """
        # Validate email format
        if not EMAIL_REGEX.match(self.email.value):
            embed = create_error_embed(
                title="Invalid Email",
                description="Please enter a valid email address and try again.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate full name
        name_valid, name_error = is_valid_name(self.full_name.value)
        if not name_valid:
            embed = create_error_embed(
                title="Invalid Name",
                description=name_error,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate ID number
        id_valid, id_error = is_valid_id_number(self.id_number.value)
        if not id_valid:
            embed = create_error_embed(
                title="Invalid ID Number",
                description=id_error,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if user is already verified
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )

        if existing:
            embed = create_error_embed(
                title="Already Registered",
                description="You have already completed the registration process.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Ensure guild_config exists (foreign key constraint)
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
            (interaction.guild.id,),
        )

        # Store KYC data
        await self.bot.db.execute(
            """
            INSERT INTO member_profiles
            (guild_id, user_id, discord_username, full_name, email,
             country, address, id_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction.guild.id,
                interaction.user.id,
                str(interaction.user),
                self.full_name.value,
                self.email.value,
                self.country.value,
                self.address.value,
                self.id_number.value,
            ),
        )

        # Assign verified role
        verified_role_id = self.bot.config.get("onboarding", "verified_role_id")
        if verified_role_id:
            role = interaction.guild.get_role(verified_role_id)
            if role:
                try:
                    await interaction.user.add_roles(
                        role, reason="KYC verification completed"
                    )
                    logger.info(
                        f"Assigned verified role to {interaction.user.name} "
                        f"({interaction.user.id})"
                    )
                except discord.Forbidden:
                    logger.error(
                        f"Missing permissions to assign role {role.name} "
                        f"to {interaction.user.name}"
                    )
            else:
                logger.warning(f"Verified role {verified_role_id} not found")

        # Remove unverified role if configured
        unverified_role_id = self.bot.config.get("onboarding", "unverified_role_id")
        if unverified_role_id:
            unverified_role = interaction.guild.get_role(unverified_role_id)
            if unverified_role and unverified_role in interaction.user.roles:
                try:
                    await interaction.user.remove_roles(
                        unverified_role, reason="KYC verification completed"
                    )
                except discord.Forbidden:
                    logger.error(
                        f"Missing permissions to remove unverified role "
                        f"from {interaction.user.name}"
                    )

        # Send confirmation
        embed = create_success_embed(
            title="Registration Complete",
            description=(
                f"Thank you, **{self.full_name.value}**!\n\n"
                "Your registration has been recorded. You now have full access "
                "to the server channels.\n\n"
                "Welcome to the community!"
            ),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        logger.info(
            f"KYC completed for {interaction.user.name} ({interaction.user.id}) "
            f"in guild {interaction.guild.name}"
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Handle errors during form submission.

        Args:
            interaction: The interaction that caused the error.
            error: The exception that was raised.

        """
        logger.error(f"Error in KYC modal submission: {error}")
        embed = create_error_embed(
            title="Registration Error",
            description=(
                "An error occurred while processing your registration. "
                "Please try again later."
            ),
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


class RegistrationView(discord.ui.View):
    """Persistent view containing the registration button.

    This view is sent with the welcome message and allows members
    to open the KYC modal form.

    Attributes:
        bot: The bot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the registration view.

        Args:
            bot: The bot instance.

        """
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot

    @discord.ui.button(
        label="Complete Registration",
        style=discord.ButtonStyle.primary,
        custom_id="onboarding:register",
        emoji="📝",
    )
    async def register_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle registration button click.

        Opens the KYC modal when the button is clicked.

        Args:
            interaction: The button interaction.
            button: The button that was clicked.

        """
        # Check if already verified
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )

        if existing:
            embed = create_info_embed(
                title="Already Registered",
                description="You have already completed the registration process.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Open KYC modal
        modal = KYCModal(self.bot)
        await interaction.response.send_modal(modal)


class GettingStartedView(discord.ui.View):
    """Persistent view for the getting-started channel.

    This view combines registration and interest selection into one
    comprehensive onboarding flow.

    Attributes:
        bot: The bot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the getting started view.

        Args:
            bot: The bot instance.

        """
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot

    @discord.ui.button(
        label="Step 1: Complete Registration",
        style=discord.ButtonStyle.primary,
        custom_id="getting_started:register",
        emoji="📝",
        row=0,
    )
    async def register_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle registration button click.

        Opens the KYC modal when the button is clicked.

        Args:
            interaction: The button interaction.
            button: The button that was clicked.

        """
        # Check if already verified
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )

        if existing:
            embed = create_success_embed(
                title="Already Registered",
                description=(
                    "You've already completed registration!\n\n"
                    "Click **Step 2** below to select your interests and "
                    "unlock topic channels."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Open KYC modal
        modal = KYCModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Step 2: Select Interests",
        style=discord.ButtonStyle.secondary,
        custom_id="getting_started:interests",
        emoji="🎯",
        row=0,
    )
    async def interests_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle interests button click.

        Opens the interest selector for verified members.

        Args:
            interaction: The button interaction.
            button: The button that was clicked.

        """
        # Check if verified first
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )

        if not existing:
            embed = create_error_embed(
                title="Registration Required",
                description=(
                    "Please complete **Step 1** first!\n\n"
                    "Click the **Complete Registration** button to verify "
                    "your membership, then you can select your interests."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get the InterestRoles cog and delegate to it
        interest_cog = self.bot.get_cog("InterestRoles")
        if not interest_cog:
            embed = create_error_embed(
                title="System Error",
                description="Interest roles system is not available.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get interest options and current selections
        options = await interest_cog._get_interest_options(interaction.guild.id)
        if not options:
            embed = create_info_embed(
                title="No Interests Available",
                description="No interests are currently configured.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        current_interests = await interest_cog._get_member_interests(
            interaction.guild.id, interaction.user.id
        )

        # Import here to avoid circular imports
        from bot.cogs.interest_roles import InterestSelectView

        # Create view with populated options
        view = InterestSelectView(
            self.bot, interest_cog, options, list(current_interests)
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


class OnboardingCog(commands.Cog, name="Onboarding"):
    """Cog for handling member onboarding and KYC verification.

    This cog manages the member verification process including:
        - Registration button in welcome messages
        - KYC form processing
        - Admin commands for verification status

    Attributes:
        bot: The KatoBot instance.

    """

    def __init__(self, bot: KatoBot) -> None:
        """Initialize the onboarding cog.

        Args:
            bot: The bot instance.

        """
        self.bot = bot
        logger.info("Onboarding cog initialized")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Register persistent views when bot starts."""
        # Register the persistent views for button handling
        self.bot.add_view(RegistrationView(self.bot))
        self.bot.add_view(GettingStartedView(self.bot))
        logger.info("Onboarding views registered")

    def get_registration_view(self) -> RegistrationView:
        """Get a new registration view instance.

        Returns:
            A RegistrationView instance for attaching to welcome messages.

        """
        return RegistrationView(self.bot)

    async def is_member_verified(self, guild_id: int, user_id: int) -> bool:
        """Check if a member has completed KYC verification.

        Args:
            guild_id: The guild ID.
            user_id: The user ID.

        Returns:
            True if the member is verified, False otherwise.

        """
        result = await self.bot.db.fetch_one(
            "SELECT 1 FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return result is not None

    @commands.command(name="register")
    async def register(self, ctx: commands.Context) -> None:
        """Request the KYC registration form.

        This command allows any user to open the registration form
        if they haven't already completed verification.

        Args:
            ctx: The command context.

        Example:
            !register

        """
        # Check if already verified
        existing = await self.bot.db.fetch_one(
            "SELECT * FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, ctx.author.id),
        )

        if existing:
            embed = create_info_embed(
                title="Already Registered",
                description="You have already completed the registration process.",
            )
            await ctx.send(embed=embed)
            return

        # Send registration button
        embed = create_info_embed(
            title="Member Registration",
            description=(
                "Click the button below to complete your registration.\n\n"
                "You'll need to provide some basic information to verify "
                "your membership."
            ),
        )
        view = RegistrationView(self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="post_registration")
    @commands.has_permissions(administrator=True)
    async def post_registration(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ) -> None:
        """Post a registration button in a channel for existing members.

        This command requires administrator permissions. Posts a message
        with the registration button that any unverified member can use.

        Args:
            ctx: The command context.
            channel: The channel to post in (defaults to current channel).

        Example:
            !post_registration #welcome

        """
        target_channel = channel or ctx.channel

        embed = create_info_embed(
            title="Member Registration",
            description=(
                "Welcome to the server! To gain full access, please complete "
                "your registration by clicking the button below.\n\n"
                "You'll need to provide some basic information to verify "
                "your membership."
            ),
        )
        view = RegistrationView(self.bot)

        await target_channel.send(embed=embed, view=view)

        if channel and channel != ctx.channel:
            confirm = create_success_embed(
                title="Registration Posted",
                description=f"Registration button posted in {channel.mention}.",
            )
            await ctx.send(embed=confirm)

    @commands.command(name="post_getting_started")
    @commands.has_permissions(administrator=True)
    async def post_getting_started(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ) -> None:
        """Post the combined getting-started message with registration and interests.

        This command requires administrator permissions. Posts a comprehensive
        onboarding message with both registration and interest selection buttons.

        Args:
            ctx: The command context.
            channel: The channel to post in (defaults to current channel).

        Example:
            !post_getting_started #getting-started

        """
        target_channel = channel or ctx.channel

        embed = create_info_embed(
            title="Welcome to OCEAN AI!",
            description=(
                "We're excited to have you here! This is a community for AI/ML "
                "enthusiasts to learn, share, and collaborate.\n\n"
                "**To unlock the server, follow these steps:**\n\n"
                "**Step 1: Complete Registration**\n"
                "Click the button below to verify your membership. "
                "This only takes a moment.\n\n"
                "**Step 2: Select Your Interests**\n"
                "After registering, choose the topics you're interested in. "
                "This grants you access to dedicated channels for those topics "
                "(Deep Learning, Computer Vision, NLP, and more).\n\n"
                "*You must complete Step 1 before Step 2.*"
            ),
        )
        view = GettingStartedView(self.bot)

        await target_channel.send(embed=embed, view=view)

        if channel and channel != ctx.channel:
            confirm = create_success_embed(
                title="Getting Started Posted",
                description=f"Getting started message posted in {channel.mention}.",
            )
            await ctx.send(embed=confirm)

        logger.info(
            f"Posted getting-started message in #{target_channel.name} "
            f"by {ctx.author.name}"
        )

    @commands.command(name="kyc_status")
    @commands.has_permissions(administrator=True)
    async def kyc_status(
        self, ctx: commands.Context, member: discord.Member
    ) -> None:
        """Check the KYC verification status of a member.

        This command requires administrator permissions.

        Args:
            ctx: The command context.
            member: The member to check.

        Example:
            !kyc_status @user

        """
        profile = await self.bot.db.fetch_one(
            """
            SELECT full_name, email, country, verified_at
            FROM member_profiles
            WHERE guild_id = ? AND user_id = ?
            """,
            (ctx.guild.id, member.id),
        )

        if not profile:
            embed = create_info_embed(
                title="KYC Status",
                description=f"{member.mention} has **not** completed KYC verification.",
            )
        else:
            embed = create_success_embed(
                title="KYC Status",
                description=(
                    f"{member.mention} is **verified**.\n\n"
                    f"**Name:** {profile['full_name']}\n"
                    f"**Email:** {profile['email']}\n"
                    f"**Country:** {profile['country']}\n"
                    f"**Verified:** {profile['verified_at']}"
                ),
            )

        await ctx.send(embed=embed)

    @commands.command(name="kyc_list")
    @commands.has_permissions(administrator=True)
    async def kyc_list(self, ctx: commands.Context) -> None:
        """List all verified members in the server.

        This command requires administrator permissions.

        Args:
            ctx: The command context.

        Example:
            !kyc_list

        """
        profiles = await self.bot.db.fetch_all(
            """
            SELECT user_id, discord_username, full_name, verified_at
            FROM member_profiles
            WHERE guild_id = ?
            ORDER BY verified_at DESC
            LIMIT 25
            """,
            (ctx.guild.id,),
        )

        if not profiles:
            embed = create_info_embed(
                title="Verified Members",
                description="No members have completed KYC verification yet.",
            )
            await ctx.send(embed=embed)
            return

        # Build member list
        description = "**Verified Members:**\n\n"
        for profile in profiles:
            user = ctx.guild.get_member(profile["user_id"])
            user_mention = user.mention if user else f"Unknown ({profile['user_id']})"
            description += (
                f"• {user_mention} - {profile['full_name']} "
                f"({profile['verified_at'][:10]})\n"
            )

        # Get total count
        count_result = await self.bot.db.fetch_one(
            "SELECT COUNT(*) as count FROM member_profiles WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        total = count_result["count"] if count_result else len(profiles)

        if total > 25:
            description += f"\n*...and {total - 25} more*"

        embed = create_info_embed(
            title=f"Verified Members ({total})",
            description=description,
        )
        await ctx.send(embed=embed)

    @commands.command(name="kyc_delete")
    @commands.has_permissions(administrator=True)
    async def kyc_delete(
        self, ctx: commands.Context, member: discord.Member
    ) -> None:
        """Delete KYC data for a member (allows re-registration).

        This command requires administrator permissions.

        Args:
            ctx: The command context.
            member: The member whose KYC data to delete.

        Example:
            !kyc_delete @user

        """
        result = await self.bot.db.execute(
            "DELETE FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )

        if result.rowcount > 0:
            # Remove verified role if configured
            verified_role_id = self.bot.config.get("onboarding", "verified_role_id")
            if verified_role_id:
                role = ctx.guild.get_role(verified_role_id)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(
                            role, reason="KYC data deleted by admin"
                        )
                    except discord.Forbidden:
                        pass

            embed = create_success_embed(
                title="KYC Data Deleted",
                description=(
                    f"KYC data for {member.mention} has been deleted.\n"
                    "They can now re-register."
                ),
            )
        else:
            embed = create_error_embed(
                title="No Data Found",
                description=f"No KYC data found for {member.mention}.",
            )

        await ctx.send(embed=embed)
        logger.info(f"KYC data deleted for {member.name} by {ctx.author.name}")

    @commands.command(name="kyc_delete_id")
    @commands.has_permissions(administrator=True)
    async def kyc_delete_id(
        self, ctx: commands.Context, user_id: int
    ) -> None:
        """Delete KYC data by user ID (for users who left the server).

        This command requires administrator permissions. Use this when
        a member has left the server and you need to remove their data.

        Args:
            ctx: The command context.
            user_id: The Discord user ID to delete.

        Example:
            !kyc_delete_id 123456789012345678

        """
        # First check if there's data to delete
        profile = await self.bot.db.fetch_one(
            """
            SELECT discord_username, full_name
            FROM member_profiles
            WHERE guild_id = ? AND user_id = ?
            """,
            (ctx.guild.id, user_id),
        )

        if not profile:
            embed = create_error_embed(
                title="No Data Found",
                description=f"No KYC data found for user ID `{user_id}`.",
            )
            await ctx.send(embed=embed)
            return

        # Delete the data
        await self.bot.db.execute(
            "DELETE FROM member_profiles WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, user_id),
        )

        # Also delete any interest selections
        await self.bot.db.execute(
            "DELETE FROM member_interests WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, user_id),
        )

        embed = create_success_embed(
            title="KYC Data Deleted",
            description=(
                f"KYC data deleted for:\n"
                f"**User ID:** `{user_id}`\n"
                f"**Username:** {profile['discord_username']}\n"
                f"**Name:** {profile['full_name']}"
            ),
        )
        await ctx.send(embed=embed)
        logger.info(f"KYC data deleted for user ID {user_id} by {ctx.author.name}")

    @commands.command(name="kyc_cleanup")
    @commands.has_permissions(administrator=True)
    async def kyc_cleanup(
        self, ctx: commands.Context, confirm: str = None
    ) -> None:
        """Find and remove KYC data for users who left the server.

        This command requires administrator permissions. Run without
        arguments to see a list of orphaned records. Run with 'confirm'
        to actually delete them.

        Args:
            ctx: The command context.
            confirm: Pass 'confirm' to actually delete the records.

        Example:
            !kyc_cleanup          # List orphaned records
            !kyc_cleanup confirm  # Delete orphaned records

        """
        # Get all KYC records for this guild
        profiles = await self.bot.db.fetch_all(
            """
            SELECT user_id, discord_username, full_name, verified_at
            FROM member_profiles
            WHERE guild_id = ?
            """,
            (ctx.guild.id,),
        )

        if not profiles:
            embed = create_info_embed(
                title="KYC Cleanup",
                description="No KYC records found in this server.",
            )
            await ctx.send(embed=embed)
            return

        # Find users no longer in the guild
        orphaned = []
        for profile in profiles:
            member = ctx.guild.get_member(profile["user_id"])
            if member is None:
                orphaned.append(profile)

        if not orphaned:
            embed = create_success_embed(
                title="KYC Cleanup",
                description=(
                    f"All {len(profiles)} KYC records belong to current members.\n"
                    "No cleanup needed."
                ),
            )
            await ctx.send(embed=embed)
            return

        if confirm and confirm.lower() == "confirm":
            # Delete orphaned records
            for profile in orphaned:
                await self.bot.db.execute(
                    "DELETE FROM member_profiles WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, profile["user_id"]),
                )
                await self.bot.db.execute(
                    "DELETE FROM member_interests WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, profile["user_id"]),
                )

            embed = create_success_embed(
                title="KYC Cleanup Complete",
                description=f"Deleted {len(orphaned)} orphaned KYC records.",
            )
            await ctx.send(embed=embed)
            logger.info(
                f"KYC cleanup: deleted {len(orphaned)} records by {ctx.author.name}"
            )
        else:
            # Show preview
            description = f"**Found {len(orphaned)} orphaned records:**\n\n"
            for profile in orphaned[:10]:
                description += (
                    f"- `{profile['user_id']}` - {profile['discord_username']} "
                    f"({profile['full_name']})\n"
                )
            if len(orphaned) > 10:
                description += f"\n*...and {len(orphaned) - 10} more*"

            description += (
                f"\n\nRun `!kyc_cleanup confirm` to delete these records."
            )

            embed = create_info_embed(
                title="KYC Cleanup Preview",
                description=description,
            )
            await ctx.send(embed=embed)

    @post_getting_started.error
    @kyc_delete_id.error
    @kyc_cleanup.error
    @kyc_status.error
    @kyc_list.error
    @kyc_delete.error
    async def onboarding_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Error handler for onboarding commands.

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
        elif isinstance(error, commands.MemberNotFound):
            embed = create_error_embed(
                title="Member Not Found",
                description="Could not find the specified member.",
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Error in onboarding command: {error}")
            embed = create_error_embed(
                title="Command Error",
                description="An error occurred while executing this command.",
                error_details=str(error),
            )
            await ctx.send(embed=embed)


async def setup(bot: KatoBot) -> None:
    """Load the Onboarding cog.

    This function is called by discord.py when loading the extension.

    Args:
        bot: The bot instance.

    """
    await bot.add_cog(OnboardingCog(bot))
    logger.info("Onboarding cog loaded")
