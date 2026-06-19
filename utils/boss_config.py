"""
Boss configuration management for TWOM Boss Timer
Handles loading boss data, alias mapping, and display names
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


def load_bosses(default_bosses_path: Path) -> Dict:
    """
    Load boss configuration from default bosses file.

    Args:
        default_bosses_path: Path to default_bosses.json

    Returns:
        Dictionary of boss configurations
    """
    if default_bosses_path.exists():
        with open(default_bosses_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_alias_map(bosses: Dict) -> Dict[str, str]:
    """
    Build alias to boss_name mapping.

    Args:
        bosses: Boss configuration dictionary

    Returns:
        Dictionary mapping lowercase alias to boss_name
    """
    alias_map = {}
    for boss_name, boss_data in bosses.items():
        # Boss name itself is an alias
        alias_map[boss_name.lower()] = boss_name

        # Add display name as alias
        display_name = boss_data.get("display_name")
        if display_name:
            alias_map[display_name.lower()] = boss_name

        # Add all configured aliases
        for alias in boss_data.get("aliases", []):
            alias_map[alias.lower()] = boss_name

    return alias_map


def get_boss_by_alias(alias: str, alias_map: Dict[str, str]) -> Optional[str]:
    """
    Get boss name by alias (case-insensitive).

    Args:
        alias: Alias to look up
        alias_map: Alias mapping dictionary

    Returns:
        Boss name if found, None otherwise
    """
    return alias_map.get(alias.lower())


@dataclass
class BossDeathCommand:
    """Parsed result of a boss death report."""

    boss_name: Optional[str]  # resolved boss key, or None if alias unknown
    boss_input: str  # the text the user typed for the boss name
    time_part: Optional[str]  # trailing time text, or None
    has_space_before_d: bool  # True when the death keyword was a separate "d" token


def parse_boss_death_command(
    message: str, alias_map: Dict[str, str]
) -> Optional[BossDeathCommand]:
    """
    Parse a boss death report of the form ``<boss> d [time]`` or ``<boss>d [time]``.

    The boss name is matched as the **longest** token sequence before the death
    keyword, so multi-word aliases (e.g. ``red bee``) resolve correctly instead
    of being split into a shorter prefix alias (e.g. ``red``). The parser never
    splits inside a whitespace token, avoiding the previous bug where the ``d``
    inside ``red`` was treated as the death keyword.

    Args:
        message: Raw user message.
        alias_map: Alias mapping from :func:`build_alias_map`.

    Returns:
        A :class:`BossDeathCommand` when the message looks like a death report
        (``boss_name`` is ``None`` when the boss alias is unknown), or ``None``
        when the message is not a death report at all.
    """
    tokens = message.lower().split()
    if not tokens:
        return None

    # Case A: standalone "d" death keyword — "<boss tokens> d [time tokens]".
    # The boss is everything before the first standalone "d" (longest sequence),
    # so multi-word aliases are matched before any shorter prefix.
    if "d" in tokens:
        i = tokens.index("d")
        boss_input = " ".join(tokens[:i])
        if not boss_input:
            return None
        time_part = " ".join(tokens[i + 1:]) or None
        boss_name = get_boss_by_alias(boss_input, alias_map)
        return BossDeathCommand(boss_name, boss_input, time_part, True)

    # Case B: no-space form "<boss>d [time]" — a single boss token ending in 'd'
    # (e.g. CJK names like "大树d"). Only the first token can carry the keyword.
    first = tokens[0]
    if not first.endswith("d"):
        return None  # no death keyword present → not a death report
    time_part = " ".join(tokens[1:]) or None

    # Longest before short: try the full token first (boss name may end in 'd'),
    # then fall back to the token without the trailing 'd'.
    boss_name = get_boss_by_alias(first, alias_map)
    if boss_name:
        return BossDeathCommand(boss_name, first, time_part, False)
    stripped = first[:-1]
    boss_name = get_boss_by_alias(stripped, alias_map)
    return BossDeathCommand(boss_name, stripped, time_part, False)


def get_boss_display_name(boss_name: str, bosses: Dict) -> str:
    """
    Get boss display name with emoji.

    Args:
        boss_name: Boss key/name
        bosses: Boss configuration dictionary

    Returns:
        Formatted display name (emoji + display_name)
    """
    boss_data = bosses.get(boss_name, {})
    emoji = boss_data.get("emoji", "")
    display_name = boss_data.get("display_name", boss_name)
    return f"{emoji}{display_name}" if emoji else display_name


def calculate_spawn_time(
    boss_name: str, death_time: datetime, bosses: Dict
) -> datetime:
    """
    Calculate boss spawn time based on death time and respawn duration.

    Args:
        boss_name: Boss key/name
        death_time: When the boss was killed
        bosses: Boss configuration dictionary

    Returns:
        Calculated spawn time
    """
    boss_data = bosses.get(boss_name, {})
    hours = boss_data.get("respawn_hours", 0)
    minutes = boss_data.get("respawn_minutes", 0)
    seconds = boss_data.get("respawn_seconds", 0)

    return death_time + timedelta(hours=hours, minutes=minutes, seconds=seconds)
