"""Integration tests for the Code of Conduct cog.

This module tests the CoC cog functionality, verifying that:
    - The cog initializes correctly
    - The embed builder produces valid Discord embeds
    - All rules are included in the embed
    - The cog loads successfully into the bot

Usage:
    uv run pytest tests/integration/test_coc.py -v
"""

import pytest

from bot.cogs.coc import COC_RULES, CoCCog
from bot.core.bot import KatoBot
from bot.core.config import Config


class TestCoCEmbedBuilder:
    """Test the CoC embed builder."""

    def test_build_coc_embed_returns_embed(self) -> None:
        """Test that _build_coc_embed returns a Discord embed."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        assert embed is not None
        assert embed.title == "OCEAN AI Community Code of Conduct"
        assert embed.description is not None
        assert len(embed.description) > 0

    def test_build_coc_embed_has_all_rules(self) -> None:
        """Test that the embed contains all CoC rules."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        # Should have 10 fields (9 rules + moderators section)
        assert len(embed.fields) == 10
        assert len(embed.fields) == len(COC_RULES)

    def test_build_coc_embed_field_names(self) -> None:
        """Test that embed fields have the expected names."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        expected_names = [
            "1. Respect and Inclusivity",
            "2. Embrace All Learning Levels",
            "3. Cultural Sensitivity",
            "4. Accuracy and Misinformation",
            "5. Productive Disagreement",
            "6. Privacy and Safety",
            "7. No Spam or Self-promotion",
            "8. Inappropriate Content",
            "9. Keep it Professional",
            "Moderators and Enforcement",
        ]

        for i, field in enumerate(embed.fields):
            assert field.name == expected_names[i]

    def test_build_coc_embed_within_discord_limits(self) -> None:
        """Test that the embed is within Discord's character limits."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        # Discord limits:
        # - Title: 256 characters
        # - Description: 4096 characters
        # - Field name: 256 characters
        # - Field value: 1024 characters
        # - Total embed: 6000 characters

        assert len(embed.title) <= 256
        assert len(embed.description) <= 4096

        total_length = len(embed.title) + len(embed.description)

        for field in embed.fields:
            assert len(field.name) <= 256
            assert len(field.value) <= 1024
            total_length += len(field.name) + len(field.value)

        if embed.footer and embed.footer.text:
            total_length += len(embed.footer.text)

        assert total_length <= 6000

    def test_build_coc_embed_has_footer(self) -> None:
        """Test that the embed has a footer."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        assert embed.footer is not None
        assert embed.footer.text == "Questions or Concerns? Ask an admin"

    def test_build_coc_embed_fields_not_inline(self) -> None:
        """Test that all embed fields are not inline for readability."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        embed = cog._build_coc_embed()

        for field in embed.fields:
            assert field.inline is False


class TestCoCCogInitialization:
    """Test CoC cog initialization."""

    def test_cog_initializes(self) -> None:
        """Test that the CoC cog initializes successfully."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        assert cog.bot == bot
        assert cog is not None

    def test_cog_has_commands(self) -> None:
        """Test that the cog has the expected commands."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        assert hasattr(cog, "post_coc")
        assert hasattr(cog, "preview_coc")

    def test_cog_name(self) -> None:
        """Test that the cog has the correct name."""
        config = Config("assets/config.toml")
        bot = KatoBot(config)
        cog = CoCCog(bot)

        assert cog.qualified_name == "CoC"


@pytest.mark.asyncio
async def test_cog_loads_successfully() -> None:
    """Test that the CoC cog can be loaded into the bot."""
    config = Config("assets/config.toml")
    bot = KatoBot(config)

    # Load the cog
    await bot.load_extension("bot.cogs.coc")

    # Check that cog is loaded
    assert "CoC" in bot.cogs

    # Cleanup
    await bot.close()
