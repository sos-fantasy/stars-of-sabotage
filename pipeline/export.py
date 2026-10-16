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
    "pts_incomplete", "pts_sacks", "pts_carries", "pts_receptions", "pts_fumbles", "pts_ints",
    "pts_kicking", "sabotage_pts",
]
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
         .with_columns(pl.lit(cfg["offense"]["interception_thrown"] + cfg["offense"]["pick_six_thrown"]).alias("p6_value")))
    d = defenses.filter(pl.col("week") == week)
    return stories.build(week, p.to_dicts(), d.to_dicts(), season)
