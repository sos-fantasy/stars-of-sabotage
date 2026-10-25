"""Projected vs actual, every player, every week (owner request, October 25, 2026).

Source of the projections: data/projection-log/{season}-wNN.json, which keeps each
player's last projection made before his game kicked off (review.update_log). Weeks 1
to 5 were rebuilt after the fact and are marked "replayed". Actuals: the scored week
in scores-{season}.json and defense-{season}.json.

Status per row:
- final: game over and his stat line is in; miss = actual - projected.
- dnp: game over, the team's stats are in, and he has no stat line (did not play).
- removed: dropped from the starters before kickoff (ruled out or moved down the
  depth chart); shown, not counted as a miss.
- awaiting: game over, stats not posted yet (nflverse posts after games end).
- pending: not started or in progress.

Writes data/results/{season}-wNN.json per week and data/results-{season}.json, an
index with each week's summary and every player's projection by week (player pages).
"""
from __future__ import annotations

import json
from pathlib import Path


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    return [dict(zip(d["cols"], r)) for r in d["rows"]]


def week_results(season: int, week: int, log: dict, scores: list[dict], defense: list[dict], games: list[dict]) -> dict:
    g_by = {g["game_id"]: g for g in games if g["week"] == week}
    # Replayed weeks have no game id per player; find it from the team's game that week.
    team_game = {}
    for gid, g in g_by.items():
        team_game[g["home_team"]] = team_game[g["away_team"]] = gid
    final_games = {gid for gid, g in g_by.items() if g.get("home_score") is not None}
    act = {r["player_id"]: r for r in scores if r["week"] == week}
    teams_in = {r["team"] for r in scores if r["week"] == week}
    dact = {r["team"]: r for r in defense if r["week"] == week}

    def status(game_id, team, have):
        if game_id not in final_games:
            return "pending"
        if have:
            return "final"
        return "dnp" if team in teams_in else "awaiting"

    players = []
    for pid, p in log.get("players", {}).items():
        a = act.get(pid)
        gid = p.get("game_id") or team_game.get(p["team"])
        st = status(gid, p["team"], a is not None)
        if p.get("removed") and st in ("dnp", "pending", "awaiting"):
            st = "removed"
        row = {"id": pid, "name": p["name"], "pos": "RB" if p["pos"] == "FB" else p["pos"], "team": p["team"],
               "opp": p["opp"], "home": p.get("home") if p.get("home") is not None else int(g_by.get(gid, {}).get("home_team") == p["team"]), "slot": p.get("slot"), "game_id": gid,
               "proj": p["proj"], "lo": p["lo"], "hi": p["hi"], "status": st}
        if a is not None:
            row["actual"] = a["sabotage_pts"]
            row["miss"] = round(float(a["sabotage_pts"]) - float(p["proj"]), 1)
            row["in_range"] = p["lo"] <= a["sabotage_pts"] <= p["hi"]
        players.append(row)
    for team, d in log.get("defenses", {}).items():
        a = dact.get(team)
        gid = d.get("game_id") or team_game.get(team)
        st = status(gid, team, a is not None)
        if st == "dnp":
            st = "awaiting"
        row = {"id": team, "name": f"{team} defense", "pos": "DEF", "team": team, "opp": d["opp"],
               "home": int(g_by.get(gid, {}).get("home_team") == team),
               "game_id": gid, "proj": d["proj"], "lo": d["lo"], "hi": d["hi"], "status": st}
        if a is not None:
            row["actual"] = a["sabotage_pts"]
            row["miss"] = round(float(a["sabotage_pts"]) - float(d["proj"]), 1)
            row["in_range"] = d["lo"] <= a["sabotage_pts"] <= d["hi"]
        players.append(row)
    players.sort(key=lambda r: -r["proj"])

    done = [r for r in players if r["status"] == "final"]
    by_pos: dict[str, list] = {}
    for r in done:
        by_pos.setdefault(r["pos"], []).append(r)
    summary = {pos: {"n": len(v), "avg_miss": round(sum(abs(r["miss"]) for r in v) / len(v), 1),
                     "in_range": round(sum(1 for r in v if r["in_range"]) / len(v), 3)}
               for pos, v in sorted(by_pos.items())}
    count = {}
    for r in players:
        count[r["status"]] = count.get(r["status"], 0) + 1
    import weather as Wx
    info = {}
    for gid, g in g_by.items():
        try:
            k = Wx.kickoff_utc(g["gameday"], g["gametime"]).isoformat()
        except Exception:
            k = None
        info[gid] = {"kickoff": k, "home": g["home_team"], "away": g["away_team"],
                     "home_score": g.get("home_score"), "away_score": g.get("away_score")}
    # Cards for every game of the week: the frozen pre-kickoff card where the log has
    # one, else the basics from the schedule.
    cards = []
    for gid, g in sorted(g_by.items(), key=lambda kv: (info[kv[0]]["kickoff"] or "", kv[0])):
        base = {"game_id": gid, "home": g["home_team"], "away": g["away_team"], "gameday": g["gameday"],
                "gametime": g["gametime"], "roof": g.get("roof")}
        cards.append({**base, **(log.get("games", {}).get(gid) or {}),
                      "home_score": g.get("home_score"), "away_score": g.get("away_score")})
    return {"season": season, "week": week, "source": log.get("source", "live"), "game_info": info, "cards": cards,
            "games": len(g_by), "games_final": len(final_games),
            "n_final": len(done), "counts": count,
            "avg_miss": round(sum(abs(r["miss"]) for r in done) / len(done), 1) if done else None,
            "in_range": round(sum(1 for r in done if r["in_range"]) / len(done), 3) if done else None,
            "summary": summary, "rows": players}


def build(data_out: Path, season: int, log=print) -> dict | None:
    data_out = Path(data_out)
    logdir = data_out / "projection-log"
    if not logdir.exists():
        return None
    scores = _rows(data_out / f"scores-{season}.json")
    defense = _rows(data_out / f"defense-{season}.json")
    games = _rows(data_out / f"games-{season}.json")
    outdir = data_out / "results"
    outdir.mkdir(exist_ok=True)
    weeks, proj_by_player = [], {}
    for f in sorted(logdir.glob(f"{season}-w*.json")):
        wlog = json.loads(f.read_text())
        week = int(f.stem.split("-w")[1])
        res = week_results(season, week, wlog, scores, defense, games)
        if not res["rows"]:
            continue
        (outdir / f"{season}-w{week:02d}.json").write_text(json.dumps(res))
        weeks.append({k: res[k] for k in ("week", "source", "games", "games_final", "n_final", "counts",
                                           "avg_miss", "in_range", "summary")})
        for r in res["rows"]:
            if r["pos"] != "DEF":
                proj_by_player.setdefault(r["id"], {})[str(week)] = [r["proj"], r["lo"], r["hi"], r["status"]]
    if not weeks:
        return None
    log(f"[results] {season}: weeks {[w['week'] for w in weeks]}, latest week {weeks[-1]['week']} "
        f"{weeks[-1]['n_final']} final rows, avg miss {weeks[-1]['avg_miss']}")
    return {"season": season, "weeks": weeks, "players": proj_by_player}
