"""
Time utilities for TWOM Boss Timer
Handles timezone conversion, time parsing, and formatting
"""

import re
import zoneinfo
from datetime import datetime, timedelta
from typing import Optional

from astrbot.api import logger


def init_timezone(tz_str: str = "Asia/Shanghai") -> zoneinfo.ZoneInfo:
    """Initialize timezone from config string"""
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception as e:
        logger.warning(f"Invalid timezone {tz_str}: {e}, using Asia/Shanghai")
        return zoneinfo.ZoneInfo("Asia/Shanghai")


def format_time(
    dt: datetime,
    show_date: bool = True,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """
    Format datetime for display with dual timezone support.
    Returns formatted string with both primary and secondary time if configured.

    Args:
        dt: Datetime to format
        show_date: Whether to include date in output
        secondary_tz: Optional secondary timezone (e.g., America/Toronto)
        show_secondary: Whether to show secondary timezone

    Returns:
        Formatted time string, e.g., "01月10日 15:30:00 | 🍁 01月10日 02:30:00"
    """
    if show_date:
        primary_time = dt.strftime("%m月%d日 %H:%M:%S")
    else:
        primary_time = dt.strftime("%H:%M:%S")

    if not show_secondary or not secondary_tz:
        return primary_time

    # Convert to secondary timezone (automatic DST handling)
    dt_secondary = dt.astimezone(secondary_tz)
    if show_date:
        secondary_time = dt_secondary.strftime("%m月%d日 %H:%M:%S")
    else:
        secondary_time = dt_secondary.strftime("%H:%M:%S")

    return f"{primary_time} | 🍁 {secondary_time}"


def format_time_short(
    dt: datetime,
    secondary_tz: Optional[zoneinfo.ZoneInfo] = None,
    show_secondary: bool = True,
) -> str:
    """Format datetime (short version, no date)"""
    return format_time(dt, show_date=False, secondary_tz=secondary_tz, show_secondary=show_secondary)


def parse_spawn_time(time_str: str, timezone: zoneinfo.ZoneInfo) -> datetime:
    """
    Parse spawn time string into datetime object.

    Supported formats:
      - "15:30" or "15:30:45" (today or tomorrow)
      - "01-11 15:30" or "01-11 15:30:45" (specific date)

    Args:
        time_str: Time string to parse
        timezone: Timezone for the datetime

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If time_str format is invalid
    """
    now = datetime.now(timezone)
    time_str = time_str.strip().replace("：", ":")  # Handle Chinese colon

    # Try parsing with date
    if " " in time_str:
        # Format: "01-11 15:30" or "01-11 15:30:45"
        parts = time_str.split()
        if len(parts) != 2:
            raise ValueError("格式应为: MM-DD HH:MM 或 MM-DD HH:MM:SS")

        date_part, time_part = parts

        # Parse date (MM-DD)
        date_match = re.match(r"(\d{1,2})-(\d{1,2})", date_part)
        if not date_match:
            raise ValueError("日期格式应为: MM-DD")

        month = int(date_match.group(1))
        day = int(date_match.group(2))

        # Parse time
        time_match = re.match(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", time_part)
        if not time_match:
            raise ValueError("时间格式应为: HH:MM 或 HH:MM:SS")

        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        second = int(time_match.group(3)) if time_match.group(3) else 0

        # Determine year (current year or next year if date has passed)
        year = now.year
        try:
            spawn_time = datetime(year, month, day, hour, minute, second, tzinfo=timezone)
            if spawn_time <= now:
                # Try next year
                spawn_time = datetime(year + 1, month, day, hour, minute, second, tzinfo=timezone)
        except ValueError as e:
            raise ValueError(f"无效的日期或时间: {e}")
    else:
        # Format: "15:30" or "15:30:45" (today)
        time_match = re.match(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", time_str)
        if not time_match:
            raise ValueError("时间格式应为: HH:MM 或 HH:MM:SS")

        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        second = int(time_match.group(3)) if time_match.group(3) else 0

        # Use today's date
        spawn_time = datetime(
            now.year, now.month, now.day, hour, minute, second, tzinfo=timezone
        )

        # If time has passed today, assume tomorrow
        if spawn_time <= now:
            spawn_time += timedelta(days=1)

    return spawn_time


def parse_death_time(time_str: str, timezone: zoneinfo.ZoneInfo) -> datetime:
    """
    Parse death time from user input.

    Supported formats:
      - "d" - now
      - "d 23" - current hour :23
      - "d 12:30" - today 12:30
      - "d 12:30:45" - today 12:30:45

    Args:
        time_str: Time string to parse (without "d" prefix)
        timezone: Timezone for the datetime

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If time_str format is invalid
    """
    now = datetime.now(timezone)
    time_str = time_str.strip().replace("：", ":")  # Handle Chinese colon

    if not time_str:
        # Just "d" - killed now
        return now

    # Check if it's just minutes (e.g., "23")
    if time_str.isdigit():
        # Current hour, specified minute
        minute = int(time_str)
        if not 0 <= minute < 60:
            raise ValueError("分钟必须在 0-59 之间")
        death_time = now.replace(minute=minute, second=0, microsecond=0)
        return death_time

    # Try parsing as HH:MM or HH:MM:SS
    time_match = re.match(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        second = int(time_match.group(3)) if time_match.group(3) else 0

        if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
            raise ValueError("时间格式错误")

        # Use today's date with specified time
        death_time = now.replace(
            hour=hour, minute=minute, second=second, microsecond=0
        )
        return death_time

    raise ValueError(
        "时间格式错误。支持格式：d, d 23, d 12:30, d 12:30:45"
    )
