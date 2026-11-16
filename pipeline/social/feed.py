"""RSS feed of social cards for Pinterest's "auto-publish from RSS" (no API approval needed).

Pinterest rules (help.pinterest.com, "Auto-publish Pins from your RSS feed"): RSS 2.0, the site
must be claimed (starsofsabotage.com, claimed Nov 15, 2026), every item's link must be on that
domain, title and description come from the item, the image from <enclosure> or <media:content>.
Pinterest picks up changes within 24 hours and publishes oldest first, up to 200 Pins a day.

Items live in social/pinterest-feed.json (newest last). The XML is written to
site/assets/social/auto/pinterest.xml, served at FEED_URL.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "social" / "pinterest-feed.json"
XML = ROOT / "site" / "assets" / "social" / "auto" / "pinterest.xml"
SITE = "https://starsofsabotage.com"
FEED_URL = f"{SITE}/assets/social/auto/pinterest.xml"
KEEP = 50


def card_link(card_id: str, season: int, week: int) -> str:
    """That week's leaderboard. The card ID keeps every Pin's link unique; the page ignores it."""
    return f"{SITE}/?season={season}&from={week}&to={week}&card={card_id}"


def load() -> list[dict]:
    return json.loads(ITEMS.read_text()) if ITEMS.exists() else []


def add(item: dict) -> bool:
    """Add one item unless its id is already in the feed. Returns True if added."""
    for k in ("id", "title", "description", "link", "image", "image_bytes"):
        if not item.get(k):
            raise ValueError(f"feed item missing {k}")
    if not item["link"].startswith(SITE + "/") or not item["image"].startswith(SITE + "/"):
        raise ValueError("Pinterest only accepts links on the claimed domain")
    items = load()
    if any(i["id"] == item["id"] for i in items):
        return False
    item.setdefault("published", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    items.append(item)
    ITEMS.write_text(json.dumps(items[-KEEP:], indent=1, ensure_ascii=False) + "\n")
    write()
    return True


def render(items: list[dict]) -> str:
    out = []
    for i in reversed(items):  # newest first in the file; Pinterest still publishes oldest first
        when = format_datetime(datetime.fromisoformat(i["published"]))
        out.append(
            "<item>"
            f"<title>{escape(i['title'])}</title>"
            f"<link>{escape(i['link'])}</link>"
            f"<description>{escape(i['description'])}</description>"
            f'<guid isPermaLink="false">{escape(i["id"])}</guid>'
            f"<pubDate>{when}</pubDate>"
            f'<enclosure url="{escape(i["image"])}" length="{int(i["image_bytes"])}" type="image/jpeg"/>'
            f'<media:content url="{escape(i["image"])}" medium="image" type="image/jpeg"/>'
            "</item>"
        )
    built = format_datetime(datetime.now(timezone.utc))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">'
        "<channel><title>Stars of Sabotage cards</title>"
        f"<link>{SITE}/</link>"
        "<description>Fantasy football where the worst plays score. Weekly cards from starsofsabotage.com.</description>"
        "<language>en-us</language>"
        f'<atom:link href="{FEED_URL}" rel="self" type="application/rss+xml"/>'
        f"<lastBuildDate>{built}</lastBuildDate>"
        + "".join(out) + "</channel></rss>\n"
    )


def write() -> None:
    XML.parent.mkdir(parents=True, exist_ok=True)
    XML.write_text(render(load()), encoding="utf-8")
