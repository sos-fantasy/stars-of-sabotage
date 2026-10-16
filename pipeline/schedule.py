"""When the hourly workflow should do real work, and when a week counts as final.

GitHub cron runs in UTC and ignores daylight saving, so the workflow fires
every hour and this module decides in America/New_York time.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

DAILY_HOURS = {6, 10}                 # morning refresh, plus late-morning catch-up
GAME_DAY_HOURS = {16, 19, 22}         # during and after the afternoon and night windows
AFTER_GAME_DAY_HOURS = {1, 4}         # overnight, after late games and the nightly nflverse run
CORRECTION_SLOTS = {(2, 22), (3, 4)}  # (weekday, hour): Wed 10 PM and Thu 4 AM; Mon=0


def is_due(now_et: datetime, game_dates: set[date]) -> tuple[bool, str]:
    """Return (due, reason) for an ET wall-clock time."""
    h, d = now_et.hour, now_et.date()
    if h in DAILY_HOURS:
        return True, "daily refresh"
    if d in game_dates and h in GAME_DAY_HOURS:
        return True, "game day"
    if (d - timedelta(days=1)) in game_dates and h in AFTER_GAME_DAY_HOURS:
        return True, "after game day"
    if (now_et.weekday(), h) in CORRECTION_SLOTS:
        return True, "stat corrections"
    return False, "nothing scheduled this hour"


def final_at(last_game_day: date) -> datetime:
    """A week is final at 10 AM ET on the first Thursday after its last game,
    once the Wednesday-night correction refresh has landed."""
    days = (3 - last_game_day.weekday()) % 7 or 7
    return datetime.combine(last_game_day + timedelta(days=days), time(10, 0), tzinfo=ET)


def week_status(now: datetime, games_total: int, games_done: int, last_game_day: date | None) -> str:
    if games_done == 0:
        return "upcoming"
    if games_done < games_total:
        return "in_progress"
    return "final" if now >= final_at(last_game_day) else "provisional"
