"""
Map configuration management for TWOM Boss Timer
Handles loading map data and alias mapping
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from astrbot.api import logger


def load_maps(assets_dir: Path) -> List[Dict]:
    """
    Load map configuration from assets directory.

    Args:
        assets_dir: Assets directory containing maps.json

    Returns:
        List of map configurations
    """
    maps_file = assets_dir / "maps.json"
    if not maps_file.exists():
        logger.warning(f"maps.json not found at {maps_file}")
        return []

    try:
        with open(maps_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("maps", [])
    except Exception as e:
        logger.error(f"Failed to load maps.json: {e}")
        return []


def build_map_alias_map(maps: List[Dict]) -> Dict[str, Dict]:
    """
    Build alias to map mapping.

    Args:
        maps: List of map configurations

    Returns:
        Dictionary mapping lowercase alias/ID to map data
    """
    alias_map = {}
    for map_data in maps:
        map_id = map_data.get("id")
        map_name = map_data.get("name")

        # Map by ID
        if map_id:
            alias_map[map_id.lower()] = map_data

        # Map by name
        if map_name:
            alias_map[map_name.lower()] = map_data

        # Map by aliases
        for alias in map_data.get("aliases", []):
            alias_map[alias.lower()] = map_data

    return alias_map


def get_map_by_alias(alias: str, alias_map: Dict[str, Dict]) -> Optional[Dict]:
    """
    Get map data by alias/ID/name (case-insensitive).

    Args:
        alias: Alias, ID, or name to look up
        alias_map: Map alias mapping dictionary

    Returns:
        Map data if found, None otherwise
    """
    return alias_map.get(alias.lower())


def get_maps_by_category(maps: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group maps by category.

    Args:
        maps: List of map configurations

    Returns:
        Dictionary of category -> list of maps
    """
    result = {}
    for map_data in maps:
        category = map_data.get("category", "其他")
        if category not in result:
            result[category] = []
        result[category].append(map_data)
    return result
