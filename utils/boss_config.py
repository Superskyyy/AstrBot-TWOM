"""
Boss configuration management for TWOM Boss Timer
Handles loading boss data, alias mapping, and display names
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from astrbot.api import logger


def load_bosses(data_dir: Path, default_bosses_path: Path) -> Dict:
    """
    Load boss configuration from data directory or default.

    Args:
        data_dir: Directory to store/load boss configuration
        default_bosses_path: Path to default bosses.json

    Returns:
        Dictionary of boss configurations
    """
    bosses_file = data_dir / "bosses.json"

    # Copy default bosses if not exists
    if not bosses_file.exists():
        if default_bosses_path.exists():
            shutil.copy(default_bosses_path, bosses_file)
            logger.info("Created default bosses.json")

    # Load bosses
    if bosses_file.exists():
        with open(bosses_file, "r", encoding="utf-8") as f:
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
