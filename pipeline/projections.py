"""Weekly projections for the coming week (brief section 9), built on project.py.

Players: QB, RB/FB, WR, TE count model with game context (spread and total, opponent
rates, home, roof, wind). Kickers: season-to-date average, because the kicking model
did not beat it on the backtest. Defenses: points-allowed distribution from the
opponent's implied points.

Every number shown is "if he plays". Players listed Out, Doubtful, or on injured
reserve on the week's injury report are left off.
"""
from __future__ import annotations

import numpy as np
import polars as pl

import project as P

USE = {"QB": ["n_incomplete", "n_sacks", "n_carries", "n_fumbles", "n_fumbles_lost", "n_ints", "n_pick_sixes"],
       "RB": ["n_carries", "n_receptions", "n_fumbles", "n_fumbles_lost"],
       "WR": ["n_receptions", "n_carries", "n_fumbles", "n_fumbles_lost"],
       "TE": ["n_receptions", "n_carries", "n_fumbles", "n_fumbles_lost"]}
LABEL = {"n_incomplete": "incompletions", "n_sacks": "sacks", "n_carries": "carries", "n_receptions": "catches",
         "n_fumbles": "fumbles", "n_fumbles_lost": "fumbles lost", "n_ints": "interceptions", "n_pick_sixes": "pick sixes"}
HALF_LIFE, K_BASE = 3, 2
TRAIN_YEARS = 9
OUT_STATUSES = {"Out", "Doubtful", "IR", "Injured Reserve", "PUP", "Suspended"}


def kmap(cols):
    k = {c: K_BASE for c in cols}
    k.update({"n_fumbles": K_BASE * 3, "n_fumbles_lost": K_BASE * 3, "n_ints": K_BASE * 2,
              "n_pick_sixes": K_BASE * 4, "pts_kicking": K_BASE * 2})
    return k


def design(d: pl.DataFrame, c: str) -> np.ndarray:
    return np.column_stack([
        np.ones(d.height),
        np.log(np.clip(d[f"e_{c}"].to_numpy(), 1e-3, None)),
        d["implied"].to_numpy() - 22,
        d["team_spread"].to_numpy(),
        np.log(d[f"o_{c}"].to_numpy()),
        d["home"].to_numpy().astype(float),
        d["indoor"].to_numpy().astype(float),
        d["wind_mph"].to_numpy() / 10,
    ])


FEATURE_NAMES = ["", "", "game script", "game script", "opponent", "home field", "roof", "wind"]


def _fill_ctx(df: pl.DataFrame, cols) -> pl.DataFrame:
    return df.with_columns(pl.col("implied").fill_null(22.0), pl.col("team_spread").fill_null(0.0),
                           pl.col("home").fill_null(0), pl.col("indoor").fill_null(False),
                           pl.col("wind_mph").fill_null(8.0), *[pl.col(f"o_{c}").fill_null(1.0) for c in cols])


def player_projections(hist: pl.DataFrame, upcoming: pl.DataFrame, sched_all: pl.DataFrame, cfg: dict,
                       target_t: int, wind_override: dict | None = None) -> pl.DataFrame:
    """hist: scored player-weeks (project.load_history). upcoming: one row per player to
    project with player_id, player_display_name, position, team, opponent_team, season, week.
    Returns one row per player with the projection, its range, components, and drivers."""
    W = P.weights(cfg)
    cols = list(W)
    up = upcoming.with_columns(*[pl.lit(0).cast(hist.schema[c]).alias(c) for c in cols if c in hist.columns],
                               pl.lit(0).alias("sabotage_pts"), pl.lit(True).alias("is_target"))
    up = up.with_columns(pl.col("position").replace_strict(P.POS_GROUP, default=None).alias("pg"),
                         (pl.col("season") * 100 + pl.col("week")).alias("t"))
    allrows = pl.concat([hist.with_columns(pl.lit(False).alias("is_target")), up], how="diagonal_relaxed")
    allrows = P.baselines(allrows)
    m = P.count_model(allrows, cfg, half_life=HALF_LIFE, k=kmap(cols))
    # Opponent rates from real games only; the target row takes the latest value.
    real = m.filter(~pl.col("is_target"))
    opp = P.opponent_rates(real, cols)
    ctx = P.game_context(sched_all).drop("opp")
    m = m.join(ctx, on=["season", "week", "team"], how="left")
    m = m.join(opp, on=["opponent_team", "season", "week"], how="left")
    latest = _latest_opponent_rates(real, cols)
    tgt = m.filter(pl.col("is_target")).drop([f"o_{c}" for c in cols]).join(latest, on="opponent_team", how="left")
    if wind_override:
        tgt = tgt.with_columns(pl.col("team").replace_strict(wind_override, default=None).alias("_w")) \
                 .with_columns(pl.when(pl.col("_w").is_not_null() & ~pl.col("indoor").fill_null(False))
                               .then(pl.col("_w")).otherwise(pl.col("wind_mph")).alias("wind_mph")).drop("_w")
    train = m.filter(~pl.col("is_target") & (pl.col("t") < target_t)
                     & (pl.col("season") >= target_t // 100 - TRAIN_YEARS))
    train, tgt = _fill_ctx(train, cols), _fill_ctx(tgt, cols)

    out = []
    for pg, use in USE.items():
        tr, te = train.filter(pl.col("pg") == pg), tgt.filter(pl.col("pg") == pg)
        if te.is_empty():
            continue
        comp, drivers_pts = {}, {n: np.zeros(te.height) for n in set(FEATURE_NAMES) if n}
        total_tr, total_te = np.zeros(tr.height), np.zeros(te.height)
        for c in cols:
            if c == "pts_kicking":
                continue
            base_te, base_tr = te[f"e_{c}"].to_numpy(), tr[f"e_{c}"].to_numpy()
            if c not in use:
                mu_te, mu_tr = base_te, base_tr
            else:
                b = P.poisson_fit(design(tr, c), tr[c].to_numpy().astype(float))
                Xte, Xtr = design(te, c), design(tr, c)
                mu_te = np.clip(np.exp(Xte @ b), 0.2 * base_te, 5 * base_te + 0.05)
                mu_tr = np.clip(np.exp(Xtr @ b), 0.2 * base_tr, 5 * base_tr + 0.05)
                # Driver effects: points gained or lost from each context feature vs a neutral game.
                neutral = Xte.copy()
                neutral[:, 2:] = 0
                neutral[:, 4] = 0
                for j in range(2, Xte.shape[1]):
                    only = neutral.copy()
                    only[:, j] = Xte[:, j]
                    drivers_pts[FEATURE_NAMES[j]] += (np.exp(only @ b) - np.exp(neutral @ b)) * W[c]
            comp[c] = mu_te
            total_te += mu_te * W[c]
            total_tr += mu_tr * W[c]
        lo, hi = _ranges(total_tr, tr["sabotage_pts"].to_numpy(), total_te)
        rows = te.select("player_id", "player_display_name", "position", "team", "opponent_team", "home", "game_id")
        rows = rows.with_columns(pl.Series("proj", np.round(total_te, 1)), pl.Series("lo", lo), pl.Series("hi", hi),
                                 pl.lit("model").alias("method"))
        comps = [{c: round(float(comp[c][i]), 2) for c in use} for i in range(te.height)]
        drv = [_driver_text(drivers_pts, i, te.row(i, named=True)) for i in range(te.height)]
        out.append(rows.with_columns(pl.Series("components", comps, dtype=pl.Object),
                                     pl.Series("drivers", drv, dtype=pl.Object)))
    # Kickers: season-to-date average (falls back to last season, then the position average).
    k = tgt.filter(pl.col("pg") == "K")
    if not k.is_empty():
        trk = train.filter(pl.col("pg") == "K")
        lo, hi = _ranges(trk["b_std"].fill_null(0).to_numpy(), trk["sabotage_pts"].to_numpy(), k["b_std"].fill_null(0).to_numpy())
        out.append(k.select("player_id", "player_display_name", "position", "team", "opponent_team", "home", "game_id")
                   .with_columns(pl.Series("proj", np.round(k["b_std"].fill_null(0).to_numpy(), 1)), pl.Series("lo", lo),
                                 pl.Series("hi", hi), pl.lit("season average").alias("method"),
                                 pl.Series("components", [{} for _ in range(k.height)], dtype=pl.Object),
                                 pl.Series("drivers", [["Kicking misses barely repeat week to week, so this is his season average."]] * k.height,
                                           dtype=pl.Object)))
    return pl.concat(out, how="diagonal_relaxed") if out else pl.DataFrame()


def _latest_opponent_rates(real: pl.DataFrame, cols, half_life: float = 8.0) -> pl.DataFrame:
    per = (real.group_by(["opponent_team", "season", "week", "t"]).agg([pl.col(c).sum() for c in cols])
           .sort(["opponent_team", "t"]))
    last_season = per["season"].max()
    league = per.filter(pl.col("season") == last_season).select([pl.col(c).mean().alias(f"_l_{c}") for c in cols])
    ew = per.with_columns([pl.col(c).ewm_mean(half_life=half_life).over("opponent_team").alias(f"_d_{c}") for c in cols]) \
        .group_by("opponent_team").agg([pl.col(f"_d_{c}").last() for c in cols])
    ew = ew.join(league, how="cross")
    return ew.select("opponent_team", *[(pl.col(f"_d_{c}") / pl.col(f"_l_{c}")).clip(0.4, 2.5).alias(f"o_{c}") for c in cols])


def _ranges(pred_tr, act_tr, pred_te, bins: int = 10):
    """10th to 90th percentile of what actually happened to training-set players whose
    projection was close to this one. Honest about how wide outcomes run."""
    if len(pred_tr) < 50:
        return np.round(pred_te * 0.3, 0), np.round(pred_te * 2, 0)
    edges = np.quantile(pred_tr, np.linspace(0, 1, bins + 1))
    idx_tr = np.clip(np.searchsorted(edges, pred_tr, side="right") - 1, 0, bins - 1)
    q10 = np.array([np.quantile(act_tr[idx_tr == b], 0.1) if (idx_tr == b).any() else 0 for b in range(bins)])
    q90 = np.array([np.quantile(act_tr[idx_tr == b], 0.9) if (idx_tr == b).any() else 0 for b in range(bins)])
    idx = np.clip(np.searchsorted(edges, pred_te, side="right") - 1, 0, bins - 1)
    return np.round(q10[idx], 0), np.round(q90[idx], 0)


def _driver_text(drv: dict, i: int, row: dict) -> list[str]:
    out = []
    for name, arr in sorted(drv.items(), key=lambda kv: -abs(kv[1][i])):
        v = float(arr[i])
        if abs(v) < 1.0:
            continue
        sign = "+" if v > 0 else "−"
        why = {"game script": "projected game flow (spread and total)",
               "opponent": f"what {row['opponent_team']}'s defense allows",
               "home field": "home field" if row.get("home") else "playing on the road",
               "roof": "indoor game" if row.get("indoor") else "outdoor game",
               "wind": f"wind ({row.get('wind_mph', 0):.0f} mph)"}[name]
        out.append(f"{sign}{abs(v):.1f} pts from {why}")
        if len(out) == 2:
            break
    return out


# ---------- defenses ----------

def defense_projections(def_hist: pl.DataFrame, sched_all: pl.DataFrame, games: pl.DataFrame,
                        table: dict, target_t: int) -> pl.DataFrame:
    """Expected Sabotage points for each defense this week. Points allowed is modeled as
    the opponent's implied points plus the defense's recent over- or under-performance,
    with the spread of outcomes taken from the last six seasons; each simulated score
    is turned into bucket points and averaged."""
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    D = def_hist.with_columns(pl.col("team").replace(era), pl.col("opponent").replace(era),
                              (pl.col("season") * 100 + pl.col("week")).alias("t")).sort(["team", "t"])
    ctx = P.game_context(sched_all)
    D = D.join(ctx.select("season", "week", pl.col("team").alias("opponent"), pl.col("implied").alias("opp_implied")),
               on=["season", "week", "opponent"], how="left").drop_nulls("opp_implied")
    D = D.with_columns((pl.col("points_allowed") - pl.col("opp_implied")).alias("r"))
    D = D.with_columns(pl.col("r").shift(1).ewm_mean(half_life=8, ignore_nulls=True).over("team").fill_null(0).alias("r_ew"))
    tr = D.filter((pl.col("t") < target_t) & (pl.col("season") >= target_t // 100 - 6))
    X = np.column_stack([np.ones(tr.height), tr["opp_implied"].to_numpy(), tr["r_ew"].to_numpy()])
    y = tr["points_allowed"].to_numpy().astype(float)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ beta
    latest_r = D.filter(pl.col("t") < target_t).group_by("team").agg(pl.col("r").ewm_mean(half_life=8).last().alias("r_now"))
    g = games.join(latest_r, on="team", how="left").with_columns(pl.col("r_now").fill_null(0.0))
    mu = np.column_stack([np.ones(g.height), g["opp_implied"].to_numpy(), g["r_now"].to_numpy()]) @ beta
    sims = np.clip(np.round(mu[:, None] + res[None, :]), 0, None)
    pts = bucket_points(sims, table)
    return g.with_columns(pl.Series("proj", np.round(pts.mean(axis=1), 1)),
                          pl.Series("lo", np.quantile(pts, 0.1, axis=1)), pl.Series("hi", np.quantile(pts, 0.9, axis=1)),
                          pl.Series("pa_mean", np.round(mu, 1)))


def bucket_points(x, table: dict):
    return np.select([x <= 0, x <= 6, x <= 13, x <= 20, x <= 27, x <= 34],
                     [table["0"], table["1-6"], table["7-13"], table["14-20"], table["21-27"], table["28-34"]],
                     table["35+"])


# ---------- the weekly build ----------

def target_week(sched_season: pl.DataFrame, now) -> tuple[int | None, pl.DataFrame]:
    """The week to preview and its games that have not kicked off. Once a week is down
    to its last two games (Monday night), the preview moves on to the next week."""
    import weather as Wx
    g = sched_season.filter(pl.col("game_type") == "REG").with_columns(
        pl.struct(["gameday", "gametime"]).map_elements(lambda s: Wx.kickoff_utc(s["gameday"], s["gametime"]),
                                                        return_dtype=pl.Datetime("us", "UTC")).alias("kickoff"))
    todo = g.filter(pl.col("kickoff") > now)
    if todo.is_empty():
        return None, todo
    wk = todo["week"].min()
    if todo.filter(pl.col("week") == wk).height <= 2 and todo.filter(pl.col("week") == wk + 1).height:
        wk += 1
    return wk, todo.filter(pl.col("week") == wk)


def build(data_out, season: int, now, cfg: dict, log=print) -> dict | None:
    import json
    from pathlib import Path
    import nflreadpy as nfl
    import weather as Wx
    data_out = Path(data_out)
    seasons = list(range(season - TRAIN_YEARS - 1, season + 1))
    sched_all = nfl.load_schedules(seasons)
    wk, games = target_week(sched_all.filter(pl.col("season") == season), now)
    if wk is None:
        return None
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    games = games.with_columns(pl.col("home_team").replace(era), pl.col("away_team").replace(era))
    hist = P.load_history(data_out, [s for s in seasons if (data_out / f"scores-{s}.json").exists()])
    target_t = season * 100 + wk

    # Who to project: players with a game for this team in its last three games this season.
    cur = hist.filter(pl.col("season") == season)
    last_team = hist.sort("t").group_by("player_id").agg(pl.col("team").last().alias("cur_team"))
    recent = (cur.join(cur.group_by("team").agg(pl.col("week").unique().sort().tail(3).alias("_wks")), on="team")
              .filter(pl.col("week").is_in(pl.col("_wks").list.explode()).over("team") if False else
                      pl.col("_wks").list.contains(pl.col("week")))
              .join(last_team, on="player_id").filter(pl.col("team") == pl.col("cur_team"))
              .group_by("player_id").agg(pl.col("player_display_name").last(), pl.col("position").last(), pl.col("team").last()))
    try:
        inj = nfl.load_injuries(season).filter((pl.col("week") == wk) & pl.col("report_status").is_in(list(OUT_STATUSES)))
        out_ids = set(inj["gsis_id"].drop_nulls().to_list())
    except Exception as e:
        log(f"[projections] injuries unavailable: {e}")
        out_ids = set()
    # One quarterback per team: the one who threw the most (incompletions plus sacks) in
    # the team's latest game, skipping anyone ruled out. Backups otherwise crowd the list.
    qb_load = (cur.filter(pl.col("pg") == "QB").with_columns((pl.col("n_incomplete") + pl.col("n_sacks")).alias("_load"))
               .sort(["team", "t", "_load"], descending=[False, True, True]))
    starters = {}
    for r in qb_load.iter_rows(named=True):
        if r["team"] not in starters and r["player_id"] not in out_ids and r["_load"] > 0:
            starters[r["team"]] = r["player_id"]
    recent = recent.filter((pl.col("position") != "QB") | pl.col("player_id").is_in(list(starters.values())))
    sides = pl.concat([
        games.select("game_id", pl.col("home_team").alias("team"), pl.col("away_team").alias("opponent_team")),
        games.select("game_id", pl.col("away_team").alias("team"), pl.col("home_team").alias("opponent_team"))])
    up = (recent.filter(~pl.col("player_id").is_in(list(out_ids))).join(sides, on="team")
          .with_columns(pl.lit(season).alias("season"), pl.lit(wk).alias("week")))

    # Weather for outdoor games; the forecast wind feeds the model.
    gl = games.select("game_id", "gameday", "gametime", "stadium", "stadium_id", "roof", "home_team", "away_team",
                      "spread_line", "total_line").to_dicts()
    wx = Wx.forecast(gl, now, log=log)
    wind = {}
    for g in gl:
        w = wx.get(g["game_id"])
        if w and not w.get("indoor") and w.get("wind_mph") is not None:
            wind[g["home_team"]] = wind[g["away_team"]] = w["wind_mph"]

    players = player_projections(hist, up, sched_all, cfg, target_t, wind_override=wind)

    # Defenses
    dfr = []
    for s in seasons:
        p = data_out / f"defense-{s}.json"
        if p.exists():
            d = json.loads(p.read_text())
            dfr.append(pl.DataFrame(d["rows"], schema=d["cols"], orient="row", infer_schema_length=None)
                       .with_columns(pl.lit(s).alias("season")))
    ctx = P.game_context(sched_all.filter(pl.col("season") == season)).filter(pl.col("week") == wk)
    dgames = sides.join(ctx.select(pl.col("team").alias("opponent_team"), pl.col("implied").alias("opp_implied")),
                        on="opponent_team", how="left").drop_nulls("opp_implied")
    defs = defense_projections(pl.concat(dfr, how="diagonal_relaxed"), sched_all, dgames,
                               cfg["defense"]["points_allowed"], target_t)

    imp = {r["team"]: r["implied"] for r in ctx.iter_rows(named=True)}
    out_games = []
    for g in gl:
        w = wx.get(g["game_id"]) or {}
        v = Wx.venue(g, Wx.load_stadiums())
        out_games.append({"game_id": g["game_id"], "home": g["home_team"], "away": g["away_team"],
                          "gameday": g["gameday"], "gametime": g["gametime"], "stadium": g["stadium"],
                          "roof": Wx.roof_of(g, v), "weather": w or None,
                          "home_implied": _r(imp.get(g["home_team"])), "away_implied": _r(imp.get(g["away_team"]))})
    plist = []
    for r in players.sort("proj", descending=True).iter_rows(named=True):
        plist.append({"id": r["player_id"], "name": r["player_display_name"], "pos": r["position"], "team": r["team"],
                      "opp": r["opponent_team"], "home": int(r["home"] or 0), "game_id": r["game_id"],
                      "proj": r["proj"], "lo": r["lo"], "hi": r["hi"], "method": r["method"],
                      "components": r["components"], "drivers": r["drivers"]})
    dlist = [{"team": r["team"], "opp": r["opponent_team"], "game_id": r["game_id"], "proj": r["proj"],
              "lo": float(r["lo"]), "hi": float(r["hi"]), "pa_mean": r["pa_mean"]}
             for r in defs.sort("proj", descending=True).iter_rows(named=True)]
    log(f"[projections] {season} week {wk}: {len(plist)} players, {len(dlist)} defenses, {len(out_games)} games, "
        f"{sum(1 for g in out_games if g['weather'] and not g['weather'].get('indoor'))} forecasts")
    return {"season": season, "week": wk, "generated": now.isoformat(timespec="minutes"),
            "games": out_games, "players": plist, "defenses": dlist}


def _r(x):
    return None if x is None else round(float(x), 1)
