"""Sabotage scoring engine.

Point values and interpretation switches come from config/scoring.yml.
Inputs are nflverse frames (polars): weekly player stats, play-by-play,
and schedules. Field names verified against nflreadpy 0.1.5, 2026 data.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scoring.yml"
FG_BUCKETS = ["0-19", "20-29", "30-39", "40-49", "50+"]


def load_config(path: Path | str = CONFIG_PATH, **overrides) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    cfg["interpretation"] = {**cfg.get("interpretation", {}), **overrides}
    return cfg


def fg_bucket(distance: float) -> str:
    if distance < 20:
        return "0-19"
    if distance < 30:
        return "20-29"
    if distance < 40:
        return "30-39"
    if distance < 50:
        return "40-49"
    return "50+"


def pick_sixes(pbp: pl.DataFrame) -> pl.DataFrame:
    """Pick sixes thrown, per passer per game."""
    return (
        pbp.filter((pl.col("interception") == 1) & (pl.col("return_touchdown") == 1))
        .group_by(["game_id", "passer_player_id"])
        .agg(pl.len().cast(pl.Int64).alias("pick_sixes"))
        .rename({"passer_player_id": "player_id"})
    )


def blocked_kicks(pbp: pl.DataFrame) -> pl.DataFrame:
    """Blocked FGs by distance bucket and blocked PATs, per kicker per game."""
    b = pbp.filter(
        (pl.col("field_goal_result") == "blocked") | (pl.col("extra_point_result") == "blocked")
    )
    rows = []
    for r in b.iter_rows(named=True):
        row = {"game_id": r["game_id"], "player_id": r["kicker_player_id"], "pat_blocked_pbp": 0}
        row.update({f"fgb_{k}": 0 for k in FG_BUCKETS})
        if r["field_goal_result"] == "blocked":
            row[f"fgb_{fg_bucket(r['kick_distance'])}"] = 1
        else:
            row["pat_blocked_pbp"] = 1
        rows.append(row)
    cols = ["game_id", "player_id", "pat_blocked_pbp"] + [f"fgb_{k}" for k in FG_BUCKETS]
    if not rows:
        return pl.DataFrame(schema={c: (pl.Utf8 if c in ("game_id", "player_id") else pl.Int64) for c in cols})
    return pl.DataFrame(rows).group_by(["game_id", "player_id"]).agg(pl.all().sum())


SCRIMMAGE_PLAYS = ["pass", "run", "qb_kneel", "qb_spike"]
RETURN_PLAYS = ["kickoff", "punt"]


def fumbles(pbp: pl.DataFrame, include_returns: bool) -> pl.DataFrame:
    """Fumbles per fumbler per game from play-by-play.

    Scrimmage fumbles count when the fumbler's team had the ball. This catches
    aborted and dropped snaps, which nflverse leaves out of the sack, rushing,
    and receiving fumble columns. A lost fumble is credited to the last player
    on the first fumbler's team to fumble on the play, so a defender who
    fumbles after a recovery never takes it. Position filtering happens in
    score_players.
    """
    cols = {"game_id": pl.Utf8, "player_id": pl.Utf8, "fum": pl.Int64, "fum_lost": pl.Int64}
    kinds = SCRIMMAGE_PLAYS + (RETURN_PLAYS if include_returns else [])
    parts = []
    same_team_2 = pl.col("fumbled_2_player_id").is_not_null() & (pl.col("fumbled_2_team") == pl.col("fumbled_1_team"))
    for slot in ("1", "2"):
        last = ~same_team_2 if slot == "1" else same_team_2
        keep = pl.col(f"fumbled_{slot}_player_id").is_not_null() & pl.col("play_type").is_in(kinds)
        scrim_ok = pl.col("play_type").is_in(RETURN_PLAYS) | (pl.col(f"fumbled_{slot}_team") == pl.col("posteam"))
        parts.append(
            pbp.filter(keep & scrim_ok).select(
                "game_id",
                pl.col(f"fumbled_{slot}_player_id").alias("player_id"),
                pl.lit(1, dtype=pl.Int64).alias("fum"),
                pl.when(last & (pl.col("fumble_lost") == 1)).then(1).otherwise(0).cast(pl.Int64).alias("fum_lost"),
            )
        )
    df = pl.concat(parts) if parts else pl.DataFrame(schema=cols)
    if df.is_empty():
        return pl.DataFrame(schema=cols)
    return df.group_by(["game_id", "player_id"]).agg(pl.col("fum").sum(), pl.col("fum_lost").sum())


def score_players(stats: pl.DataFrame, pbp: pl.DataFrame, cfg: dict) -> pl.DataFrame:
    o, k, it = cfg["offense"], cfg["kicker"], cfg["interpretation"]
    df = (
        stats.join(pick_sixes(pbp), on=["game_id", "player_id"], how="left")
        .join(blocked_kicks(pbp), on=["game_id", "player_id"], how="left")
        .join(fumbles(pbp, it["fumble_scope"] == "scrimmage_and_returns"), on=["game_id", "player_id"], how="left")
        .fill_null(0)
    )
    eligible = pl.col("position").is_in(it["fumble_positions"])
    fum = pl.when(eligible).then(pl.col("fum")).otherwise(0)
    fum_lost = pl.when(eligible).then(pl.col("fum_lost")).otherwise(0)
    miss = {
        "0-19": pl.col("fg_missed_0_19"),
        "20-29": pl.col("fg_missed_20_29"),
        "30-39": pl.col("fg_missed_30_39"),
        "40-49": pl.col("fg_missed_40_49"),
        "50+": pl.col("fg_missed_50_59") + pl.col("fg_missed_60_"),
    }
    pat_miss = pl.col("pat_missed")
    if it["blocked_kicks_are_misses"]:
        miss = {b: e + pl.col(f"fgb_{b}") for b, e in miss.items()}
        pat_miss = pat_miss + pl.col("pat_blocked_pbp")

    df = df.with_columns(
        (pl.col("attempts") - pl.col("completions")).alias("n_incomplete"),
        pl.col("sacks_suffered").alias("n_sacks"),
        pl.col("carries").alias("n_carries"),
        pl.col("receptions").alias("n_receptions"),
        fum.alias("n_fumbles"),
        fum_lost.alias("n_fumbles_lost"),
        pl.col("passing_interceptions").alias("n_ints"),
        pl.col("pick_sixes").alias("n_pick_sixes"),
        pat_miss.alias("n_pat_missed"),
        *[e.alias(f"n_fgm_{b}") for b, e in miss.items()],
    )
    # Without stacking, a lost fumble scores only fumble_lost and a pick six only pick_six.
    fum_scored = pl.col("n_fumbles") if it["stack_fumble_lost"] else pl.col("n_fumbles") - pl.col("n_fumbles_lost")
    int_scored = pl.col("n_ints") if it["stack_pick_six"] else pl.col("n_ints") - pl.col("n_pick_sixes")
    comps = {
        "pts_incomplete": pl.col("n_incomplete") * o["incomplete_pass"],
        "pts_sacks": pl.col("n_sacks") * o["sack_taken"],
        "pts_carries": pl.col("n_carries") * o["rush_attempt"],
        "pts_receptions": pl.col("n_receptions") * o["reception"],
        "pts_fumbles": fum_scored * o["fumble"] + pl.col("n_fumbles_lost") * o["fumble_lost"],
        "pts_ints": int_scored * o["interception_thrown"] + pl.col("n_pick_sixes") * o["pick_six_thrown"],
        "pts_kicking": sum(pl.col(f"n_fgm_{b}") * k["fg_missed"][b] for b in FG_BUCKETS)
        + pl.col("n_pat_missed") * k["pat_missed"],
    }
    df = df.with_columns(**comps)
    df = df.with_columns(pl.sum_horizontal(list(comps)).alias("sabotage_pts"), pl.lit(cfg["version"]).alias("scoring_version"))
    keep = ["player_id", "player_display_name", "position", "season", "week", "game_id", "team", "opponent_team"]
    ncols = [c for c in df.columns if c.startswith("n_")]
    return df.select(keep + ncols + list(comps) + ["sabotage_pts", "scoring_version"])


def non_offensive_points(pbp: pl.DataFrame) -> pl.DataFrame:
    """Points each team scored per game without its offense: return TDs, defensive
    TDs, safeties, defensive two-point returns, plus the try after those TDs."""
    plays = pbp.sort(["game_id", "play_id"]).to_dicts()
    pts: dict[tuple[str, str], int] = {}
    for i, p in enumerate(plays):
        team = None
        add = 0
        if p.get("touchdown") == 1 and p.get("td_team") and (
            p.get("return_touchdown") == 1 or p["td_team"] != p.get("posteam")
        ):
            team, add = p["td_team"], 6
            nxt = plays[i + 1] if i + 1 < len(plays) and plays[i + 1]["game_id"] == p["game_id"] else None
            if nxt:
                if nxt.get("extra_point_result") == "good":
                    add += 1
                elif nxt.get("two_point_conv_result") == "success":
                    add += 2
        elif p.get("safety") == 1 and p.get("defteam"):
            team, add = p["defteam"], 2
        elif p.get("defensive_two_point_conv") == 1 and p.get("defteam"):
            team, add = p["defteam"], 2
        if team:
            pts[(p["game_id"], team)] = pts.get((p["game_id"], team), 0) + add
    return pl.DataFrame(
        [{"game_id": g, "team": t, "non_off_pts": v} for (g, t), v in pts.items()],
        schema={"game_id": pl.Utf8, "team": pl.Utf8, "non_off_pts": pl.Int64},
    )


def yahoo_excluded_points(pbp: pl.DataFrame) -> pl.DataFrame:
    """Points a team scored that Yahoo leaves out of its opponent's Points Allowed
    (help.yahoo.com/kb/SLN6441.html, read October 15, 2026): interception and
    fumble return TDs on scrimmage plays, blocked field goal return TDs, all
    safeties, and defensive two-point returns. Kick and punt return TDs and all
    PATs still count, so the try after an excluded TD is not removed."""
    scrim = pl.col("play_type").is_in(SCRIMMAGE_PLAYS)
    blocked_fg = (pl.col("play_type") == "field_goal") & (pl.col("field_goal_result") == "blocked")
    def_td = (pl.col("touchdown") == 1) & pl.col("td_team").is_not_null() & (pl.col("td_team") == pl.col("defteam")) & (scrim | blocked_fg)
    parts = [
        pbp.filter(def_td).select("game_id", pl.col("td_team").alias("team"), pl.lit(6, dtype=pl.Int64).alias("excl_pts")),
        pbp.filter(pl.col("safety") == 1).select("game_id", pl.col("defteam").alias("team"), pl.lit(2, dtype=pl.Int64).alias("excl_pts")),
        pbp.filter(pl.col("defensive_two_point_conv") == 1).select(
            "game_id", pl.col("defteam").alias("team"), pl.lit(2, dtype=pl.Int64).alias("excl_pts")),
    ]
    return pl.concat(parts).group_by(["game_id", "team"]).agg(pl.col("excl_pts").sum())


def pa_points(points_allowed: int, table: dict) -> tuple[str, int]:
    if points_allowed <= 0:
        return "0", table["0"]
    for label, val in table.items():
        if label == "0":
            continue
        if label.endswith("+"):
            if points_allowed >= int(label[:-1]):
                return label, val
        else:
            lo, hi = map(int, label.split("-"))
            if lo <= points_allowed <= hi:
                return label, val
    raise ValueError(points_allowed)


def score_defenses(schedules: pl.DataFrame, pbp: pl.DataFrame, cfg: dict) -> pl.DataFrame:
    g = schedules.filter(pl.col("home_score").is_not_null())
    sides = pl.concat([
        g.select("game_id", "season", "week", pl.col("home_team").alias("team"),
                 pl.col("away_team").alias("opponent"), pl.col("away_score").alias("opp_score")),
        g.select("game_id", "season", "week", pl.col("away_team").alias("team"),
                 pl.col("home_team").alias("opponent"), pl.col("home_score").alias("opp_score")),
    ])
    nop = non_offensive_points(pbp).rename({"team": "opponent", "non_off_pts": "opp_non_off_pts"})
    yex = yahoo_excluded_points(pbp).rename({"team": "opponent", "excl_pts": "opp_yahoo_excluded"})
    sides = (
        sides.join(nop, on=["game_id", "opponent"], how="left")
        .join(yex, on=["game_id", "opponent"], how="left")
        .fill_null(0)
    )
    mode = cfg["interpretation"]["points_allowed"]
    if mode == "offense_only":
        pa = pl.col("opp_score") - pl.col("opp_non_off_pts")
    elif mode == "yahoo":
        pa = pl.col("opp_score") - pl.col("opp_yahoo_excluded")
    elif mode == "raw":
        pa = pl.col("opp_score")
    else:
        raise ValueError(f"unknown points_allowed mode: {mode}")
    sides = sides.with_columns(pa.alias("points_allowed"))
    table = cfg["defense"]["points_allowed"]
    res = [pa_points(v, table) for v in sides["points_allowed"].to_list()]
    return sides.with_columns(
        pl.Series("pa_bucket", [r[0] for r in res]),
        pl.Series("sabotage_pts", [r[1] for r in res], dtype=pl.Int64),
        pl.lit(cfg["version"]).alias("scoring_version"),
    ).sort(["week", "team"])
