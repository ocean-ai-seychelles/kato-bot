"""Reusable embed templates for consistent bot messaging.

This module provides pre-styled embed templates for different message types:
    - Welcome messages (friendly, inviting)
    - Success messages (confirmations, completions)
    - Error messages (warnings, failures)
    - Info messages (neutral information)

All embeds use consistent color schemes and formatting for a polished look.

Example:
    >>> from bot.utils.embeds import create_welcome_embed
    >>> embed = create_welcome_embed(
    ...     title="Welcome!",
    ...     description="Welcome to our server",
    ...     user=member
    ... )
    >>> await channel.send(embed=embed)

"""

import discord


def create_welcome_embed(
    title: str,
    description: str,
    user: discord.Member | None = None,
    thumbnail_url: str | None = None,
) -> discord.Embed:
    """Create a welcoming embed with consistent styling.

    Args:
        title: The embed title (bold, prominent).
        description: The main message content.
        user: Optional member to set as thumbnail and footer.
        thumbnail_url: Optional custom thumbnail URL (overrides user avatar).

    Returns:
        A styled Discord embed ready to send.

    Example:
        >>> embed = create_welcome_embed(
        ...     title="Welcome to OCEAN AI!",
        ...     description="We're glad you're here",
        ...     user=member
        ... )

    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),  # Friendly blue
    )

    # Set thumbnail (user avatar or custom URL)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    elif user and user.avatar:
        embed.set_thumbnail(url=user.avatar.url)

    # Set footer with user info
    if user:
        embed.set_footer(
            text=f"Welcome {user.name}!",
            icon_url=user.avatar.url if user.avatar else None,
        )

    return embed


def create_success_embed(
    title: str,
    description: str,
) -> discord.Embed:
    """Create a success/confirmation embed.

    Args:
        title: The success message title.
        description: Details about what succeeded.

    Returns:
        A green-colored success embed.

    Example:
        >>> embed = create_success_embed(
        ...     title="Welcome Message Updated",
        ...     description="The welcome message has been changed"
        ... )

    """
    embed = discord.Embed(
        title=f"✓ {title}",
        description=description,
        color=discord.Color.green(),
    )
    return embed


def create_error_embed(
    title: str,
    description: str,
    error_details: str | None = None,
) -> discord.Embed:
    """Create an error/warning embed.

    Args:
        title: The error message title.
        description: What went wrong.
        error_details: Optional technical details about the error.

    Returns:
        A red-colored error embed.

    Example:
        >>> embed = create_error_embed(
        ...     title="Permission Denied",
        ...     description="You need admin role to use this command"
        ... )

    """
    embed = discord.Embed(
        title=f"✗ {title}",
        description=description,
        color=discord.Color.red(),
    )

    if error_details:
        embed.add_field(name="Details", value=error_details, inline=False)

    return embed


def create_info_embed(
    title: str,
    description: str,
) -> discord.Embed:
    """Create an informational embed.

    Args:
        title: The info message title.
        description: The information to display.

    Returns:
        A blue-colored info embed.

    Example:
        >>> embed = create_info_embed(
        ...     title="Current Configuration",
        ...     description="Welcome channel: #welcome"
        ... )

    """
    embed = discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blue(),
    )
    return embed
