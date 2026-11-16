"""When each social card is due, in Eastern time.

Game cards: every game that is not a Sunday afternoon game (Thursday, Saturday,
Sunday night, Monday, holidays) posts the next morning at 9 AM ET. A Sunday
night game posts Monday at 1 PM, because Monday 9 AM belongs to Sunday Wreckage.
Two games due in the same slot are spaced an hour apart in kickoff order.

Sunday Wreckage: Monday 9 AM ET after that week's Sunday afternoon games.

A card stays due for WINDOW after its slot so a late data refresh or a missed
hourly run still posts it the same day.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from top7 import is_night, is_sunday_afternoon, weekday

ET = ZoneInfo("America/New_York")
WINDOW = timedelta(hours=12)


def _at(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour, 0), tzinfo=ET)


def slots(games: list[dict], season: int) -> list[dict]:
    out, taken = [], {}
    standalone = sorted((g for g in games if not is_sunday_afternoon(g)),
                        key=lambda g: (g["gameday"], g.get("gametime") or ""))
    for g in standalone:
        day = date.fromisoformat(g["gameday"]) + timedelta(days=1)
        hour = 13 if weekday(g) == "SUNDAY" and is_night(g) else 9
        key = (day, hour)
        while key in taken:  # same slot already used: next hour
            key = (key[0], key[1] + 1)
        taken[key] = g["game_id"]
        out.append({"id": f"game-{g['game_id']}", "type": "game", "game_id": g["game_id"],
                    "week": g["week"], "due": _at(*key)})
    sundays = {}
    for g in games:
        if is_sunday_afternoon(g):
            sundays.setdefault(g["week"], g["gameday"])
    for week, sunday in sundays.items():
        out.append({"id": f"wreckage-{season}-{week:02d}", "type": "wreckage", "week": week,
                    "due": _at(date.fromisoformat(sunday) + timedelta(days=1), 9)})
    return sorted(out, key=lambda s: s["due"])


def due(all_slots: list[dict], now: datetime, done: set[str]) -> list[dict]:
    return [s for s in all_slots if s["due"] <= now < s["due"] + WINDOW and s["id"] not in done]
