"""
Lib Mini scheduled reminder helpers.
"""

import re
from datetime import datetime

LIB_MINI_REMINDER_MESSAGE = "📚😙 Lib Mini/图书馆 Mini 即将刷新，请注意... 📖"

_LIB_MINI_DEATH_PATTERN = re.compile(
    r"^(?:lib\s*mini|图书馆\s*mini|图书馆)\s*d(?:\s+.*)?$",
    re.IGNORECASE,
)


def normalize_message(message: str) -> str:
    """Normalize spacing and case for Lib Mini command matching."""
    return re.sub(r"\s+", " ", message.replace("　", " ")).strip().lower()


def is_lib_mini_death_report(message: str) -> bool:
    """Return True when a message reports Lib Mini death."""
    return bool(_LIB_MINI_DEATH_PATTERN.match(normalize_message(message)))


def get_followup_window_start(reminder_time: datetime) -> datetime:
    """Return the matching :00 window start for a :45 follow-up check."""
    return reminder_time.replace(minute=0, second=0, microsecond=0)


def should_send_followup_reminder(
    reminder_time: datetime,
    last_death_report_time: datetime | None,
) -> bool:
    """Return True when no Lib Mini death report happened in this reminder window."""
    if last_death_report_time is None:
        return True

    window_start = get_followup_window_start(reminder_time)
    return not (window_start <= last_death_report_time < reminder_time)
