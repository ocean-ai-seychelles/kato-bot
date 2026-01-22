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

from bot.cogs.onboarding import (
    EMAIL_REGEX,
    KYCModal,
    OnboardingCog,
    RegistrationView,
    is_garbage_input,
    is_sequential,
    is_valid_id_number,
    is_valid_name,
)
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


class TestNameValidation:
    """Test full name validation."""

    def test_valid_names(self) -> None:
        """Test that valid names are accepted."""
        valid_names = [
            "John Doe",
            "Mary Jane Smith",
            "Jean-Pierre Dupont",
            "O'Brien Patrick",
            "Ana Maria Garcia",
        ]
        for name in valid_names:
            is_valid, error = is_valid_name(name)
            assert is_valid, f"'{name}' should be valid but got: {error}"

    def test_single_word_names_rejected(self) -> None:
        """Test that single word names are rejected."""
        is_valid, error = is_valid_name("John")
        assert not is_valid
        assert "first and last name" in error.lower()

    def test_garbage_names_rejected(self) -> None:
        """Test that garbage input is rejected."""
        # These are rejected because each individual word is garbage
        garbage_names = ["test user", "fake name", "none none"]
        for name in garbage_names:
            is_valid, _ = is_valid_name(name)
            assert not is_valid, f"'{name}' should be rejected as garbage"

    def test_names_with_numbers_rejected(self) -> None:
        """Test that names with numbers are rejected."""
        is_valid, _ = is_valid_name("John Doe123")
        assert not is_valid


class TestIDNumberValidation:
    """Test ID number validation."""

    def test_valid_id_numbers(self) -> None:
        """Test that valid ID numbers are accepted."""
        valid_ids = [
            "55667788",  # Non-sequential pattern
            "13579024",  # Mixed non-sequential
            "1029384756",  # Long non-sequential
            "90817263",  # Random-ish pattern
        ]
        for id_num in valid_ids:
            is_valid, error = is_valid_id_number(id_num)
            assert is_valid, f"'{id_num}' should be valid but got: {error}"

    def test_non_digits_rejected(self) -> None:
        """Test that non-digit characters are rejected."""
        invalid_ids = [
            "ABC12345",
            "123-456-789",
            "12345ABC",
            "12 34 56",
        ]
        for id_num in invalid_ids:
            is_valid, error = is_valid_id_number(id_num)
            assert not is_valid, f"'{id_num}' should be rejected"
            assert "digits" in error.lower()

    def test_short_ids_rejected(self) -> None:
        """Test that IDs shorter than 5 digits are rejected."""
        is_valid, error = is_valid_id_number("1234")
        assert not is_valid
        assert "5 digits" in error

    def test_all_same_digit_rejected(self) -> None:
        """Test that IDs with all same digit are rejected."""
        invalid_ids = ["111111", "000000", "999999999"]
        for id_num in invalid_ids:
            is_valid, _ = is_valid_id_number(id_num)
            assert not is_valid, f"'{id_num}' should be rejected"

    def test_sequential_ids_rejected(self) -> None:
        """Test that sequential IDs are rejected."""
        invalid_ids = ["123456", "654321", "12345678", "987654321"]
        for id_num in invalid_ids:
            is_valid, _ = is_valid_id_number(id_num)
            assert not is_valid, f"'{id_num}' should be rejected as sequential"


class TestSequentialDetection:
    """Test the is_sequential helper function."""

    def test_ascending_sequence(self) -> None:
        """Test that ascending sequences are detected."""
        assert is_sequential("12345")
        assert is_sequential("123456789")

    def test_descending_sequence(self) -> None:
        """Test that descending sequences are detected."""
        assert is_sequential("54321")
        assert is_sequential("987654321")

    def test_non_sequential(self) -> None:
        """Test that non-sequential numbers are not flagged."""
        assert not is_sequential("13579")
        assert not is_sequential("24680")
        assert not is_sequential("55667788")


class TestGarbageDetection:
    """Test the is_garbage_input helper function."""

    def test_common_garbage_detected(self) -> None:
        """Test that common garbage inputs are detected."""
        garbage = ["test", "asdf", "fake", "none", "null", "na", "n/a"]
        for g in garbage:
            assert is_garbage_input(g), f"'{g}' should be detected as garbage"

    def test_repeated_chars_detected(self) -> None:
        """Test that repeated character inputs are detected."""
        assert is_garbage_input("aaaa")
        assert is_garbage_input("1111")

    def test_valid_inputs_not_flagged(self) -> None:
        """Test that valid inputs are not flagged."""
        valid = ["John Doe", "Maria Garcia", "New York", "12345678"]
        for v in valid:
            assert not is_garbage_input(v), f"'{v}' should not be flagged as garbage"


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
        assert modal.id_number.min_length == 5

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
