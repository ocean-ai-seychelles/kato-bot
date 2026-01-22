"""Configuration loader for Kato bot.

This module provides a configuration loader that reads TOML files and validates
server-specific settings. It supports nested key access and provides sensible
defaults for optional configuration values.

The configuration system is designed to:
    - Keep secrets separate from code (TOML files are not committed for production)
    - Validate required configuration on startup
    - Provide type-safe access to configuration values
    - Support nested configuration structures

Example:
    >>> from bot.core.config import Config
    >>> config = Config("assets/config.toml")
    >>> guild_id = config.get("server", "guild_id")
    >>> spam_enabled = config.get("automod", "spam", "enabled", default=False)

"""

import tomllib
from pathlib import Path
from typing import Any


class Config:
    """Configuration container for bot settings loaded from TOML files.

    This class loads and validates configuration from TOML files, providing
    nested key access and validation of required configuration sections.

    Attributes:
        data: The loaded configuration dictionary from the TOML file.
        path: Path to the configuration file that was loaded.

    Example:
        >>> config = Config("assets/config.toml")
        >>> guild_id = config.get("server", "guild_id")
        >>> welcome_enabled = config.get("welcome", "enabled", default=True)

    """

    def __init__(self, config_path: str = "assets/config.toml") -> None:
        """Load configuration from TOML file and validate required sections.

        Args:
            config_path: Path to the TOML configuration file. Defaults to
                "assets/config.toml".

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If the configuration is missing required sections.
            tomllib.TOMLDecodeError: If the TOML file is malformed.

        """
        self.path = Path(config_path)

        if not self.path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please create a config.toml file with your server settings."
            )

        with open(self.path, "rb") as f:
            self.data = tomllib.load(f)

        self._validate()

    def _validate(self) -> None:
        """Validate that required configuration sections are present.

        Raises:
            ValueError: If any required configuration section is missing.

        """
        required_sections = ["server", "channels", "roles"]

        missing_sections = [
            section for section in required_sections if section not in self.data
        ]

        if missing_sections:
            raise ValueError(
                f"Configuration is missing required sections: "
                f"{', '.join(missing_sections)}\n"
                f"Please ensure your config.toml contains all required sections."
            )

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a configuration value using nested keys.

        This method allows accessing nested configuration values using a
        sequence of keys. If any key in the path doesn't exist, the default
        value is returned.

        Args:
            *keys: Variable number of keys to traverse in the configuration.
                For example, get("automod", "spam", "enabled") accesses
                config["automod"]["spam"]["enabled"].
            default: Value to return if the key path doesn't exist. Defaults
                to None.

        Returns:
            The configuration value at the specified key path, or the default
            value if the path doesn't exist.

        Example:
            >>> config = Config("assets/config.toml")
            >>> # Get a nested value
            >>> threshold = config.get("automod", "spam", "threshold", default=5)
            >>> # Get a top-level value
            >>> guild_id = config.get("server", "guild_id")

        """
        value = self.data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def reload(self) -> None:
        """Reload configuration from the TOML file.

        This method re-reads the configuration file and updates the
        internal data dictionary. Useful for picking up configuration
        changes without restarting the bot.

        Raises:
            FileNotFoundError: If the configuration file no longer exists.
            ValueError: If the configuration is missing required sections.
            tomllib.TOMLDecodeError: If the TOML file is malformed.

        Example:
            >>> config = Config("assets/config.toml")
            >>> # Make changes to config.toml externally
            >>> config.reload()  # Pick up the changes

        """
        if not self.path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.path}\n"
                f"Cannot reload non-existent configuration."
            )

        with open(self.path, "rb") as f:
            self.data = tomllib.load(f)

        self._validate()

    def __repr__(self) -> str:
        """Return a string representation of the Config object.

        Returns:
            String showing the configuration file path.

        """
        return f"Config(path={self.path})"
