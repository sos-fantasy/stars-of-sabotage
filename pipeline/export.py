"""Turn scored frames into the compact JSON files the static site reads."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

import polars as pl

import schedule
import stories

PLAYER_POSITIONS = ["QB", "RB", "FB", "WR", "TE", "K"]

# Column order for scores/{season}.json. The site reads these by name.
PLAYER_COLS = [
    "player_id", "player_display_name", "position", "team", "opponent_team", "week",
    "n_incomplete", "n_sacks", "n_carries", "n_receptions", "n_fumbles", "n_fumbles_lost",
    "n_ints", "n_pick_sixes", "n_fg_missed", "n_pat_missed",
    "pts_incomplete", "pts_sacks", "pts_carries", "pts_receptions", "pts_fumble", "pts_fumble_lost",
    "pts_int", "pts_pick_six", "pts_kicking", "sabotage_pts",
]
SUM_COLS = [c for c in PLAYER_COLS if c.startswith(("n_", "pts_"))] + ["sabotage_pts"]
DEF_COLS = ["team", "opponent", "week", "opp_score", "points_allowed", "pa_bucket", "sabotage_pts"]


def player_rows(scored: pl.DataFrame) -> pl.DataFrame:
    fgm = [c for c in scored.columns if c.startswith("n_fgm_")]
    return (
        scored.filter(pl.col("position").is_in(PLAYER_POSITIONS))
        .with_columns(pl.sum_horizontal(fgm).alias("n_fg_missed"))
        .with_columns(pl.col(c).cast(pl.Int64) for c in PLAYER_COLS if c.startswith(("n_", "pts_")) or c == "sabotage_pts")
        .select(PLAYER_COLS)
        .sort(["week", "sabotage_pts", "player_display_name"], descending=[False, True, False])
    )


def fill_missing_teams(stats: pl.DataFrame, pbp: pl.DataFrame) -> pl.DataFrame:
    """A few old stat rows have no team (e.g. Steve Bono, 1999 week 9). Recover it from
    the play-by-play: the offense on plays where he passed, ran, or caught the ball."""
    if stats["team"].null_count() == 0:
        return stats
    parts = [pbp.select("game_id", pl.col(c).alias("player_id"), pl.col("posteam").alias("t"))
             for c in ("passer_player_id", "rusher_player_id", "receiver_player_id") if c in pbp.columns]
    seen = (pl.concat(parts).drop_nulls().group_by(["game_id", "player_id"])
            .agg(pl.col("t").mode().first().alias("t_pbp")))
    games = pbp.select("game_id", "home_team", "away_team").unique("game_id")
    out = (stats.join(seen, on=["game_id", "player_id"], how="left").join(games, on="game_id", how="left")
           .with_columns(pl.coalesce("team", "t_pbp").alias("team")))
    out = out.with_columns(
        pl.when(pl.col("opponent_team").is_null() & pl.col("team").is_not_null())
        .then(pl.when(pl.col("team") == pl.col("home_team")).then(pl.col("away_team")).otherwise(pl.col("home_team")))
        .otherwise(pl.col("opponent_team")).alias("opponent_team"))
    return out.drop("t_pbp", "home_team", "away_team")


def season_totals(data_dir, seasons: list[int]) -> tuple[dict, dict]:
    """Per player-season and defense-season totals from the season files, for the All seasons view."""
    from pathlib import Path
    data_dir = Path(data_dir)
    prow, drow = [], []
    for s in seasons:
        p = json.loads((data_dir / f"scores-{s}.json").read_text())
        df = pl.DataFrame(p["rows"], schema=p["cols"], orient="row")
        agg = (df.sort("week").group_by("player_id", maintain_order=True)
               .agg(pl.col("player_display_name").last(), pl.col("position").last(), pl.col("team").last(),
                    pl.len().alias("g"), *[pl.col(c).sum() for c in SUM_COLS])
               .with_columns(pl.lit(s).alias("season")))
        prow.append(agg)
        d = json.loads((data_dir / f"defense-{s}.json").read_text())
        dd = pl.DataFrame(d["rows"], schema=d["cols"], orient="row")
        drow.append(dd.group_by("team").agg(pl.len().alias("g"), pl.col("points_allowed").sum(),
                                            pl.col("sabotage_pts").sum()).with_columns(pl.lit(s).alias("season")))
    pcols = ["season", "player_id", "player_display_name", "position", "team", "g"] + SUM_COLS
    dcols = ["season", "team", "g", "points_allowed", "sabotage_pts"]
    P = pl.concat(prow).select(pcols).sort(["season", "sabotage_pts"], descending=[True, True])
    D = pl.concat(drow).select(dcols).sort(["season", "sabotage_pts"], descending=[True, True])
    return compact(P, pcols), compact(D, dcols)


def compact(df: pl.DataFrame, cols: list[str]) -> dict:
    return {"cols": cols, "rows": df.select(cols).rows()}


def week_table(schedules: pl.DataFrame, now: datetime) -> list[dict]:
    reg = schedules.filter(pl.col("game_type") == "REG")
    out = []
    for wk in sorted(reg["week"].unique().to_list()):
        g = reg.filter(pl.col("week") == wk)
        done = g.filter(pl.col("home_score").is_not_null())
        days = [date.fromisoformat(d) for d in g["gameday"].to_list()]
        last = max(date.fromisoformat(d) for d in done["gameday"].to_list()) if done.height else None
        status = schedule.week_status(now, g.height, done.height, max(days) if done.height == g.height else last)
        row = {"week": wk, "games": g.height, "games_done": done.height,
               "first_day": min(days).isoformat(), "last_day": max(days).isoformat(), "status": status}
        if status == "provisional":
            row["final_at"] = schedule.final_at(max(days)).isoformat()
        out.append(row)
    return out


def data_hash(*payloads) -> str:
    h = hashlib.sha256()
    for p in payloads:
        h.update(json.dumps(p, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:16]


def highlights(season: int, week: int, players: pl.DataFrame, stats: pl.DataFrame,
               defenses: pl.DataFrame, cfg: dict) -> list[dict]:
    extra = stats.select("player_id", "week", "fg_missed_list", "fg_blocked_list")
    p = (players.filter(pl.col("week") == week)
         .join(extra, on=["player_id", "week"], how="left")
         .with_columns(pl.lit(cfg["offense"]["interception_thrown"] + cfg["offense"]["pick_six_thrown"]).alias("p6_value"),
                       (pl.col("pts_fumble") + pl.col("pts_fumble_lost")).alias("pts_fumbles")))
    d = defenses.filter(pl.col("week") == week)
    return stories.build(week, p.to_dicts(), d.to_dicts(), season)
