"""Kickoff-hour forecasts for outdoor and retractable-roof games (brief section 11).

Source: Open-Meteo's free forecast API, which is for non-commercial use (no ads, no
subscriptions), under 10,000 calls a day, and requires CC BY 4.0 attribution. One call
per game in the coming week, so a few dozen calls a day at most.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORECAST = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m,weather_code"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=GMT&start_date={d0}&end_date={d1}")
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=1"
UA = {"User-Agent": "starsofsabotage.com (non-commercial)"}
# WMO weather codes, short words for the page.
WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Fog",
       51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
       61: "Rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
       71: "Snow", 73: "Snow", 75: "Heavy snow", 77: "Snow", 80: "Showers", 81: "Showers", 82: "Heavy showers",
       85: "Snow showers", 86: "Snow showers", 95: "Thunderstorms", 96: "Thunderstorms", 99: "Thunderstorms"}


def load_stadiums(path: Path = ROOT / "config" / "stadiums.csv") -> tuple[dict, dict]:
    by_name, by_id = {}, {}
    with path.open(newline="") as f:
        rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    for r in rows:
        v = {"city": r["city"], "lat": float(r["lat"]), "lon": float(r["lon"]), "roof": r["roof_override"] or None}
        by_name[r["stadium"]] = v
        by_id.setdefault(r["stadium_id"], v)
    return by_name, by_id


def venue(game: dict, stadiums: tuple[dict, dict]) -> dict | None:
    by_name, by_id = stadiums
    return by_name.get(game.get("stadium") or "") or by_id.get(game.get("stadium_id") or "")


def kickoff_utc(gameday: str, gametime: str | None) -> datetime:
    from zoneinfo import ZoneInfo
    h, m = (gametime or "13:00").split(":")[:2]
    d = datetime.fromisoformat(gameday).replace(hour=int(h), minute=int(m), tzinfo=ZoneInfo("America/New_York"))
    return d.astimezone(timezone.utc)


def _get(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.loads(r.read().decode())


def roof_of(game: dict, v: dict | None) -> str:
    return (v or {}).get("roof") or game.get("roof") or "outdoors"


def forecast(games: list[dict], now: datetime, get=_get, log=print) -> dict[str, dict]:
    """game_id -> forecast at the kickoff hour, for games in the next 15 days.
    Indoor games get {"indoor": True} and no API call."""
    stadiums = load_stadiums()
    out = {}
    for g in games:
        v = venue(g, stadiums)
        roof = roof_of(g, v)
        if roof in ("dome", "closed"):
            out[g["game_id"]] = {"indoor": True, "roof": roof}
            continue
        ko = kickoff_utc(g["gameday"], g.get("gametime"))
        if not v or ko < now - timedelta(hours=4) or ko > now + timedelta(days=15):
            continue
        try:
            d = get(FORECAST.format(lat=v["lat"], lon=v["lon"], d0=ko.date().isoformat(),
                                    d1=(ko + timedelta(hours=4)).date().isoformat()))
        except Exception as e:
            log(f"[weather] {g['game_id']}: {e}")
            continue
        h = d.get("hourly", {})
        key = ko.replace(minute=0).strftime("%Y-%m-%dT%H:%M")
        if key not in h.get("time", []):
            continue
        i = h["time"].index(key)
        pick = lambda k: (h.get(k) or [None] * (i + 1))[i]
        code = pick("weather_code")
        out[g["game_id"]] = {"indoor": False, "roof": roof, "temp_f": pick("temperature_2m"),
                             "wind_mph": pick("wind_speed_10m"), "gust_mph": pick("wind_gusts_10m"),
                             "precip_pct": pick("precipitation_probability"),
                             "sky": WMO.get(code, ""), "city": v["city"]}
    return out


def check_stadiums(get=_get) -> list[dict]:
    """Distance from each venue to Open-Meteo's geocoded city, so a bad row stands out."""
    by_name, _ = load_stadiums()
    rows = []
    from urllib.parse import quote
    for name, v in by_name.items():
        try:
            r = (get(GEOCODE.format(name=quote(v["city"]))).get("results") or [{}])[0]
            km = _km(v["lat"], v["lon"], r["latitude"], r["longitude"]) if r else None
        except Exception:
            km = None
        rows.append({"stadium": name, "city": v["city"], "km_from_city": None if km is None else round(km, 1)})
    return rows


def _km(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))
