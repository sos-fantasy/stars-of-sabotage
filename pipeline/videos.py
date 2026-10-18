"""Weekly worst-plays videos (brief section 10).

Sources, in order of authority:
1. config/videos_manual.csv: rows the owner adds by hand. A manual row replaces every
   automatic video for that season and week. A youtube_url of "none" hides the week.
2. YouTube RSS feeds for the playlists or channels in config/video_sources.yml
   (channels are filtered by title; a curated playlist can skip the filter).
3. Videos found on earlier runs, carried forward from the previous deploy, because a
   feed only lists a channel's latest 15 or so uploads.

Each video's embeddability is checked through YouTube's oEmbed endpoint: 200 means it
can be embedded, 401 or 403 means the uploader turned embedding off (the page shows a
link card instead), 404 means the video is gone (it is dropped).
"""
from __future__ import annotations

import csv
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FEED = "https://www.youtube.com/feeds/videos.xml?{}={}"   # channel_id or playlist_id
OEMBED = "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v={}"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
WEEK_RE = re.compile(r"\bweek\s*(\d{1,2})\b", re.I)
UA = {"User-Agent": "starsofsabotage.com video check (+https://starsofsabotage.com)"}


def load_sources(path: Path = ROOT / "config" / "video_sources.yml") -> list[dict]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text()) or {}).get("sources", []) or []


def play_on_site(path: Path = ROOT / "config" / "video_sources.yml") -> bool:
    """False when videos should open on YouTube instead of playing on our page."""
    if not path.exists():
        return True
    return bool((yaml.safe_load(path.read_text()) or {}).get("play_on_site", True))


def video_id(url: str) -> str | None:
    """Pull the 11-character id out of any common YouTube link, or accept a bare id."""
    url = (url or "").strip()
    if ID_RE.match(url):
        return url
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.findtext("a:title", default="", namespaces=NS)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        if not vid:
            continue
        # In a playlist feed each entry names its own uploader; prefer that.
        author = e.findtext("a:author/a:name", namespaces=NS)
        out.append({"id": vid, "title": (e.findtext("a:title", namespaces=NS) or "").strip(),
                    "published": e.findtext("a:published", namespaces=NS), "channel": author or channel})
    return out


def week_ends(games: list[dict]) -> dict[int, date]:
    """Date of the last game in each regular-season week."""
    ends: dict[int, date] = {}
    for g in games:
        d = date.fromisoformat(g["gameday"])
        if g["week"] not in ends or d > ends[g["week"]]:
            ends[g["week"]] = d
    return ends


def assign_week(title: str, published: str, ends: dict[int, date]) -> int | None:
    """The week a video covers. A week number in the title wins when it is a real week
    that has finished by the publish date. Otherwise it is the week whose last game came
    most recently on or before the publish date (Eastern)."""
    from schedule import ET as EASTERN
    pub = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(EASTERN).date()
    done = [w for w, d in ends.items() if d <= pub]
    m = WEEK_RE.search(title or "")
    if m and int(m.group(1)) in done:
        return int(m.group(1))
    return max(done) if done else None


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def check_embed(vid: str, get=fetch) -> str:
    """'yes', 'no' (embedding disabled), 'gone' (removed or private), or 'unknown'."""
    try:
        code, _ = get(OEMBED.format(vid))
    except Exception:
        return "unknown"
    return {200: "yes", 401: "no", 403: "no", 404: "gone", 400: "gone"}.get(code, "unknown")


def read_manual(path: Path = ROOT / "config" / "videos_manual.csv") -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("season") or "").strip() or (r.get("season") or "").startswith("#"):
                continue
            url = (r.get("youtube_url") or "").strip()
            rows.append({"season": int(r["season"]), "week": int(r["week"]),
                         "id": None if url.lower() == "none" else video_id(url),
                         "title": (r.get("title") or "").strip(), "hide": url.lower() == "none"})
    return rows


def build(season: int, games: list[dict], prev: list[dict], sources: list[dict], manual: list[dict],
          get=fetch, log=print) -> list[dict]:
    """Merge carried-forward, feed, and manual videos into the list the site reads."""
    ends = week_ends(games)
    by_id = {v["id"]: dict(v) for v in prev if v.get("source") == "auto"}
    for src in sources:
        # A curated playlist needs no title filter; a whole channel does.
        pat = re.compile(src.get("title_pattern") or "", re.I)
        kind = "playlist_id" if src.get("playlist_id") else "channel_id"
        try:
            code, body = get(FEED.format(kind, src[kind]))
        except Exception as e:  # network trouble: keep what we had
            log(f"[videos] {src.get('name')}: feed unreachable ({e})")
            continue
        if code != 200:
            log(f"[videos] {src.get('name')}: feed returned {code}")
            continue
        found = 0
        for e in parse_feed(body):
            if not pat.search(e["title"]) or e["id"] in by_id:
                continue
            wk = assign_week(e["title"], e["published"], ends)
            if wk is None:
                continue
            by_id[e["id"]] = {"season": season, "week": wk, "id": e["id"], "title": e["title"],
                              "channel": e["channel"] or src.get("name", ""), "published": e["published"],
                              "source": "auto", "embed": "unknown"}
            found += 1
        log(f"[videos] {src.get('name')}: {found} new")

    # Manual rows replace automatic ones for their week.
    manual_weeks = {(m["season"], m["week"]) for m in manual}
    out = [v for v in by_id.values() if (v["season"], v["week"]) not in manual_weeks]
    prev_manual = {v["id"]: v for v in prev if v.get("source") == "manual"}
    for m in manual:
        if m["hide"] or not m["id"]:
            continue
        old = prev_manual.get(m["id"], {})
        out.append({"season": m["season"], "week": m["week"], "id": m["id"],
                    "title": m["title"] or old.get("title", ""), "channel": old.get("channel", ""),
                    "published": old.get("published"), "source": "manual", "embed": old.get("embed", "unknown")})

    # Recheck embeddability for this season's videos and anything not yet known.
    kept = []
    for v in out:
        if v["season"] == season or v["embed"] == "unknown":
            status = check_embed(v["id"], get)
            if status != "unknown":
                v["embed"] = status
            if status == "gone":
                log(f"[videos] {v['id']} ({v['season']} week {v['week']}) is no longer on YouTube; dropped")
                continue
            if v["source"] == "manual" and (not v["title"] or not v["channel"]) and status == "yes":
                info = _oembed(v["id"], get)
                v["title"] = v["title"] or info.get("title", "")
                v["channel"] = v["channel"] or info.get("author_name", "")
        kept.append(v)
    kept.sort(key=lambda v: (-v["season"], -v["week"], v.get("published") or ""))
    return kept


def _oembed(vid: str, get) -> dict:
    """Title and uploader name from oEmbed, for videos added by hand."""
    import json
    try:
        code, body = get(OEMBED.format(vid))
        return json.loads(body) if code == 200 else {}
    except Exception:
        return {}
