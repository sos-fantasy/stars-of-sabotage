"""Weekly projection review: the Improvements page.

After a week's games are done, compare each player's last projection before kickoff
with what he scored, pick the five biggest misses for their position, and explain them
from measured numbers:

  * which scored events made up the miss (projected vs actual counts),
  * how likely a miss that size was from randomness alone, given the projection,
  * playing time (snap share), volume (attempts, carries, targets), passing efficiency,
    game script (final margin vs the spread), weather (forecast vs recorded), and
    the injury report.

Each measured cause is tagged, tallied across weeks, and mapped to a data addition we
could test. A short write-up by Claude (Anthropic API) sits on top when an API key is
set; it gets only the measured facts and is told to label any guess as a guess.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import polars as pl

import project as P

ROOT = Path(__file__).resolve().parent.parent
TOP_N = 5
EVENTS = ["n_incomplete", "n_sacks", "n_carries", "n_receptions", "n_fumbles", "n_fumbles_lost", "n_ints", "n_pick_sixes"]
LABEL = {"n_incomplete": "incompletions", "n_sacks": "sacks", "n_carries": "carries", "n_receptions": "catches",
         "n_fumbles": "fumbles", "n_fumbles_lost": "lost fumbles", "n_ints": "interceptions", "n_pick_sixes": "pick sixes"}
TURNOVER = {"n_fumbles", "n_fumbles_lost", "n_ints", "n_pick_sixes"}

# What each measured cause suggests we add or change, and how we would test it.
PROPOSALS = {
    "playing_time": ("Project playing time, not just per-game rates",
                     "Add expected snap share from the last three games plus Wednesday to Friday practice status "
                     "(did not practice, limited, full), and scale every event by it. Test: backtest 2021 to 2025 "
                     "with snap counts and practice reports from nflverse."),
    "injury_tag": ("Discount players listed Questionable",
                   "Players listed Questionable who play often leave early or play limited snaps. Add the report "
                   "status as a feature and test whether it lowers the average miss."),
    "volume": ("Project opportunities directly",
               "Model pass attempts, carries and targets from team pace and the player's share, then turn them "
               "into incompletions, carries and catches. Test against the current per-event averages."),
    "efficiency": ("Add opponent pass-defense quality",
                   "Use completion percentage over expected allowed by the opponent (from play-by-play) instead of "
                   "raw incompletions allowed. Test on quarterbacks."),
    "game_script": ("Use the latest line before kickoff",
                    "Blowouts change how much a team throws. Refresh the spread and total close to kickoff and test "
                    "whether a blowout-risk term (a large spread) helps quarterbacks and running backs."),
    "pressure": ("Add pass-rush and pass-protection quality",
                 "Sack spikes follow pressure. Add the opponent's pressure rate and the team's offensive line "
                 "injuries (from the injury report) and test them on quarterback sacks."),
    "weather": ("Refresh forecasts closer to kickoff",
                "Wind forecasts change. Run a forecast within three hours of kickoff for outdoor games."),
    "turnover_luck": ("Mostly randomness",
                      "Fumbles, interceptions and pick sixes repeat poorly. Expect these misses to continue; no data "
                      "fix is likely to remove them."),
    "role_change": ("Track depth chart moves",
                    "A player who moved up or down the depth chart that week, or was new to it, plays a different "
                    "role than his history shows. Test weighting recent games more after a depth chart change."),
    "news": ("Check team news",
             "A miss with no measured cause may come from news we do not read (a coach limiting a player, a role "
             "change). This needs a licensed news source before it can be tested."),
}


# ---------- projection log ----------

def update_log(log: dict, proj: dict, now) -> dict:
    """Keep each player's last projection made before his game kicked off."""
    import weather as Wx
    if not proj:
        return log
    kick = {g["game_id"]: Wx.kickoff_utc(g["gameday"], g["gametime"]) for g in proj.get("games", [])}
    wind = {g["game_id"]: (g.get("weather") or {}).get("wind_mph") for g in proj.get("games", [])}
    log.setdefault("season", proj["season"])
    log.setdefault("week", proj["week"])
    log.setdefault("source", "live")
    players, defs = log.setdefault("players", {}), log.setdefault("defenses", {})
    for p in proj.get("players", []):
        k = kick.get(p.get("game_id"))
        if k is None or k > now:
            players[p["id"]] = {**p, "forecast_wind": wind.get(p.get("game_id"))}
    for d in proj.get("defenses", []):
        k = kick.get(d.get("game_id"))
        if k is None or k > now:
            defs[d["team"]] = d
    return log


def replay_log(season: int, week: int, hist: pl.DataFrame, sched: pl.DataFrame, def_hist: pl.DataFrame, cfg: dict,
               snaps: pl.DataFrame | None = None) -> dict:
    """For weeks before the log existed: projections rebuilt from games played before the
    week, for every player who played (no depth chart or forecast). Marked 'replayed'."""
    import projections as PR
    t = season * 100 + week
    actual = hist.filter(pl.col("t") == t)
    up = actual.select("player_id", "player_display_name", "position", "team", "opponent_team", "season", "week") \
               .with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id"))
    pr = PR.player_projections(hist.filter(pl.col("t") < t), up, sched, cfg, t, snaps=snaps)
    players = {r["player_id"]: {"id": r["player_id"], "name": r["player_display_name"], "pos": r["position"],
                                "team": r["team"], "opp": r["opponent_team"], "proj": r["proj"], "lo": r["lo"],
                                "hi": r["hi"], "method": r["method"], "components": r["components"], "slot": None}
               for r in pr.iter_rows(named=True)}
    ctx = P.game_context(sched.filter(pl.col("season") == season)).filter(pl.col("week") == week)
    era = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    dg = (def_hist.filter((pl.col("season") == season) & (pl.col("week") == week))
          .with_columns(pl.col("team").replace(era), pl.col("opponent").replace(era))
          .join(ctx.select(pl.col("team").alias("opponent"), pl.col("implied").alias("opp_implied")), on="opponent", how="left")
          .drop_nulls("opp_implied"))
    defs = {}
    if dg.height:
        dp = PR.defense_projections(def_hist, sched, dg.select("team", pl.col("opponent").alias("opponent_team"), "opp_implied")
                                    .with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id")), cfg["defense"]["points_allowed"], t)
        defs = {r["team"]: {"team": r["team"], "opp": r["opponent_team"], "proj": r["proj"], "lo": float(r["lo"]),
                            "hi": float(r["hi"]), "pa_mean": r["pa_mean"]} for r in dp.iter_rows(named=True)}
    return {"season": season, "week": week, "source": "replayed", "players": players, "defenses": defs}


# ---------- luck ----------

def luck_probability(components: dict, weights: dict, miss: float, sims: int = 40000, seed: int = 7) -> float | None:
    """Chance that randomness alone, around this projection, produces a miss at least
    this big. Each event is a Poisson count around its projected mean, except that lost
    fumbles are drawn from the fumbles (each fumble is lost with the projected share)
    and pick sixes from the interceptions, since one cannot happen without the other."""
    if not components:
        return None
    rng = np.random.default_rng(seed)
    c = {k: max(float(v), 0.0) for k, v in components.items()}
    total = np.zeros(sims)
    mean = sum(v * weights[k] for k, v in c.items())
    nested = {"n_fumbles_lost": "n_fumbles", "n_pick_sixes": "n_ints"}
    draws = {}
    for k in [k for k in c if k not in nested]:
        draws[k] = rng.poisson(c[k], sims)
    for child, parent in nested.items():
        if child in c:
            if parent in draws and c[parent] > 0:
                p = min(c[child] / c[parent], 1.0)
                draws[child] = rng.binomial(draws[parent], p)
            else:
                draws[child] = rng.poisson(c[child], sims)
    for k, d in draws.items():
        total += d * weights[k]
    return float(np.mean(np.abs(total - mean) >= abs(miss)))


def range_probability(proj: float, lo: float, hi: float, miss: float) -> float | None:
    """Same idea for kickers and defenses, from their 10th to 90th percentile range,
    treating it as a normal spread (10th to 90th covers 2.56 standard deviations)."""
    from math import erf, sqrt
    sd = max((hi - lo) / 2.56, 1e-6)
    z = abs(miss) / sd
    return float(1 - erf(z / sqrt(2)))


# ---------- the review ----------

def build_week(season: int, week: int, log: dict, data_out: Path, cfg: dict, sched: pl.DataFrame,
               loaders: dict, mae_by_pos: dict, prev_log: dict | None = None) -> dict:
    """loaders: functions returning snap counts, player stats, injuries, players (id crosswalk);
    any may fail, and that cause is then reported as 'not measured'."""
    W = P.weights(cfg)
    hist = P.load_history(data_out, [season])
    wk = hist.filter(pl.col("week") == week)
    actual = {r["player_id"]: r for r in wk.iter_rows(named=True)}
    rows = []
    for pid, p in log.get("players", {}).items():
        a = actual.get(pid)
        if a is None:
            continue
        miss = float(a["sabotage_pts"]) - float(p["proj"])
        pos = "RB" if p["pos"] == "FB" else p["pos"]
        scale = mae_by_pos.get(pos) or 1.0
        rows.append({"kind": "player", "id": pid, "name": p["name"], "pos": p["pos"], "team": p["team"], "opp": p["opp"],
                     "slot": p.get("slot"), "proj": p["proj"], "lo": p["lo"], "hi": p["hi"], "actual": a["sabotage_pts"],
                     "miss": round(miss, 1), "rel": abs(miss) / scale, "components": p.get("components") or {},
                     "method": p.get("method"), "forecast_wind": p.get("forecast_wind"), "row": a})
    did_not_play = [p["name"] for pid, p in log.get("players", {}).items() if pid not in actual]
    # defenses
    dpath = data_out / f"defense-{season}.json"
    if dpath.exists():
        d = json.loads(dpath.read_text())
        dact = {r["team"]: r for r in (dict(zip(d["cols"], x)) for x in d["rows"]) if r["week"] == week}
        for team, dp in log.get("defenses", {}).items():
            a = dact.get(team)
            if not a:
                continue
            miss = float(a["sabotage_pts"]) - float(dp["proj"])
            rows.append({"kind": "defense", "id": team, "name": f"{team} defense", "pos": "DEF", "team": team,
                         "opp": dp["opp"], "proj": dp["proj"], "lo": dp["lo"], "hi": dp["hi"], "actual": a["sabotage_pts"],
                         "miss": round(miss, 1), "rel": abs(miss) / (mae_by_pos.get("DEF") or 1.0),
                         "pa_mean": dp.get("pa_mean"), "points_allowed": a["points_allowed"]})
    if not rows:
        return {}
    # week summary
    by_pos = {}
    for r in rows:
        pos = "RB" if r["pos"] == "FB" else r["pos"]
        by_pos.setdefault(pos, []).append(abs(r["miss"]))
    summary = {pos: {"n": len(v), "avg_miss": round(float(np.mean(v)), 2), "backtest": mae_by_pos.get(pos)}
               for pos, v in sorted(by_pos.items())}
    inside = sum(1 for r in rows if r["lo"] <= r["actual"] <= r["hi"])
    top = sorted(rows, key=lambda r: -abs(r["miss"]))[:TOP_N]

    measures = _measures(season, week, [r for r in top if r["kind"] == "player"], hist, sched, loaders)
    # depth chart: this week's slot against last week's (live weeks only)
    if prev_log and log.get("source") == "live":
        before = {pid: p.get("slot") for pid, p in prev_log.get("players", {}).items()}
        for r in top:
            if r["kind"] == "player" and r.get("slot"):
                measures.setdefault(r["id"], {})["slot"] = r["slot"]
                measures[r["id"]]["slot_prev"] = before.get(r["id"])
    out_top = []
    for r in top:
        out_top.append(_explain(r, W, measures.get(r["id"], {}), sched, season, week, len(rows)))
    return {"season": season, "week": week, "source": log.get("source", "live"),
            "summary": summary, "range_hit": round(inside / len(rows), 3), "n": len(rows),
            "did_not_play": did_not_play[:20], "did_not_play_n": len(did_not_play), "top": out_top}


def _measures(season, week, top_players, hist, sched, loaders) -> dict:
    out = {r["id"]: {} for r in top_players}
    ids = list(out)
    if not ids:
        return out
    # snap share, this game vs his previous three
    try:
        snaps = loaders["snaps"]()
        xw = loaders["players"]().select("gsis_id", "pfr_id").drop_nulls()
        s = snaps.join(xw, left_on="pfr_player_id", right_on="pfr_id").filter(pl.col("gsis_id").is_in(ids))
        for pid in ids:
            mine = s.filter(pl.col("gsis_id") == pid).sort("week")
            now = mine.filter(pl.col("week") == week)["offense_pct"].to_list()
            before = mine.filter(pl.col("week") < week)["offense_pct"].tail(3).to_list()
            if now:
                out[pid]["snap_pct"] = round(now[0] * 100)
            if before:
                out[pid]["snap_pct_usual"] = round(float(np.mean(before)) * 100)
    except Exception as e:
        print(f"[review] snap counts unavailable: {e}")
    # volume and passing efficiency
    try:
        ps = loaders["stats"]().filter(pl.col("player_id").is_in(ids) & (pl.col("season_type") == "REG"))
        for pid in ids:
            mine = ps.filter(pl.col("player_id") == pid).sort("week")
            now = mine.filter(pl.col("week") == week)
            before = mine.filter(pl.col("week") < week).tail(4)
            if now.is_empty():
                continue
            m = out[pid]
            for col in ("attempts", "carries", "targets"):
                if col in mine.columns:
                    m[col] = int(now[col][0] or 0)
                    if before.height:
                        m[f"{col}_usual"] = round(float(before[col].fill_null(0).mean()), 1)
            if "attempts" in mine.columns and (now["attempts"][0] or 0) > 0:
                m["inc_rate"] = round(100 * (1 - (now["completions"][0] or 0) / now["attempts"][0]))
                att, comp = before["attempts"].fill_null(0).sum(), before["completions"].fill_null(0).sum()
                if att:
                    m["inc_rate_usual"] = round(100 * (1 - comp / att))
    except Exception as e:
        print(f"[review] player stats unavailable: {e}")
    # injury report
    try:
        inj = loaders["injuries"]().filter((pl.col("week") == week) & pl.col("gsis_id").is_in(ids))
        for r in inj.iter_rows(named=True):
            if r.get("report_status"):
                out[r["gsis_id"]]["injury_status"] = r["report_status"]
                out[r["gsis_id"]]["injury"] = r.get("report_primary_injury")
    except Exception as e:
        print(f"[review] injuries unavailable: {e}")
    return out


def _game(sched, season, week, team):
    g = P.game_context(sched.filter(pl.col("season") == season)).filter((pl.col("week") == week) & (pl.col("team") == team))
    raw = sched.filter((pl.col("season") == season) & (pl.col("week") == week) & (pl.col("game_type") == "REG")
                       & ((pl.col("home_team") == team) | (pl.col("away_team") == team)))
    if g.is_empty() or raw.is_empty():
        return {}
    r, c = raw.row(0, named=True), g.row(0, named=True)
    if r["home_score"] is None:
        return {"expected_margin": c["team_spread"], "wind": r.get("wind"), "roof": r.get("roof")}
    margin = (r["home_score"] - r["away_score"]) * (1 if r["home_team"] == team else -1)
    return {"expected_margin": c["team_spread"], "margin": margin, "wind": r.get("wind"), "roof": r.get("roof"),
            "score": f'{r["away_team"]} {r["away_score"]}, {r["home_team"]} {r["home_score"]}'}


def _explain(r: dict, W: dict, m: dict, sched, season, week, n_week: int = 1) -> dict:
    g = _game(sched, season, week, r["team"])
    facts, tags, why = [], [], []
    miss = r["miss"]
    over = miss > 0
    if r["kind"] == "player":
        comps = r["components"]
        breakdown = []
        for c in EVENTS:
            if c not in comps and not r["row"].get(c):
                continue
            pc, ac = float(comps.get(c, 0)), float(r["row"].get(c) or 0)
            d = (ac - pc) * W[c]
            if abs(d) >= 1:
                breakdown.append({"event": LABEL[c], "projected": round(pc, 1), "actual": int(ac), "points": round(d, 1)})
        breakdown.sort(key=lambda b: -abs(b["points"]))
        luck = luck_probability(comps, W, miss) if r.get("method") == "model" else \
            range_probability(r["proj"], r["lo"], r["hi"], miss)
        turnover_pts = sum(b["points"] for b in breakdown if b["event"] in {LABEL[c] for c in TURNOVER})
        if breakdown and abs(turnover_pts) >= 0.5 * abs(miss):
            tags.append("turnover_luck")
            why.append(f"Turnovers made up {abs(turnover_pts):.0f} of the {abs(miss):.0f}-point miss. Those repeat poorly week to week.")
        sp, su = m.get("snap_pct"), m.get("snap_pct_usual")
        if sp is not None and su and (sp < 0.7 * su or (su >= 80 and sp < 60)):
            tags.append("playing_time")
            why.append(f"He played {sp}% of offensive snaps against his usual {su}%, so every rate ran on less time.")
        elif sp is not None and not su and sp < 50:
            tags.append("playing_time")
            why.append(f"He played only {sp}% of offensive snaps, and the projection assumed a full game.")
        elif sp is not None and su and sp > 1.3 * su and su < 70:
            tags.append("playing_time")
            why.append(f"His role grew: {sp}% of snaps against his usual {su}%.")
        for col, word in (("attempts", "pass attempts"), ("carries", "carries"), ("targets", "targets")):
            v, u = m.get(col), m.get(f"{col}_usual")
            if v is not None and u and u >= 3 and (v >= 1.4 * u or v <= 0.6 * u):
                tags.append("volume")
                why.append(f"Volume swung: {v} {word} against his recent {u}.")
                break
        if "slot" in m and m.get("slot") != m.get("slot_prev"):
            tags.append("role_change")
            why.append(f"Depth chart change: {m['slot']} this week, "
                       + (f"{m['slot_prev']} the week before." if m.get("slot_prev") else "not a listed starter the week before."))
        sk = next((x for x in breakdown if x["event"] == "sacks"), None)
        if sk and sk["actual"] >= 2 * sk["projected"] + 2:
            tags.append("pressure")
            why.append(f"He was sacked {sk['actual']} times against {sk['projected']:.1f} projected.")
        ir, iu = m.get("inc_rate"), m.get("inc_rate_usual")
        if ir is not None and iu is not None and abs(ir - iu) >= 10:
            tags.append("efficiency")
            why.append(f"He missed on {ir}% of throws against his recent {iu}%.")
        if m.get("injury_status") in ("Questionable", "Doubtful"):
            tags.append("injury_tag")
            why.append(f"He was listed {m['injury_status']}{' (' + m['injury'] + ')' if m.get('injury') else ''} that week.")
        fw = r.get("forecast_wind")
        if fw is not None and g.get("wind") is not None and abs(float(g["wind"]) - float(fw)) >= 10:
            tags.append("weather")
            why.append(f"Wind was {g['wind']} mph against a forecast of {fw:.0f}.")
        facts = {"breakdown": breakdown[:5], **m}
    else:
        luck = range_probability(r["proj"], r["lo"], r["hi"], miss)
        facts = {"points_allowed": r.get("points_allowed"), "expected_allowed": r.get("pa_mean")}
        if r.get("pa_mean") is not None:
            why.append(f"The defense was charged {r['points_allowed']} points against about {r['pa_mean']:.0f} expected.")
    if g.get("margin") is not None and abs(g["margin"] - g["expected_margin"]) >= 14:
        tags.append("game_script")
        why.append(f"Game script broke from the line: {r['team']} finished {g['margin']:+d} against an expected {g['expected_margin']:+.1f} ({g.get('score', '')}).")
    expected = None if luck is None else luck * n_week
    if luck is not None:
        if luck >= 0.10:
            why.append(f"Randomness alone produces a miss this size about {round(luck * 100)}% of the time, so much of this is noise.")
        elif luck > 0:
            one_in = round(1 / luck)
            why.append(f"Randomness alone produces a miss this size for about 1 player in {one_in:,}. With {n_week} projections "
                       f"this week, about {expected:.1f} such misses were expected from chance.")
        else:
            why.append("Randomness alone almost never produces a miss this size, so something real moved this one.")
    if not tags and (luck is None or luck * n_week < 0.5):
        tags.append("news")
        why.append("None of the measured causes fits, and randomness alone rarely produces a miss this big. Something we do not track probably mattered.")
    return {"kind": r["kind"], "id": r["id"], "name": r["name"], "pos": r["pos"], "team": r["team"], "opp": r["opp"],
            "slot": r.get("slot"), "proj": r["proj"], "lo": r["lo"], "hi": r["hi"], "actual": r["actual"], "miss": miss,
            "direction": "over" if over else "under", "luck": None if luck is None else round(luck, 4),
            "expected_by_chance": None if expected is None else round(expected, 2),
            "tags": tags, "why": why, "facts": facts, "game": g}


# ---------- tally and Claude ----------

def tally(weeks: list[dict]) -> list[dict]:
    counts = {}
    for w in weeks:
        for t in w.get("top", []):
            for tag in t.get("tags", []):
                counts[tag] = counts.get(tag, 0) + 1
    total = sum(len(w.get("top", [])) for w in weeks) or 1
    status = _status()
    out = []
    for tag, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        title, plan = PROPOSALS[tag]
        out.append({"tag": tag, "count": n, "share": round(n / total, 2), "title": title, "plan": plan,
                    "status": status.get(tag, {}).get("status", "proposed"), "note": status.get(tag, {}).get("note", "")})
    return out


def _status() -> dict:
    p = ROOT / "config" / "improvement_status.yml"
    if not p.exists():
        return {}
    import yaml
    return yaml.safe_load(p.read_text()) or {}


def facts_hash(week: dict) -> str:
    keep = {k: week[k] for k in ("season", "week", "summary", "top", "range_hit") if k in week}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:12]


SYSTEM = """You review a fantasy football projection system for the site Stars of Sabotage. In this league
players score points for things that go wrong: incompletions (2), sacks taken (5), carries (1), catches (2),
fumbles (7), lost fumbles (+10), interceptions (10), pick sixes (+21), missed kicks, and points a defense allows.

You get one week's five biggest misses with only measured facts. Write a short analysis for the site's public
Improvements page and for the owner.

Rules:
- Reason only from the facts given. When you suggest a cause that is not in the facts, say plainly that it is
  a guess and what data would confirm it.
- For each miss, one short paragraph: what drove it, how much was likely randomness (use the luck number), and
  what data or change would have helped, if any.
- Then a section "What to test next": at most three concrete changes, each with the data source and how to
  backtest it. Prefer changes supported by several misses or by the running tally. Do not promise accuracy you
  cannot reach; some misses are noise.
- Plain text. No em dashes. No headings except "What to test next". Do not use the words testament, pivotal,
  tapestry, moreover, furthermore. No bullet points with bold titles. Under 450 words."""


def claude_summary(week: dict, tally_rows: list[dict], log=print) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    facts = {k: week[k] for k in ("season", "week", "summary", "range_hit", "did_not_play_n", "top")}
    body = {"model": os.environ.get("SOS_REVIEW_MODEL", "claude-sonnet-5-5"), "max_tokens": 1400, "system": SYSTEM,
            "messages": [{"role": "user", "content": "Facts for this week:\n" + json.dumps(facts, default=str)
                          + "\n\nRunning tally of causes across all reviewed weeks:\n" + json.dumps(tally_rows)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
        return text.replace("—", ", ").replace("–", "-") or None
    except Exception as e:
        log(f"[review] Claude summary skipped: {e}")
        return None


# ---------- the pipeline step ----------

def run(data_out: Path, prev_data: Path | None, season: int, now, cfg: dict, weeks: list[dict], proj: dict | None,
        log=print) -> dict:
    import shutil
    from functools import lru_cache
    import nflreadpy as nfl
    data_out = Path(data_out)
    logdir = data_out / "projection-log"
    logdir.mkdir(exist_ok=True)
    if prev_data and (prev_data / "projection-log").exists():
        for f in (prev_data / "projection-log").glob("*.json"):
            if not (logdir / f.name).exists():
                shutil.copy2(f, logdir / f.name)
    if proj:
        p = logdir / f"{proj['season']}-w{proj['week']:02d}.json"
        cur = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps(update_log(cur, proj, now), default=str))

    prev = json.loads((prev_data / "improvements.json").read_text()) if prev_data and (prev_data / "improvements.json").exists() else {}
    done = {(w["season"], w["week"]): w for w in prev.get("weeks", [])}
    bt = json.loads((ROOT / "config" / "backtest.json").read_text()) if (ROOT / "config" / "backtest.json").exists() else {}
    mae = {pos: v["proj"]["mae"] for pos, v in {**bt.get("players", {}), **bt.get("defenses", {})}.items()}

    ready = [w for w in weeks if w["status"] in ("final", "provisional") and w.get("games_done") == w.get("games")]
    todo = [w for w in ready if (season, w["week"]) not in done or done[(season, w["week"])].get("status") != w["status"]]
    if todo:
        sched = nfl.load_schedules(list(range(season - 10, season + 1)))
        loaders = {"snaps": lru_cache(None)(lambda: nfl.load_snap_counts(season)),
                   "stats": lru_cache(None)(lambda: nfl.load_player_stats(season)),
                   "injuries": lru_cache(None)(lambda: nfl.load_injuries(season)),
                   "players": lru_cache(None)(lambda: nfl.load_players())}
        hist = defs = snaps_all = None
        for w in todo:
            lp = logdir / f"{season}-w{w['week']:02d}.json"
            wlog = json.loads(lp.read_text()) if lp.exists() else None
            if not wlog or not wlog.get("players"):
                if hist is None:
                    seasons = list(range(season - 10, season + 1))
                    hist = P.load_history(data_out, [s for s in seasons if (data_out / f"scores-{s}.json").exists()])
                    defs = pl.concat([pl.DataFrame(d["rows"], schema=d["cols"], orient="row", infer_schema_length=None)
                                      .with_columns(pl.lit(s).alias("season"))
                                      for s in seasons if (data_out / f"defense-{s}.json").exists()
                                      for d in [json.loads((data_out / f"defense-{s}.json").read_text())]], how="diagonal_relaxed")
                if snaps_all is None:
                    import projections as PR
                    try:
                        snaps_all = PR.load_snaps(list(range(season - 10, season + 1)))
                    except Exception as e:
                        log(f"[review] snap counts unavailable for replay: {e}")
                        snaps_all = pl.DataFrame()
                wlog = replay_log(season, w["week"], hist, sched, defs, cfg, snaps=snaps_all)
                lp.write_text(json.dumps(wlog, default=str))
            pp = logdir / f"{season}-w{w['week'] - 1:02d}.json"
            review = build_week(season, w["week"], wlog, data_out, cfg, sched, loaders, mae,
                                prev_log=json.loads(pp.read_text()) if pp.exists() else None)
            if not review:
                continue
            review["status"] = w["status"]
            old = done.get((season, w["week"]), {})
            h = facts_hash(review)
            review["facts_hash"] = h
            review["claude"] = old.get("claude") if old.get("facts_hash") == h else None
            done[(season, w["week"])] = review
            log(f"[review] {season} week {w['week']} ({review['source']}, {w['status']}): top miss "
                f"{review['top'][0]['name']} {review['top'][0]['miss']:+.1f}")
    weeks_out = [done[k] for k in sorted(done, reverse=True)]
    tl = tally(weeks_out)
    for w in weeks_out:
        if not w.get("claude"):
            w["claude"] = claude_summary(w, tl, log=log)
            if w["claude"]:
                w["claude_model"] = os.environ.get("SOS_REVIEW_MODEL", "claude-sonnet-5-5")
    return {"generated": now.isoformat(timespec="minutes"), "weeks": weeks_out, "tally": tl}
