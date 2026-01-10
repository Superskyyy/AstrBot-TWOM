"""
Message formatting utilities for TWOM Boss Timer
Handles creating user-friendly messages
"""

import zoneinfo
from datetime import datetime
from typing import Dict, List, Optional

from .time_utils import format_time, format_time_short


def format_boss_spawn_message(
    display_name: str,
    spawn_time: datetime,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """
    Format boss spawn confirmation message.

    Args:
        display_name: Boss display name (with emoji)
        spawn_time: When the boss will spawn
        secondary_tz: Optional secondary timezone
        show_secondary: Whether to show secondary timezone

    Returns:
        Formatted message
    """
    time_str = format_time(spawn_time, secondary_tz=secondary_tz, show_secondary=show_secondary)
    return f"✅ 下一只 {display_name}：{time_str}"


def format_timer_added_message(
    display_name: str,
    spawn_time: datetime,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """
    Format timer added confirmation message.

    Args:
        display_name: Boss display name (with emoji)
        spawn_time: When the boss will spawn
        secondary_tz: Optional secondary timezone
        show_secondary: Whether to show secondary timezone

    Returns:
        Formatted message
    """
    time_str = format_time(spawn_time, secondary_tz=secondary_tz, show_secondary=show_secondary)
    return (
        f"✅ 已添加 {display_name} 的计时器\n"
        f"刷新时间：{time_str}\n\n"
        f"使用 /boss list 查看所有计时器"
    )


def format_timer_list(
    timers: Dict,
    bosses: Dict,
    timezone: zoneinfo.ZoneInfo,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """
    Format timer list message.

    Args:
        timers: Dictionary of timers to display
        bosses: Boss configuration dictionary
        timezone: Primary timezone
        secondary_tz: Optional secondary timezone
        show_secondary: Whether to show secondary timezone

    Returns:
        Formatted timer list message
    """
    if not timers:
        return "当前没有活跃的Boss计时器"

    # Sort timers by spawn time
    sorted_timers = sorted(
        timers.items(),
        key=lambda x: datetime.fromisoformat(x[1]["spawn_time"]),
    )

    lines = ["⏳ Boss计时器列表：\n"]
    for timer_id, timer_data in sorted_timers:
        boss_name = timer_data["boss"]
        spawn_time_str = timer_data["spawn_time"]

        # Get display name
        boss_data = bosses.get(boss_name, {})
        emoji = boss_data.get("emoji", "")
        display_name = boss_data.get("display_name", boss_name)
        full_display = f"{emoji}{display_name}" if emoji else display_name

        # Parse and format spawn time
        spawn_time = datetime.fromisoformat(spawn_time_str).replace(tzinfo=timezone)
        time_str = format_time(spawn_time, secondary_tz=secondary_tz, show_secondary=show_secondary)

        lines.append(f"{full_display}：{time_str}")

    return "\n".join(lines)


def format_reminder_message(
    display_name: str,
    spawn_time: datetime,
    minutes_before: int,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """
    Format reminder message.

    Args:
        display_name: Boss display name (with emoji)
        spawn_time: When the boss will spawn
        minutes_before: How many minutes before spawn
        secondary_tz: Optional secondary timezone
        show_secondary: Whether to show secondary timezone

    Returns:
        Formatted reminder message
    """
    time_str = format_time_short(spawn_time, secondary_tz=secondary_tz, show_secondary=show_secondary)
    return f"⏰ {display_name} 将在约 {minutes_before} 分钟后的 [{time_str}] 刷新！"


def format_map_list(maps_by_category: Dict[str, List[Dict]]) -> str:
    """
    Format map list message grouped by category.

    Args:
        maps_by_category: Dictionary of category -> list of maps

    Returns:
        Formatted map list message
    """
    lines = ["🗺️ 可用地图列表：\n"]

    for category, maps in maps_by_category.items():
        lines.append(f"【{category}】")
        for map_data in maps:
            map_name = map_data.get("name", "未知")
            aliases = map_data.get("aliases", [])
            if aliases:
                alias_str = "、".join(aliases[:3])  # Show first 3 aliases
                lines.append(f"  • {map_name} (别名: {alias_str})")
            else:
                lines.append(f"  • {map_name}")
        lines.append("")  # Empty line between categories

    lines.append("使用 /map <地图名> 查看具体地图")
    return "\n".join(lines)
