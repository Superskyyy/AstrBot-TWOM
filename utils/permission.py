"""
Permission utilities for TWOM Boss Timer
Handles whitelist and boss filtering for groups/users
"""

import json
from typing import Dict, List, Optional, Set

from astrbot.api import logger


def is_group_enabled(group_id: str, config: Dict) -> bool:
    """
    Check if boss timer is enabled for this group.

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        True if enabled (whitelist disabled or group in whitelist)
    """
    whitelist_enabled = config.get("whitelist_enabled", False)
    if not whitelist_enabled:
        return True

    whitelist_groups = config.get("whitelist_groups", [])
    return str(group_id) in [str(g) for g in whitelist_groups]


def is_user_enabled(user_id: str, config: Dict) -> bool:
    """
    Check if boss timer is enabled for this user in private chat.

    Args:
        user_id: User ID to check
        config: Plugin configuration

    Returns:
        True if enabled (user in whitelist_users)
    """
    whitelist_users = config.get("whitelist_users", [])
    if not whitelist_users:
        logger.debug("Private chat disabled: whitelist_users is empty")
        return False
    return str(user_id) in [str(u) for u in whitelist_users]


def is_core_group(group_id: str, config: Dict) -> bool:
    """
    Check if this is a core group (can view all timers).

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        True if this is a core group
    """
    core_groups = config.get("core_groups", [])
    return str(group_id) in [str(g) for g in core_groups]


def get_allowed_bosses_for_group(group_id: str, config: Dict) -> Optional[Set[str]]:
    """
    Get set of allowed boss names for this group.

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        Set of allowed boss names, or None if no filtering (all bosses allowed)
    """
    filter_enabled = config.get("group_boss_filter_enabled", False)
    if not filter_enabled:
        return None  # No filtering, all bosses allowed

    # Parse filters from JSON string
    filters_str = config.get("group_boss_filters", "{}")
    try:
        filters = json.loads(filters_str)
    except Exception as e:
        logger.error(f"Failed to parse group_boss_filters: {e}")
        return None

    # Get filter for this group
    group_filter = filters.get(str(group_id))
    if not group_filter:
        return None  # No filter for this group, all bosses allowed

    # Return as set for fast lookup
    return set(group_filter)


def should_show_timer(
    timer_id: str,
    timer_data: Dict,
    viewer_group_id: Optional[str],
    viewer_user_id: Optional[str],
    config: Dict,
) -> bool:
    """
    Check if a timer should be visible to the viewer.

    Args:
        timer_id: Timer ID
        timer_data: Timer data dictionary
        viewer_group_id: Group ID of viewer (None for private chat)
        viewer_user_id: User ID of viewer
        config: Plugin configuration

    Returns:
        True if timer should be shown
    """
    # Private chat viewer
    if viewer_group_id is None:
        # Only show private timers for this user
        return timer_id.startswith(f"private_{viewer_user_id}_")

    # Group viewer
    # Never show private timers in groups (even core groups)
    if timer_id.startswith("private_"):
        return False

    # Core groups can see all group timers
    if is_core_group(viewer_group_id, config):
        return True

    # Normal groups only see their own timers
    return timer_id.startswith(f"{viewer_group_id}_")
