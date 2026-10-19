"""Walk-forward backtest of the production projection code (brief section 9.3).

    python pipeline/backtest.py --data-dir dist/data --seasons 2021-2025 --out config/backtest.json

For every week of every test season: keep only games played before that week, refit,
project every player who played that week, and compare with what he scored. Defenses
the same way. Baselines: season-to-date average and last-4-games average.
Takes several minutes, so it runs by hand after a model change, not every hour.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project as P  # noqa: E402
import projections as PR  # noqa: E402
import score as S  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="dist/data")
    ap.add_argument("--seasons", default="2021-2025")
    ap.add_argument("--out", default="config/backtest.json")
    a = ap.parse_args(argv)
    lo, hi = (int(x) for x in a.seasons.split("-"))
    test = list(range(lo, hi + 1))
    import nflreadpy as nfl
    cfg = S.load_config()
    first = lo - PR.TRAIN_YEARS - 1
    sched = nfl.load_schedules(list(range(first, hi + 1)))
    hist_all = P.load_history(Path(a.data_dir), list(range(first, hi + 1)))
    hist_all = P.baselines(hist_all)
    ctx = P.game_context(sched)
    rows, drows = [], []
    defs = []
    for s in range(first, hi + 1):
        d = json.loads((Path(a.data_dir) / f"defense-{s}.json").read_text())
        defs.append(pl.DataFrame(d["rows"], schema=d["cols"], orient="row", infer_schema_length=None).with_columns(pl.lit(s).alias("season")))
    dhist = pl.concat(defs, how="diagonal_relaxed")
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    for season in test:
        for wk in range(1, 19):
            t = season * 100 + wk
            actual = hist_all.filter(pl.col("t") == t)
            if actual.is_empty():
                continue
            up = actual.select("player_id", "player_display_name", "position", "team", "opponent_team", "season", "week") \
                       .with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id"))
            hist = hist_all.filter(pl.col("t") < t).drop(["b_std", "b_last4"])
            pr = PR.player_projections(hist, up, sched, cfg, t)
            rows.append(pr.select("player_id", "proj", "lo", "hi").join(
                actual.select("player_id", "pg", "season", "week", "sabotage_pts", "b_std", "b_last4"), on="player_id"))
            # defenses
            dg = (dhist.filter((pl.col("season") == season) & (pl.col("week") == wk))
                  .with_columns(pl.col("team").replace(era), pl.col("opponent").replace(era))
                  .join(ctx.filter((pl.col("season") == season) & (pl.col("week") == wk))
                        .select(pl.col("team").alias("opponent"), pl.col("implied").alias("opp_implied")), on="opponent", how="left")
                  .drop_nulls("opp_implied"))
            dp = PR.defense_projections(dhist, sched, dg.select("team", pl.col("opponent").alias("opponent_team"), "opp_implied")
                                        .with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id")), cfg["defense"]["points_allowed"], t)
            drows.append(dp.select("team", "proj").join(dg.select("team", "sabotage_pts", "season", "week"), on="team"))
            print(f"{season} week {wk}: {pr.height} players", flush=True)
    R = pl.concat(rows, how="diagonal_relaxed")
    D = pl.concat(drows, how="diagonal_relaxed")
    # Defense baseline: season-to-date average from earlier weeks, else last season's average.
    dh = dhist.with_columns(pl.col("team").replace(era), (pl.col("season") * 100 + pl.col("week")).alias("t")).sort(["team", "t"])
    p = pl.col("sabotage_pts")
    dh = dh.with_columns(((p.cum_sum().over(["team", "season"]) - p) / pl.int_range(pl.len()).over(["team", "season"])).alias("b_std"))
    prev = dh.group_by(["team", "season"]).agg(p.mean().alias("pv")).with_columns(pl.col("season") + 1)
    dh = dh.join(prev, on=["team", "season"], how="left").with_columns(
        pl.when(pl.col("b_std").is_finite()).then(pl.col("b_std")).otherwise(pl.col("pv")).alias("b_std"))
    D = D.join(dh.select("team", "season", "week", "b_std"), on=["team", "season", "week"], how="left").with_columns(pl.lit("DEF").alias("pg"))

    def summarize(df, cols):
        out = {}
        for pg in sorted(df["pg"].unique().to_list()):
            sub = df.filter(pl.col("pg") == pg)
            out[pg] = {"n": sub.height}
            for c in cols:
                s = P.score(sub.drop_nulls(c), c, test)
                out[pg][c] = {"mae": round(s["mae"][0], 2), "spearman": round(s["spearman"][0], 3)}
            if "lo" in sub.columns:
                inside = sub.filter((pl.col("sabotage_pts") >= pl.col("lo")) & (pl.col("sabotage_pts") <= pl.col("hi"))).height
                out[pg]["range_hit"] = round(inside / sub.height, 3)
        return out
    result = {"seasons": test, "created": datetime.now(timezone.utc).isoformat(timespec="minutes"),
              "players": summarize(R, ["proj", "b_std", "b_last4"]), "defenses": summarize(D, ["proj", "b_std"])}
    Path(a.out).write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
