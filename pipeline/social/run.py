"""Scheduled social posting: build every card that is due now.

  python pipeline/social/run.py build --data live/data [--now 2026-11-16T09:05-05:00] [--card ID]
      Builds due cards. dry-run cards go to social/outbox/<id>/; live cards also
      get site/assets/social/auto/<id>.jpg and are listed in social/pending.json.
  python pipeline/social/run.py publish
      For each pending card: waits until its JPEG is live on the site, posts to
      every platform not yet done, records results in social/posted.json.

Any card that fails a check is skipped and the command exits 1, so GitHub emails
the owner. Nothing half-built is ever posted.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_html  # noqa: E402
import post_times as schedule  # noqa: E402
import top7  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOCIAL = ROOT / "social"
OUTBOX = SOCIAL / "outbox"
POSTED = SOCIAL / "posted.json"
PENDING = SOCIAL / "pending.json"
AUTO = ROOT / "site" / "assets" / "social" / "auto"
SITE = "https://starsofsabotage.com/assets/social/auto/"


def _json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def config() -> dict:
    return yaml.safe_load((SOCIAL / "config.yml").read_text())


def done_ids() -> set[str]:
    ids = set(_json(POSTED, {}).keys())
    if OUTBOX.exists():
        ids |= {p.name for p in OUTBOX.iterdir() if p.is_dir()}
    return ids


def build_card(slot: dict, data: dict, season: int) -> dict:
    if slot["type"] == "game":
        game = next(g for g in data["games"] if g["game_id"] == slot["game_id"])
        return top7.game_card(data, game, season)
    return top7.wreckage_card(data, season, slot["week"])


def write_outbox(card: dict, mode: str) -> Path:
    from render import render_fit  # playwright only needed when building

    d = OUTBOX / card["id"]
    d.mkdir(parents=True, exist_ok=True)
    trim = render_fit(lambda t: card_html.top_card(card, t), d / "card.jpg")
    caps = top7.captions(card)
    for platform, text in caps.items():
        (d / f"{platform}.txt").write_text(text + "\n", encoding="utf-8")
    meta = {
        "id": card["id"], "type": card["type"], "season": card["season"], "week": card["week"],
        "status": card["status"], "mode": mode, "trim": trim,
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": [{"rank": r["rank"], "name": r["name"], "team": r["team"], "pts": r["pts"]} for r in card["rows"]],
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    return d


def cmd_build(a) -> int:
    cfg = config()
    meta = json.loads((Path(a.data) / "meta.json").read_text())
    season = int(a.season or meta.get("season") or meta.get("current_season"))
    data = top7.load(Path(a.data), season)
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    all_slots = schedule.slots(data["games"], season)
    todo = [s for s in all_slots if s["id"] == a.card] if a.card else schedule.due(all_slots, now, done_ids())
    todo = [t for t in todo if cfg["mode"].get(t["type"], "off") != "off"]
    print(f"{now.isoformat(timespec='minutes')}: {len(todo)} card(s) due: {', '.join(t['id'] for t in todo) or 'none'}")
    if a.plan:
        import os
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"due={len(todo)}\n")
        return 0
    failures, pending = 0, _json(PENDING, [])
    for slot in todo:
        mode = cfg["mode"].get(slot["type"], "off")
        if mode == "off":
            continue
        try:
            card = build_card(slot, data, season)
            d = write_outbox(card, mode)
            print(f"built {card['id']} ({mode}) -> {d.relative_to(ROOT)}")
            if mode == "live":
                AUTO.mkdir(parents=True, exist_ok=True)
                shutil.copy(d / "card.jpg", AUTO / f"{card['id']}.jpg")
                if card["id"] not in pending:
                    pending.append(card["id"])
                if cfg.get("pinterest_feed") and (d / "pinterest.txt").exists():
                    import feed
                    pin = json.loads((d / "pinterest.txt").read_text(encoding="utf-8"))
                    feed.add({"id": card["id"], "title": pin["title"], "description": pin["description"],
                              "link": feed.card_link(card["id"], card["season"], card["week"]),
                              "image": SITE + f"{card['id']}.jpg", "image_bytes": (d / "card.jpg").stat().st_size})
        except top7.CardError as e:
            # Data not ready (no final score yet) is normal early in the window: retry next hour.
            print(f"skip {slot['id']}: {e}")
            if "no final score" not in str(e) and "not all final" not in str(e) and "missing" not in str(e):
                failures += 1
        except Exception:
            traceback.print_exc()
            failures += 1
    PENDING.write_text(json.dumps(pending, indent=1) + "\n") if pending else PENDING.unlink(missing_ok=True)
    return 1 if failures else 0


def _live(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
            return r.status == 200 and "jpeg" in r.headers.get("Content-Type", "")
    except Exception:
        return False


FETCH_ERRORS = ("2207052", "2069019")


def _retry_fetch(post, label: str, tries: int = 3, pause: int = 60):
    """Instagram and Facebook sometimes cannot download a just-hosted image while Hostinger's cache
    warms. Instagram: subcode 2207052 (Nov 16, 2026). Facebook: code 324, subcode 2069019,
    "Missing or invalid image file", marked is_transient (Nov 23 and 26, 2026; the next run worked).
    Retry only those."""
    for n in range(1, tries + 1):
        try:
            return post()
        except SystemExit as e:
            if not any(code in str(e) for code in FETCH_ERRORS) or n == tries:
                raise
            print(f"{label}: image download failed on try {n}; retrying in {pause}s")
            time.sleep(pause)


def cmd_publish(a) -> int:
    import meta  # needs tokens in the environment

    pending, posted, cfg = _json(PENDING, []), _json(POSTED, {}), config()
    failures = 0
    for cid in list(pending):
        if all(pl in posted.get(cid, {}) for pl in cfg["platforms"]):
            print(f"{cid}: already posted on every platform; dropping from pending")
            pending.remove(cid)
            continue
        url = SITE + f"{cid}.jpg"
        # Instagram fetches the image itself, so wait for two good reads in a row (one check per
        # round). A single re-check right after one success failed on Nov 16 while the cache warmed.
        deadline, good = time.time() + a.wait, 0
        while good < 2 and time.time() < deadline:
            good = good + 1 if _live(url) else 0
            if good < 2:
                time.sleep(30)
        if good < 2:
            print(f"{cid}: image not live yet at {url}; will retry next run")
            continue
        rec = posted.setdefault(cid, {})
        for platform in cfg["platforms"]:
            if platform in rec:
                continue
            cap_file = OUTBOX / cid / f"{platform}.txt"
            if not cap_file.exists():
                print(f"{cid} {platform}: no caption file (card built before {platform} was added); skipped")
                rec[platform] = {"skipped": "no caption"}
                continue
            caption = cap_file.read_text(encoding="utf-8").strip()
            try:
                if platform == "pinterest":
                    import pinterest
                    out = pinterest.publish_pinterest(url, json.loads(caption))
                else:
                    fn = {"instagram": meta.publish_instagram, "facebook": meta.publish_facebook}[platform]
                    out = _retry_fetch(lambda: fn(url, caption), f"{cid} {platform}")
                rec[platform] = out | {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            except SystemExit as e:
                print(f"{cid} {platform}: {e}")
                failures += 1
        if all(p in rec for p in cfg["platforms"]):
            pending.remove(cid)
        POSTED.write_text(json.dumps(posted, indent=1) + "\n")
    PENDING.write_text(json.dumps(pending, indent=1) + "\n") if pending else PENDING.unlink(missing_ok=True)
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--data", required=True)
    b.add_argument("--season", type=int)
    b.add_argument("--now")
    b.add_argument("--card")
    b.add_argument("--plan", action="store_true", help="only report what is due; build nothing")
    p = sub.add_parser("publish")
    p.add_argument("--wait", type=int, default=1200, help="seconds to wait for the image to go live")
    a = ap.parse_args(argv)
    return cmd_build(a) if a.cmd == "build" else cmd_publish(a)


if __name__ == "__main__":
    sys.exit(main())
