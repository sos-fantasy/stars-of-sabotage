"""Projections and the walk-forward backtest (brief section 9).

Every prediction for a game uses only games played before it: features come from
per-player running statistics shifted by one game, so a week's own result never
leaks into its prediction.

Evaluated on players who played that week (the standard "if he plays" projection).
Who plays is a separate question, handled later with injuries and depth charts.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl

POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "K": "K"}
COUNTS = ["n_incomplete", "n_sacks", "n_carries", "n_receptions", "n_fumbles", "n_fumbles_lost",
          "n_ints", "n_pick_sixes"]


def load_history(data_dir: Path, seasons: list[int]) -> pl.DataFrame:
    frames = []
    for s in seasons:
        d = json.loads((Path(data_dir) / f"scores-{s}.json").read_text())
        frames.append(pl.DataFrame(d["rows"], schema=d["cols"], orient="row", infer_schema_length=None)
                      .with_columns(pl.lit(s).alias("season")))
    df = pl.concat(frames, how="diagonal_relaxed")
    df = df.with_columns(pl.col("position").replace_strict(POS_GROUP, default=None).alias("pg"))
    df = df.filter(pl.col("pg").is_not_null())
    # One chronological index across seasons, so "last 4 games" can span a season break.
    return df.sort(["player_id", "season", "week"]).with_columns(
        (pl.col("season") * 100 + pl.col("week")).alias("t"))


# ---------- baselines ----------

def baselines(df: pl.DataFrame) -> pl.DataFrame:
    """Season-to-date average and last-4-games average, each from games before this one.

    Fallbacks, so every player-week gets a number: season-to-date falls back to the
    player's previous-season average, then to the position average from the previous
    season; last-4 falls back to the position average when he has no earlier games."""
    df = df.sort(["player_id", "t"])
    p = pl.col("sabotage_pts")
    df = df.with_columns(
        (p.cum_sum().over(["player_id", "season"]) - p).alias("_std_sum"),
        (pl.int_range(pl.len()).over(["player_id", "season"])).alias("_std_n"),
        p.shift(1).rolling_mean(4, min_samples=1).over("player_id").alias("b_last4"),
    )
    prev = (df.group_by(["player_id", "season"]).agg(p.mean().alias("_prev_avg"))
            .with_columns((pl.col("season") + 1).alias("season")))
    pos_prev = (df.group_by(["pg", "season"]).agg(p.mean().alias("_pos_avg"))
                .with_columns((pl.col("season") + 1).alias("season")))
    df = df.join(prev, on=["player_id", "season"], how="left").join(pos_prev, on=["pg", "season"], how="left")
    return df.with_columns(
        pl.when(pl.col("_std_n") > 0).then(pl.col("_std_sum") / pl.col("_std_n"))
          .otherwise(pl.coalesce("_prev_avg", "_pos_avg")).alias("b_std"),
        pl.coalesce("b_last4", "_pos_avg").alias("b_last4"),
    ).drop([c for c in df.columns if c.startswith("_")] + ["_prev_avg", "_pos_avg"], strict=False)


# ---------- metrics ----------

def score(df: pl.DataFrame, pred: str, seasons: list[int], min_week: int = 1) -> pl.DataFrame:
    """MAE and mean weekly Spearman rank correlation by position."""
    e = df.filter(pl.col("season").is_in(seasons) & (pl.col("week") >= min_week) & pl.col(pred).is_not_null())
    mae = e.group_by("pg").agg((pl.col(pred) - pl.col("sabotage_pts")).abs().mean().alias("mae"),
                               pl.len().alias("n"))
    rk = (e.with_columns(pl.col(pred).rank().over(["season", "week", "pg"]).alias("_rp"),
                         pl.col("sabotage_pts").rank().over(["season", "week", "pg"]).alias("_ra"))
          .group_by(["season", "week", "pg"]).agg(pl.corr("_rp", "_ra").alias("rho"), pl.len().alias("k"))
          .filter(pl.col("k") >= 5).group_by("pg").agg(pl.col("rho").mean().alias("spearman")))
    return mae.join(rk, on="pg").sort("pg")


# ---------- count model ----------

def weights(cfg: dict) -> dict[str, float]:
    o = cfg["offense"]
    return {"n_incomplete": o["incomplete_pass"], "n_sacks": o["sack_taken"], "n_carries": o["rush_attempt"],
            "n_receptions": o["reception"], "n_fumbles": o["fumble"], "n_fumbles_lost": o["fumble_lost"],
            "n_ints": o["interception_thrown"], "n_pick_sixes": o["pick_six_thrown"], "pts_kicking": 1}


def count_model(df: pl.DataFrame, cfg: dict, half_life: float = 6.0, k: dict | None = None,
                cap: int = 16) -> pl.DataFrame:
    """Expected count of each scored event, then expected points.

    For each event: an exponentially weighted average of the player's earlier games
    (half-life in games, across seasons), shrunk toward last season's position average
    by k pseudo-games. Rare events get a bigger k, so one fluky fumble does not swing
    the projection."""
    k = k or {}
    w = weights(cfg)
    cols = list(w)
    df = df.sort(["player_id", "t"])
    df = df.with_columns(pl.int_range(pl.len()).over("player_id").alias("_n"))
    pos_prev = (df.group_by(["pg", "season"]).agg([pl.col(c).mean().alias(f"_pm_{c}") for c in cols])
                .with_columns((pl.col("season") + 1).alias("season")))
    df = df.join(pos_prev, on=["pg", "season"], how="left")
    exprs = []
    for c in cols:
        ew = pl.col(c).shift(1).ewm_mean(half_life=half_life, ignore_nulls=True).over("player_id")
        n = pl.min_horizontal(pl.col("_n"), pl.lit(cap)).cast(pl.Float64)
        kk = float(k.get(c, 4.0))
        exprs.append(pl.when(pl.col("_n") > 0)
                     .then((n * ew + kk * pl.col(f"_pm_{c}")) / (n + kk))
                     .otherwise(pl.col(f"_pm_{c}")).alias(f"e_{c}"))
    df = df.with_columns(exprs)
    return df.with_columns(sum(pl.col(f"e_{c}") * w[c] for c in cols).alias("m_count")).drop(
        [c for c in df.columns if c.startswith("_")])


# ---------- game context ----------

def game_context(sched: pl.DataFrame) -> pl.DataFrame:
    """One row per team per regular-season game: implied points from the spread and
    total, home or away, indoor or not, and wind. nflverse's spread_line is the home
    team's expected margin, so home implied = total/2 + spread/2."""
    # Schedules keep a franchise's code from that era (OAK, SD, STL); player stats use
    # today's codes. Map them so the two line up.
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    g = sched.filter(pl.col("game_type") == "REG").with_columns(
        pl.col("home_team").replace(era), pl.col("away_team").replace(era))
    indoor = pl.col("roof").is_in(["dome", "closed"])
    base = [pl.col("season"), pl.col("week"), indoor.alias("indoor"),
            pl.when(indoor).then(0).otherwise(pl.col("wind").fill_null(8)).cast(pl.Float64).alias("wind_mph")]
    home = g.select(*base, pl.col("home_team").alias("team"), pl.col("away_team").alias("opp"), pl.lit(1).alias("home"),
                    (pl.col("total_line") / 2 + pl.col("spread_line") / 2).alias("implied"),
                    pl.col("spread_line").alias("team_spread"))
    away = g.select(*base, pl.col("away_team").alias("team"), pl.col("home_team").alias("opp"), pl.lit(0).alias("home"),
                    (pl.col("total_line") / 2 - pl.col("spread_line") / 2).alias("implied"),
                    (-pl.col("spread_line")).alias("team_spread"))
    return pl.concat([home, away])


def opponent_rates(df: pl.DataFrame, cols: list[str], half_life: float = 8.0) -> pl.DataFrame:
    """What each defense has allowed per game, from games before this one (EWMA), as a
    ratio to the league average that season so far. 1.3 means 30% more than average."""
    per = (df.group_by(["opponent_team", "season", "week", "t"]).agg([pl.col(c).sum() for c in cols])
           .sort(["opponent_team", "t"]))
    per = per.with_columns([pl.col(c).shift(1).ewm_mean(half_life=half_life, ignore_nulls=True)
                            .over("opponent_team").alias(f"_d_{c}") for c in cols])
    league = per.group_by(["season"]).agg([pl.col(c).mean().alias(f"_l_{c}") for c in cols])
    per = per.join(league, on="season")
    return per.select("opponent_team", "season", "week",
                      *[(pl.col(f"_d_{c}") / pl.col(f"_l_{c}")).fill_null(1.0).clip(0.4, 2.5).alias(f"o_{c}") for c in cols])


# Poisson regression by iteratively reweighted least squares (no extra dependency).
def poisson_fit(X, y, iters: int = 30, ridge: float = 1e-3):
    import numpy as np
    b = np.zeros(X.shape[1])
    b[0] = np.log(max(y.mean(), 1e-6))
    for _ in range(iters):
        mu = np.exp(np.clip(X @ b, -20, 20))
        z = X @ b + (y - mu) / np.maximum(mu, 1e-9)
        W = mu
        A = (X * W[:, None]).T @ X + ridge * np.eye(X.shape[1])
        b_new = np.linalg.solve(A, (X * W[:, None]).T @ z)
        if np.max(np.abs(b_new - b)) < 1e-7:
            return b_new
        b = b_new
    return b


def logistic_fit(X, y, iters: int = 40, ridge: float = 1e-3):
    import numpy as np
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        W = np.maximum(p * (1 - p), 1e-9)
        z = X @ b + (y - p) / W
        b_new = np.linalg.solve((X * W[:, None]).T @ X + ridge * np.eye(X.shape[1]), (X * W[:, None]).T @ z)
        if np.max(np.abs(b_new - b)) < 1e-8:
            return b_new
        b = b_new
    return b


# ---------- kickers ----------
FG_BUCKETS = ["0-19", "20-29", "30-39", "40-49", "50+"]


def _bucket(d):
    return pl.when(d < 20).then(pl.lit("0-19")).when(d < 30).then(pl.lit("20-29")).when(d < 40).then(pl.lit("30-39")) \
        .when(d < 50).then(pl.lit("40-49")).otherwise(pl.lit("50+"))


def kick_attempts(kicks: pl.DataFrame) -> pl.DataFrame:
    """Every field goal and extra point try with whether it missed (blocked counts as a miss,
    as in the league's scoring) and the conditions: indoor, and wind if outdoors."""
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    k = kicks.filter(pl.col("kicker_player_id").is_not_null() & pl.col("kick_distance").is_not_null()
                     & ~pl.col("extra_point_result").is_in(["aborted"]).fill_null(False))
    indoor = pl.col("roof").is_in(["dome", "closed"])
    return k.with_columns(
        pl.col("posteam").replace(era).alias("team"),
        (pl.col("play_type") == "extra_point").alias("is_pat"),
        pl.when(pl.col("play_type") == "field_goal").then(pl.col("field_goal_result") != "made")
          .otherwise(pl.col("extra_point_result") != "good").fill_null(True).alias("miss"),
        indoor.fill_null(False).alias("indoor"),
        pl.when(indoor.fill_null(False)).then(0).otherwise(pl.col("wind").fill_null(8)).cast(pl.Float64).alias("wind_mph"),
        _bucket(pl.col("kick_distance")).alias("bucket"),
        (pl.col("season") * 100 + pl.col("week")).alias("t"),
    ).sort(["t", "game_id"])
