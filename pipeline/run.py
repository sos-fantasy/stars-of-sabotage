"""Pipeline entry point.

    python pipeline/run.py --out dist [--prev deploy] [--force] [--data-dir DIR]

Fetches nflverse data for the season, scores it, writes dist/data/*.json,
and renders the static site into dist/. With --prev pointing at a checkout
of the deploy branch, it keeps the previous `updated_at` when the data did
not change, so reruns do not create noise commits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export  # noqa: E402
import schedule  # noqa: E402
import score  # noqa: E402
import site_build  # noqa: E402

SEASON = int(os.environ.get("SOS_SEASON", "2026"))


def load(season: int, data_dir: Path | None):
    """Return (stats, pbp, schedules). data_dir lets tests and local runs use saved parquet files."""
    if data_dir:
        r = lambda n: pl.read_parquet(data_dir / f"{n}_{season}.parquet")
        return r("player_stats"), r("pbp"), r("schedules")
    import nflreadpy as nfl
    sched = nfl.load_schedules(season)
    return nfl.load_player_stats(season), nfl.load_pbp(season), sched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--prev", default=None, help="checkout of the deploy branch")
    ap.add_argument("--force", action="store_true", help="run even if nothing is scheduled this hour")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--now", default=None, help="ISO time override, for testing")
    a = ap.parse_args(argv)

    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    now_et = now.astimezone(schedule.ET)

    if not a.force:
        import nflreadpy as nfl
        sched = nfl.load_schedules(SEASON)
        game_dates = {datetime.fromisoformat(d).date() for d in sched["gameday"].to_list()}
        due, why = schedule.is_due(now_et, game_dates)
        print(f"[schedule] {now_et:%a %Y-%m-%d %H:%M} ET: {why}")
        if not due:
            _set_output("ran", "false")
            return 0

    data_dir = Path(a.data_dir) if a.data_dir else None
    stats, pbp, sched = load(SEASON, data_dir)
    stats = stats.filter(pl.col("season_type") == "REG")
    pbp = pbp.filter(pl.col("season_type") == "REG") if "season_type" in pbp.columns else pbp
    cfg = score.load_config()

    players = export.player_rows(score.score_players(stats, pbp, cfg))
    defense = score.score_defenses(sched.filter(pl.col("game_type") == "REG"), pbp, cfg)
    weeks = export.week_table(sched, now)

    scores_json = export.compact(players, export.PLAYER_COLS)
    def_json = export.compact(defense, export.DEF_COLS)

    played = [w for w in weeks if w["status"] in ("final", "provisional", "in_progress")]
    latest = max((w["week"] for w in played), default=None)
    # Weekly awards need a real sample: use the latest week once at least half its games are done.
    ready = [w["week"] for w in played if w["games_done"] * 2 >= w["games"]]
    story_week = max(ready, default=None)
    story_list = export.highlights(SEASON, story_week, players, stats, defense, cfg) if story_week else []

    h = export.data_hash(scores_json, def_json, weeks, story_list, cfg)
    prev_meta = _read_prev_meta(a.prev)
    updated_at = prev_meta.get("updated_at") if prev_meta.get("data_hash") == h else now.isoformat(timespec="seconds")

    meta = {
        "season": SEASON,
        "scoring_version": cfg["version"],
        "updated_at": updated_at,
        "checked_on": now_et.date().isoformat(),
        "data_hash": h,
        "latest_week": latest,
        "weeks": weeks,
        "highlights": {"week": story_week, "status": next((w["status"] for w in weeks if w["week"] == story_week), None),
                       "stories": story_list},
        "source": "nflverse (CC BY 4.0)",
    }

    out = Path(a.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    _write(out / "data" / f"scores-{SEASON}.json", scores_json)
    _write(out / "data" / f"defense-{SEASON}.json", def_json)
    _write(out / "data" / "meta.json", meta)
    site_build.build(out, noindex=os.environ.get("SOS_NOINDEX", "1") == "1")

    print(f"[done] {players.height} player-weeks, {defense.height} defense-weeks, latest week {latest}, "
          f"data {'unchanged' if updated_at == prev_meta.get('updated_at') else 'changed'} ({h})")
    _set_output("ran", "true")
    return 0


def _read_prev_meta(prev: str | None) -> dict:
    if not prev:
        return {}
    p = Path(prev) / "data" / "meta.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def _set_output(k: str, v: str) -> None:
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a") as fh:
            fh.write(f"{k}={v}\n")


if __name__ == "__main__":
    sys.exit(main())
