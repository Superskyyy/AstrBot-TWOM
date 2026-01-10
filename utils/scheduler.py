"""
Scheduler utilities for TWOM Boss Timer
Handles reminder scheduling and job management
"""

import zoneinfo
from datetime import datetime, timedelta
from typing import Callable, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from astrbot.api import logger


def get_reminder_intervals(config: dict) -> List[int]:
    """
    Get reminder intervals from config.

    Args:
        config: Plugin configuration

    Returns:
        List of reminder intervals in minutes
    """
    intervals_str = config.get("reminder_intervals", "3")
    try:
        return [int(x.strip()) for x in intervals_str.split(",")]
    except Exception as e:
        logger.warning(f"Invalid reminder_intervals: {e}, using default [3]")
        return [3]


def schedule_reminders(
    scheduler: AsyncIOScheduler,
    timer_id: str,
    boss_name: str,
    spawn_time: datetime,
    umo: str,
    reminder_callback: Callable,
    intervals: List[int],
    timezone: zoneinfo.ZoneInfo,
) -> int:
    """
    Schedule reminder jobs for a boss timer.

    Args:
        scheduler: APScheduler instance
        timer_id: Unique timer ID
        boss_name: Boss key/name
        spawn_time: When the boss will spawn
        umo: Unified message origin (group/user ID)
        reminder_callback: Async function to call for reminders
        intervals: List of reminder intervals in minutes
        timezone: Timezone for scheduling

    Returns:
        Number of reminders successfully scheduled
    """
    now = datetime.now(timezone)
    scheduled_count = 0

    for minutes in intervals:
        remind_time = spawn_time - timedelta(minutes=minutes)

        # Skip if remind time has passed
        if remind_time <= now:
            logger.debug(f"Skipping past reminder for {boss_name} at {remind_time}")
            continue

        # Schedule the reminder
        job_id = f"{timer_id}_remind_{minutes}min"
        try:
            scheduler.add_job(
                reminder_callback,
                "date",
                run_date=remind_time,
                args=[boss_name, spawn_time, umo, minutes],
                id=job_id,
                replace_existing=True,
            )
            scheduled_count += 1
            logger.debug(f"Scheduled {boss_name} {minutes}min reminder at {remind_time}")
        except Exception as e:
            logger.error(f"Failed to schedule reminder {job_id}: {e}")

    return scheduled_count


def cancel_reminder_jobs(scheduler: AsyncIOScheduler, timer_id: str) -> int:
    """
    Cancel all reminder jobs for a timer.

    Args:
        scheduler: APScheduler instance
        timer_id: Timer ID

    Returns:
        Number of jobs cancelled
    """
    cancelled_count = 0
    # Get all jobs that match this timer
    for job in scheduler.get_jobs():
        if job.id.startswith(f"{timer_id}_remind_"):
            try:
                job.remove()
                cancelled_count += 1
                logger.debug(f"Cancelled job {job.id}")
            except Exception as e:
                logger.error(f"Failed to cancel job {job.id}: {e}")

    return cancelled_count


def cleanup_expired_timers(
    timers: dict,
    timezone: zoneinfo.ZoneInfo,
) -> int:
    """
    Remove expired timers from dictionary.

    Args:
        timers: Timers dictionary
        timezone: Timezone for comparison

    Returns:
        Number of timers removed
    """
    now = datetime.now(timezone)
    to_remove = []

    for timer_id, timer_data in timers.items():
        spawn_time_str = timer_data.get("spawn_time")
        if not spawn_time_str:
            to_remove.append(timer_id)
            continue

        try:
            spawn_time = datetime.fromisoformat(spawn_time_str).replace(tzinfo=timezone)
            if spawn_time < now:
                to_remove.append(timer_id)
        except Exception as e:
            logger.error(f"Invalid spawn_time for {timer_id}: {e}")
            to_remove.append(timer_id)

    # Remove expired timers
    for timer_id in to_remove:
        del timers[timer_id]

    return len(to_remove)
