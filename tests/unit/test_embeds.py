"""Unit tests for embed utility functions.

This module tests the embed factory functions in bot/utils/embeds.py.

Usage:
    uv run pytest tests/unit/test_embeds.py -v

"""

import discord

from bot.utils.embeds import (
    create_error_embed,
    create_info_embed,
    create_success_embed,
    create_welcome_embed,
)


class TestCreateWelcomeEmbed:
    """Tests for create_welcome_embed function."""

    def test_basic_welcome_embed(self) -> None:
        """Test creating a basic welcome embed."""
        embed = create_welcome_embed(
            title="Welcome!",
            description="Welcome to our server",
        )

        assert embed.title == "Welcome!"
        assert embed.description == "Welcome to our server"
        assert embed.color == discord.Color.blue()

    def test_welcome_embed_with_thumbnail_url(self) -> None:
        """Test welcome embed with custom thumbnail URL."""
        embed = create_welcome_embed(
            title="Welcome!",
            description="Welcome to our server",
            thumbnail_url="https://example.com/image.png",
        )

        assert embed.thumbnail.url == "https://example.com/image.png"

    def test_welcome_embed_with_user_avatar(self) -> None:
        """Test welcome embed uses user avatar when provided."""
        from unittest.mock import MagicMock

        user = MagicMock()
        user.name = "TestUser"
        user.avatar.url = "https://cdn.discord.com/avatar.png"

        embed = create_welcome_embed(
            title="Welcome!",
            description="Welcome to our server",
            user=user,
        )

        assert embed.thumbnail.url == "https://cdn.discord.com/avatar.png"
        assert embed.footer.text == "Welcome TestUser!"
        assert embed.footer.icon_url == "https://cdn.discord.com/avatar.png"

    def test_welcome_embed_with_user_no_avatar(self) -> None:
        """Test welcome embed handles user without avatar."""
        from unittest.mock import MagicMock

        user = MagicMock()
        user.name = "TestUser"
        user.avatar = None

        embed = create_welcome_embed(
            title="Welcome!",
            description="Welcome to our server",
            user=user,
        )

        # Should not set thumbnail when user has no avatar
        assert embed.thumbnail.url is None
        assert embed.footer.text == "Welcome TestUser!"
        assert embed.footer.icon_url is None

    def test_welcome_embed_thumbnail_url_overrides_user_avatar(self) -> None:
        """Test that thumbnail_url parameter overrides user avatar."""
        from unittest.mock import MagicMock

        user = MagicMock()
        user.name = "TestUser"
        user.avatar.url = "https://cdn.discord.com/avatar.png"

        embed = create_welcome_embed(
            title="Welcome!",
            description="Welcome to our server",
            user=user,
            thumbnail_url="https://example.com/custom.png",
        )

        # Custom thumbnail_url should take precedence
        assert embed.thumbnail.url == "https://example.com/custom.png"


class TestCreateSuccessEmbed:
    """Tests for create_success_embed function."""

    def test_success_embed_has_checkmark(self) -> None:
        """Test that success embed title has checkmark prefix."""
        embed = create_success_embed(
            title="Action Complete",
            description="The action was successful",
        )

        assert embed.title == "✓ Action Complete"
        assert embed.description == "The action was successful"
        assert embed.color == discord.Color.green()

    def test_success_embed_color(self) -> None:
        """Test that success embed is green."""
        embed = create_success_embed(
            title="Test",
            description="Test",
        )

        assert embed.color == discord.Color.green()


class TestCreateErrorEmbed:
    """Tests for create_error_embed function."""

    def test_error_embed_has_x_prefix(self) -> None:
        """Test that error embed title has X prefix."""
        embed = create_error_embed(
            title="Error Occurred",
            description="Something went wrong",
        )

        assert embed.title == "✗ Error Occurred"
        assert embed.description == "Something went wrong"
        assert embed.color == discord.Color.red()

    def test_error_embed_with_details(self) -> None:
        """Test error embed with error details field."""
        embed = create_error_embed(
            title="Error",
            description="An error occurred",
            error_details="Stack trace here",
        )

        # Check that there's a field with the details
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Details"
        assert embed.fields[0].value == "Stack trace here"

    def test_error_embed_without_details(self) -> None:
        """Test error embed without error details."""
        embed = create_error_embed(
            title="Error",
            description="An error occurred",
        )

        assert len(embed.fields) == 0


class TestCreateInfoEmbed:
    """Tests for create_info_embed function."""

    def test_info_embed_has_info_icon(self) -> None:
        """Test that info embed title has info icon prefix."""
        embed = create_info_embed(
            title="Information",
            description="Here is some information",
        )

        assert embed.title == "ℹ️ Information"
        assert embed.description == "Here is some information"
        assert embed.color == discord.Color.blue()

    def test_info_embed_color(self) -> None:
        """Test that info embed is blue."""
        embed = create_info_embed(
            title="Test",
            description="Test",
        )

        assert embed.color == discord.Color.blue()
