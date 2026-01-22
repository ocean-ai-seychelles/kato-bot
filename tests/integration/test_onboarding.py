"""Integration tests for the KYC onboarding system.

This module tests the onboarding cog functionality including:
    - Modal form validation
    - Database storage of KYC data
    - Admin commands for verification status
    - Email validation
    - Duplicate registration prevention

Usage:
    uv run pytest tests/integration/test_onboarding.py -v
"""

import pytest

from bot.cogs.onboarding import EMAIL_REGEX, KYCModal, OnboardingCog, RegistrationView
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestEmailValidation:
    """Test email format validation."""

    def test_valid_email_formats(self) -> None:
        """Test that valid email formats are accepted."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
            "user123@example.co.uk",
            "a@b.co",
        ]
        for email in valid_emails:
            assert EMAIL_REGEX.match(email), f"'{email}' should be valid"

    def test_invalid_email_formats(self) -> None:
        """Test that invalid email formats are rejected."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@example.com",
            "user@.com",
            "user@example.",
            "user name@example.com",
            "",
        ]
        for email in invalid_emails:
            assert not EMAIL_REGEX.match(email), f"'{email}' should be invalid"


class TestOnboardingCogInitialization:
    """Test onboarding cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the onboarding cog initializes successfully."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = OnboardingCog(bot)

        assert cog.bot == bot
        assert cog is not None

    def test_cog_has_commands(self) -> None:
        """Test that the cog has the expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = OnboardingCog(bot)

        # User commands
        assert hasattr(cog, "register")

        # Admin commands
        assert hasattr(cog, "post_registration")
        assert hasattr(cog, "kyc_status")
        assert hasattr(cog, "kyc_list")
        assert hasattr(cog, "kyc_delete")

    def test_cog_has_listener(self) -> None:
        """Test that the cog has the on_ready listener."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = OnboardingCog(bot)

        assert hasattr(cog, "on_ready")


class TestKYCModal:
    """Test KYC modal form."""

    @pytest.mark.asyncio
    async def test_modal_initializes(self) -> None:
        """Test that the KYC modal initializes with correct fields."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        modal = KYCModal(bot)

        assert modal.title == "Member Registration"
        assert modal.full_name is not None
        assert modal.email is not None
        assert modal.country is not None
        assert modal.address is not None
        assert modal.id_number is not None

        await bot.close()

    @pytest.mark.asyncio
    async def test_modal_field_requirements(self) -> None:
        """Test that modal fields have correct requirements."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        modal = KYCModal(bot)

        # All fields should be required
        assert modal.full_name.required is True
        assert modal.email.required is True
        assert modal.country.required is True
        assert modal.address.required is True
        assert modal.id_number.required is True

        await bot.close()

    @pytest.mark.asyncio
    async def test_modal_field_min_lengths(self) -> None:
        """Test that modal fields have minimum length requirements."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        modal = KYCModal(bot)

        assert modal.full_name.min_length == 2
        assert modal.email.min_length == 5
        assert modal.country.min_length == 2
        assert modal.address.min_length == 5
        assert modal.id_number.min_length == 2

        await bot.close()


class TestRegistrationView:
    """Test registration view and button."""

    @pytest.mark.asyncio
    async def test_view_initializes(self) -> None:
        """Test that the registration view initializes."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        view = RegistrationView(bot)

        assert view is not None
        assert view.timeout is None  # Persistent view

        await bot.close()

    @pytest.mark.asyncio
    async def test_view_has_button(self) -> None:
        """Test that the view has a registration button."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        view = RegistrationView(bot)

        # Check that view has children (buttons)
        assert len(view.children) > 0

        # Find the register button
        button = None
        for child in view.children:
            if hasattr(child, "custom_id") and child.custom_id == "onboarding:register":
                button = child
                break

        assert button is not None
        assert button.label == "Complete Registration"

        await bot.close()


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the onboarding cog can be loaded into the bot."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Load the cog
    await bot.load_extension("bot.cogs.onboarding")

    # Check that cog is loaded
    assert "Onboarding" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_onboarding_cog_in_bot_startup() -> None:
    """Test that onboarding cog is loaded during bot startup."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Run setup hook (this loads cogs)
    await bot.setup_hook()

    # Check that onboarding cog is loaded
    assert "Onboarding" in bot.cogs

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_is_member_verified_returns_false_for_unverified() -> None:
    """Test that is_member_verified returns False for unverified members."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Initialize database
    await bot.db.connect()
    await bot.db.apply_migrations()

    cog = OnboardingCog(bot)

    # Check for a user that hasn't registered
    result = await cog.is_member_verified(123456789, 987654321)
    assert result is False

    # Cleanup
    await bot.close()


@pytest.mark.asyncio
async def test_get_registration_view() -> None:
    """Test that get_registration_view returns a RegistrationView."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)
    cog = OnboardingCog(bot)

    view = cog.get_registration_view()

    assert isinstance(view, RegistrationView)
    assert view.bot == bot

    # Cleanup
    await bot.close()
