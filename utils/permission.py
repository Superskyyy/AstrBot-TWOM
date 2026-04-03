"""
Permission utilities for TWOM Boss Timer
Handles whitelist and boss filtering for groups/users
Supports isolated group sets (Set 1, Set 2, Set 3, ...)
"""

import json
from typing import Dict, List, Optional, Set

from astrbot.api import logger


def _get_set_config_keys(set_num: int) -> tuple[str, str]:
    """Return whitelist/core config keys for a set number."""
    if set_num == 1:
        return "whitelist_groups", "core_groups"
    return f"whitelist_groups_{set_num}", f"core_groups_{set_num}"


def _get_configured_set_numbers(config: Dict) -> List[int]:
    """
    Discover all supported set numbers from the config.

    Set 1 always exists via the legacy unnumbered keys, while extra sets use
    numbered keys such as whitelist_groups_2 / core_groups_2.
    """
    set_numbers = {1}

    for key in config.keys():
        if not (key.startswith("whitelist_groups_") or key.startswith("core_groups_")):
            continue
        suffix = key.rsplit("_", 1)[-1]
        if suffix.isdigit():
            set_numbers.add(int(suffix))

    return sorted(set_numbers)


def get_group_set(group_id: str, config: Dict) -> Optional[int]:
    """
    Determine which set a group belongs to.

    Args:
        group_id: Group ID to check
        config: Plugin configuration

    Returns:
        Set number if group is in a configured set, None otherwise
    """
    group_id_str = str(group_id)

    for set_num in _get_configured_set_numbers(config):
        whitelist_key, core_key = _get_set_config_keys(set_num)
        whitelist = [str(g) for g in config.get(whitelist_key, [])]
        core = [str(g) for g in config.get(core_key, [])]
        if group_id_str in whitelist or group_id_str in core:
            return set_num

    return None


def get_all_groups_in_set(set_num: int, config: Dict) -> Set[str]:
    """
    Get all group IDs in a specific set.

    Args:
        set_num: Set number
        config: Plugin configuration

    Returns:
        Set of all group IDs in the specified set
    """
    if set_num not in _get_configured_set_numbers(config):
        return set()

    whitelist_key, core_key = _get_set_config_keys(set_num)
    whitelist = [str(g) for g in config.get(whitelist_key, [])]
    core = [str(g) for g in config.get(core_key, [])]

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
        True if this is a core group (in any configured set)
    """
    group_id_str = str(group_id)

    for set_num in _get_configured_set_numbers(config):
        _, core_key = _get_set_config_keys(set_num)
        core_groups = [str(g) for g in config.get(core_key, [])]
        if group_id_str in core_groups:
            return True

    return False


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
    Enforces set isolation: groups can only see timers from their own set.

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
