"""
Permission utilities for TWOM Boss Timer
Handles whitelist and boss filtering for groups/users
Supports two isolated group sets (Set 1 and Set 2)
"""

import json
from typing import Dict, List, Optional, Set

from astrbot.api import logger


def get_group_set(group_id: str, config: Dict) -> Optional[int]:
    """
    Determine which set a group belongs to.

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        1 if group is in Set 1, 2 if in Set 2, None if not in any set
    """
    group_id_str = str(group_id)

    # Check Set 1 (whitelist_groups + core_groups)
    whitelist_1 = [str(g) for g in config.get("whitelist_groups", [])]
    core_1 = [str(g) for g in config.get("core_groups", [])]
    if group_id_str in whitelist_1 or group_id_str in core_1:
        return 1

    # Check Set 2 (whitelist_groups_2 + core_groups_2)
    whitelist_2 = [str(g) for g in config.get("whitelist_groups_2", [])]
    core_2 = [str(g) for g in config.get("core_groups_2", [])]
    if group_id_str in whitelist_2 or group_id_str in core_2:
        return 2

    return None


def get_all_groups_in_set(set_num: int, config: Dict) -> Set[str]:
    """
    Get all group IDs in a specific set.

    Args:
        set_num: Set number (1 or 2)
        config: Plugin configuration

    Returns:
        Set of all group IDs in the specified set
    """
    if set_num == 1:
        whitelist = [str(g) for g in config.get("whitelist_groups", [])]
        core = [str(g) for g in config.get("core_groups", [])]
    elif set_num == 2:
        whitelist = [str(g) for g in config.get("whitelist_groups_2", [])]
        core = [str(g) for g in config.get("core_groups_2", [])]
    else:
        return set()

    return set(whitelist) | set(core)


def is_group_enabled(group_id: str, config: Dict) -> bool:
    """
    Check if boss timer is enabled for this group.

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        True if enabled (whitelist disabled or group in any set)
    """
    whitelist_enabled = config.get("whitelist_enabled", False)
    if not whitelist_enabled:
        return True

    # Check if group belongs to any set
    return get_group_set(group_id, config) is not None


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
    Check if this is a core group (can view all timers in its set).

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        True if this is a core group (in either set)
    """
    group_id_str = str(group_id)
    core_1 = [str(g) for g in config.get("core_groups", [])]
    core_2 = [str(g) for g in config.get("core_groups_2", [])]
    return group_id_str in core_1 or group_id_str in core_2


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
    Enforces set isolation: groups in Set 1 cannot see Set 2 timers and vice versa.

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

    # Get timer's owner group from timer_data
    timer_group_id = timer_data.get("group_id")
    if not timer_group_id:
        # Fallback: extract from timer_id (format: {group_id}_{boss})
        parts = timer_id.split("_", 1)
        timer_group_id = parts[0] if parts else None

    # Determine which set the viewer and timer belong to
    viewer_set = get_group_set(viewer_group_id, config)
    timer_set = get_group_set(timer_group_id, config) if timer_group_id else None

    # Set isolation: only show timers from the same set
    if viewer_set != timer_set:
        return False

    # Core groups can see all timers within their set
    if is_core_group(viewer_group_id, config):
        return True

    # Normal groups only see their own timers
    return timer_id.startswith(f"{viewer_group_id}_")
