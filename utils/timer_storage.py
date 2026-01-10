"""
Timer storage management for TWOM Boss Timer
Handles loading, saving, and managing timer data
"""

import json
from pathlib import Path
from typing import Dict

from astrbot.api import logger


def load_timers(data_dir: Path) -> Dict:
    """
    Load timers from JSON file.

    Args:
        data_dir: Directory containing timers.json

    Returns:
        Dictionary of timers
    """
    timers_file = data_dir / "timers.json"
    if timers_file.exists():
        try:
            with open(timers_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load timers.json: {e}")
    return {}


def save_timers(data_dir: Path, timers: Dict) -> None:
    """Save timers to JSON file"""
    timers_file = data_dir / "timers.json"
    try:
        with open(timers_file, "w", encoding="utf-8") as f:
            json.dump(timers, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save timers.json: {e}")
