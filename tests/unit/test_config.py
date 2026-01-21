"""Unit tests for configuration loader.

This module tests the Config class in bot.core.config, verifying:
    - TOML file parsing and validation
    - Error handling for missing or malformed files
    - Nested key access via get() method
    - Default value fallbacks
    - Required section validation

These tests use temporary TOML files to avoid dependencies on real config files.

Usage:
    uv run pytest tests/unit/test_config.py -v
"""

from pathlib import Path

import pytest

from bot.core.config import Config


class TestConfigLoader:
    """Test suite for Config class TOML loading and validation."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading a valid TOML configuration file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]
guild_id = 123456789

[channels]
welcome = 111111111
mod_log = 222222222

[roles]
moderator = 333333333
"""
        )

        config = Config(str(config_file))

        assert config.get("server", "guild_id") == 123456789
        assert config.get("channels", "welcome") == 111111111
        assert config.get("roles", "moderator") == 333333333

    def test_missing_config_file_raises_error(self) -> None:
        """Test that FileNotFoundError is raised for missing config file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            Config("nonexistent/config.toml")

        assert "Configuration file not found" in str(exc_info.value)
        assert "nonexistent/config.toml" in str(exc_info.value)

    def test_missing_required_section_raises_error(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when required sections are missing."""
        config_file = tmp_path / "config.toml"
        # Missing 'roles' section
        config_file.write_text(
            """
[server]
guild_id = 123456789

[channels]
welcome = 111111111
"""
        )

        with pytest.raises(ValueError) as exc_info:
            Config(str(config_file))

        assert "missing required sections" in str(exc_info.value)
        assert "roles" in str(exc_info.value)

    def test_nested_key_access(self, tmp_path: Path) -> None:
        """Test accessing nested configuration values."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]
guild_id = 123456789

[channels]
welcome = 111111111

[roles]
moderator = 333333333

[automod.spam]
enabled = true
max_messages = 5
time_window_seconds = 10

[automod.caps]
enabled = false
threshold = 70
"""
        )

        config = Config(str(config_file))

        # Test nested access
        assert config.get("automod", "spam", "enabled") is True
        assert config.get("automod", "spam", "max_messages") == 5
        assert config.get("automod", "caps", "threshold") == 70

    def test_default_value_for_missing_key(self, tmp_path: Path) -> None:
        """Test that default values are returned for missing keys."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]
guild_id = 123456789

[channels]
welcome = 111111111

[roles]
moderator = 333333333
"""
        )

        config = Config(str(config_file))

        # Test default for missing top-level key
        assert config.get("nonexistent", default="fallback") == "fallback"

        # Test default for missing nested key
        assert config.get("server", "nonexistent", default=999) == 999

        # Test default None when not specified
        assert config.get("missing", "deeply", "nested") is None

    def test_malformed_toml_raises_error(self, tmp_path: Path) -> None:
        """Test that malformed TOML files raise an appropriate error."""
        import tomllib

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]
guild_id = "not closed string
"""
        )

        with pytest.raises(tomllib.TOMLDecodeError):
            Config(str(config_file))

    def test_repr_shows_path(self, tmp_path: Path) -> None:
        """Test that __repr__ shows the configuration file path."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]
guild_id = 123456789

[channels]
welcome = 111111111

[roles]
moderator = 333333333
"""
        )

        config = Config(str(config_file))
        repr_str = repr(config)

        assert "Config" in repr_str
        assert str(config_file) in repr_str

    def test_empty_sections_allowed(self, tmp_path: Path) -> None:
        """Test that required sections can be empty."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[server]

[channels]

[roles]
"""
        )

        config = Config(str(config_file))

        # Should not raise ValueError
        assert config.get("server", "anything", default="default") == "default"

    def test_reload_updates_data(self, tmp_path: Path) -> None:
        """Test that reload() updates configuration data."""
        config_path = tmp_path / "test_config.toml"

        # Create initial config
        config_path.write_text("""
[server]
guild_id = 123

[channels]
welcome = 456

[roles]
initial = 789
""")

        config = Config(str(config_path))
        assert config.get("server", "guild_id") == 123

        # Modify the config file
        config_path.write_text("""
[server]
guild_id = 999

[channels]
welcome = 456

[roles]
initial = 789
""")

        # Reload and verify
        config.reload()
        assert config.get("server", "guild_id") == 999

    def test_reload_missing_file_raises_error(self, tmp_path: Path) -> None:
        """Test that reload() raises error if file is deleted."""
        config_path = tmp_path / "test_config.toml"

        # Create initial config
        config_path.write_text("""
[server]
guild_id = 123

[channels]
welcome = 456

[roles]
initial = 789
""")

        config = Config(str(config_path))

        # Delete the file
        config_path.unlink()

        # Reload should raise error
        with pytest.raises(FileNotFoundError):
            config.reload()
