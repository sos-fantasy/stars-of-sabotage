"""Pipeline entry point.

    python pipeline/run.py --out dist [--prev deploy] [--force]
    python pipeline/run.py --out dist --prev deploy --backfill        # every season, 1999 on
    python pipeline/run.py --out dist --prev deploy --seasons 2010,2011

Scores the requested seasons (default: the current one) and carries every
other season forward from --prev, a checkout of the deploy branch. Then it
rebuilds the season index, the per-season totals used by the All seasons
view, meta.json, and the static pages.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export  # noqa: E402
import records  # noqa: E402
import schedule  # noqa: E402
import score  # noqa: E402
import site_build  # noqa: E402
import videos  # noqa: E402

SEASON = int(os.environ.get("SOS_SEASON", "2026"))
FIRST_SEASON = 1999   # nflverse play-by-play starts here


# The only play-by-play columns the scoring uses. Full pbp is ~372 columns per
# season; keeping it all exhausts memory during a 28-season backfill.
PBP_COLS = [
    "game_id", "play_id", "season_type", "week", "play_type", "posteam", "defteam", "home_team", "away_team",
    "td_team", "touchdown", "return_touchdown", "interception", "safety", "defensive_two_point_conv",
    "passer_player_id", "rusher_player_id", "receiver_player_id", "kicker_player_id", "kick_distance",
    "field_goal_result", "extra_point_result", "two_point_conv_result",
    "fumbled_1_player_id", "fumbled_1_team", "fumbled_2_player_id", "fumbled_2_team", "fumble_lost",
]


def load(season: int, data_dir: Path | None):
    """Return (stats, pbp, schedules). data_dir lets tests and local runs use saved parquet files."""
    if data_dir and (data_dir / f"pbp_{season}.parquet").exists():
        r = lambda n, **kw: pl.read_parquet(data_dir / f"{n}_{season}.parquet", **kw)
        return r("player_stats"), r("pbp", columns=PBP_COLS), r("schedules")
    import nflreadpy as nfl
    pbp = nfl.load_pbp(season).select(PBP_COLS)
    return nfl.load_player_stats(season), pbp, nfl.load_schedules(season)


def build_season(season: int, now: datetime, cfg: dict, data_dir: Path | None, data_out: Path) -> dict:
    """Score one season and write its files. Returns its season-index entry plus frames for meta."""
    stats, pbp, sched = load(season, data_dir)
    stats = stats.filter(pl.col("season_type") == "REG")
    if "season_type" in pbp.columns:
        pbp = pbp.filter(pl.col("season_type") == "REG")
    sched = sched.filter(pl.col("game_type") == "REG")
    stats = export.fill_missing_teams(stats, pbp)

    players = export.player_rows(score.score_players(stats, pbp, cfg))
    defense = score.score_defenses(sched, pbp, cfg)
    weeks = export.week_table(sched, now)
    _write(data_out / f"scores-{season}.json", export.compact(players, export.PLAYER_COLS))
    _write(data_out / f"defense-{season}.json", export.compact(defense, export.DEF_COLS))
    _write(data_out / f"games-{season}.json", export.games(sched))
    played = [w for w in weeks if w["status"] != "upcoming"]
    entry = {
        "season": season,
        "weeks": len(weeks),
        "latest_week": max((w["week"] for w in played), default=None),
        "status": "final" if weeks and all(w["status"] == "final" for w in weeks) else "in_progress",
        "scoring_version": cfg["version"],
    }
    print(f"[season {season}] {players.height} player-weeks, {defense.height} defense-weeks, {entry['status']}", flush=True)
    return {"entry": entry, "weeks": weeks, "players": players, "defense": defense, "stats": stats}


def _build_entry(season, now, cfg, data_dir, data_out) -> dict:
    """Worker for past seasons: build, write files, return only the small index entry."""
    return build_season(season, now, cfg, data_dir, data_out)["entry"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--prev", default=None, help="checkout of the deploy branch")
    ap.add_argument("--force", action="store_true", help="run even if nothing is scheduled this hour")
    ap.add_argument("--backfill", action="store_true", help=f"rebuild every season from {FIRST_SEASON}")
    ap.add_argument("--seasons", default="", help="comma-separated seasons to rebuild")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--now", default=None, help="ISO time override, for testing")
    a = ap.parse_args(argv)

    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    now_et = now.astimezone(schedule.ET)

    if not (a.force or a.backfill or a.seasons):
        import nflreadpy as nfl
        sched = nfl.load_schedules(SEASON)
        game_dates = {datetime.fromisoformat(d).date() for d in sched["gameday"].to_list()}
        due, why = schedule.is_due(now_et, game_dates)
        print(f"[schedule] {now_et:%a %Y-%m-%d %H:%M} ET: {why}")
        if not due:
            _set_output("ran", "false")
            return 0

    out = Path(a.out)
    data_out = out / "data"
    data_out.mkdir(parents=True, exist_ok=True)
    data_dir = Path(a.data_dir) if a.data_dir else None
    prev_data = Path(a.prev) / "data" if a.prev else None
    cfg = score.load_config()

    if a.backfill:
        todo = list(range(FIRST_SEASON, SEASON + 1))
    elif a.seasons:
        todo = sorted({int(s) for s in a.seasons.split(",") if s.strip()} | {SEASON})
    else:
        todo = [SEASON]

    # Carry forward seasons we are not rebuilding.
    prev_index = {s["season"]: s for s in _read_json(prev_data / "seasons.json", []) } if prev_data else {}
    index = {}
    for season, entry in prev_index.items():
        if season in todo:
            continue
        ok = True
        for name in (f"scores-{season}.json", f"defense-{season}.json", f"games-{season}.json"):
            src = prev_data / name
            if src.exists():
                shutil.copy2(src, data_out / name)
            else:
                ok = False
        if ok:
            index[season] = entry
        else:
            print(f"[info] season {season} is missing files in the previous deploy; it will be rebuilt")

    # Self-heal: rebuild any season the previous deploy did not have.
    missing = [s for s in range(FIRST_SEASON, SEASON + 1) if s not in index and s not in todo]
    if missing:
        print(f"[backfill] rebuilding {len(missing)} missing seasons: {missing[0]}-{missing[-1]}")
        todo = sorted(set(todo) | set(missing))

    # Past seasons build in a fresh process each, so memory is returned to the OS
    # after every season (a 28-season backfill otherwise climbs past 6 GB).
    # The current season builds here, since its frames feed meta and stories.
    import multiprocessing as mp
    past = [s for s in todo if s != SEASON]
    if past:
        ctx = mp.get_context("spawn")
        with ctx.Pool(1, maxtasksperchild=1) as pool:
            for entry in pool.starmap(_build_entry, [(s, now, cfg, data_dir, data_out) for s in past]):
                index[entry["season"]] = entry
    current = build_season(SEASON, now, cfg, data_dir, data_out)
    index[SEASON] = current["entry"]

    seasons = [index[s] for s in sorted(index, reverse=True)]
    _write(data_out / "seasons.json", seasons)

    # Season totals for every season present, for the All seasons view.
    ps, ds = export.season_totals(data_out, [s["season"] for s in seasons])
    _write(data_out / "player-seasons.json", ps)
    _write(data_out / "defense-seasons.json", ds)
    pc, dc = export.career_totals(ps, ds)
    _write(data_out / "player-careers.json", pc)
    _write(data_out / "defense-careers.json", dc)
    pfiles, search = export.player_files(data_out, [s["season"] for s in seasons])
    pdir = data_out / "players"
    pdir.mkdir(exist_ok=True)
    for pid, obj in pfiles.items():
        _write(pdir / f"{pid}.json", obj)
    _write(data_out / "search.json", search)

    weeks = current["weeks"]
    played = [w for w in weeks if w["status"] in ("final", "provisional", "in_progress")]
    latest = max((w["week"] for w in played), default=None)
    # Weekly awards need a real sample: use the latest week once at least half its games are done.
    ready = [w["week"] for w in played if w["games_done"] * 2 >= w["games"]]
    story_week = max(ready, default=None)
    story_list = (export.highlights(SEASON, story_week, current["players"], current["stats"], current["defense"], cfg)
                  if story_week else [])

    h = export.data_hash(
        _read_json(data_out / f"scores-{SEASON}.json"), _read_json(data_out / f"defense-{SEASON}.json"),
        weeks, story_list, cfg, seasons,
    )
    prev_meta = _read_json(prev_data / "meta.json", {}) if prev_data else {}
    updated_at = prev_meta.get("updated_at") if prev_meta.get("data_hash") == h else now.isoformat(timespec="seconds")

    meta = {
        "season": SEASON,
        "first_season": min(index),
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
    # Worst-plays videos. Network trouble never fails the run: earlier videos carry forward.
    prev_videos = _read_json(prev_data / "videos.json", {}) if prev_data else {}
    try:
        vids = videos.build(SEASON, export_rows(_read_json(data_out / f"games-{SEASON}.json")),
                            prev_videos.get("videos", []), videos.load_sources(), videos.read_manual())
    except Exception as e:
        print(f"[videos] skipped: {e}")
        vids = prev_videos.get("videos", [])
    _write(data_out / "videos.json", {"videos": vids, "play_on_site": videos.play_on_site()})

    recs = records.build(data_out, [s["season"] for s in seasons], cfg, SEASON, weeks)
    # Record alerts on the home page: anything still pending corrections, plus any
    # record (pending or official) set in the week the report covers.
    meta["highlights"]["records"] = [a for a in recs["alerts"]
                                     if not a["official"] or a["week"] == story_week]
    _write(data_out / "meta.json", meta)
    _write(data_out / "records.json", recs)
    site_build.build(out, noindex=os.environ.get("SOS_NOINDEX", "1") == "1", records=recs,
                     boot={"meta": meta, "seasons": seasons})

    print(f"[done] seasons {min(index)}-{max(index)} ({len(index)}), rebuilt {todo[0]}"
          f"{'-' + str(todo[-1]) if len(todo) > 1 else ''}, latest week {latest}, "
          f"data {'unchanged' if updated_at == prev_meta.get('updated_at') else 'changed'} ({h})")
    _set_output("ran", "true")
    return 0


def export_rows(compact_obj) -> list[dict]:
    """Expand a {cols, rows} file into a list of dicts."""
    if not compact_obj:
        return []
    return [dict(zip(compact_obj["cols"], r)) for r in compact_obj["rows"]]


def _read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return default


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def _set_output(k: str, v: str) -> None:
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a") as fh:
            fh.write(f"{k}={v}\n")


if __name__ == "__main__":
    sys.exit(main())
