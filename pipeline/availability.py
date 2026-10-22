"""Who is hurt and who starts: injury tags and depth charts for the site.

Sources (all nflverse, refreshed by nflverse at least daily):
- load_injuries: the league's weekly injury report. report_status is the game
  designation (Questionable, Doubtful, Out), posted on the final report of the week;
  practice_status is that week's practice participation.
- load_rosters_weekly: roster status codes. Checked against news reports on
  October 21, 2026: R01 injured reserve; R48 injured reserve, designated to return
  (James Conner); R04 reserve/PUP (Micah Parsons); R05 reserve/non-football injury
  (Giovanni Manu); R40 suspended (Montez Sweat). EXE is the commissioner's exempt
  list (nflreadr roster status dictionary).
- load_depth_charts: depth charts (ESPN player ids), snapshots once or twice a day. Players on
  injured reserve stay listed at the bottom, so availability is applied here.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

ROSTER_STATUS = {"R01": "IR", "R48": "IR, designated to return", "R04": "PUP", "R05": "NFI",
                 "R40": "Suspended"}
# Statuses that keep a player off the field this week. Doubtful players rarely play,
# so they are skipped too (owner, October 19).
UNAVAILABLE = {"Out", "Doubtful", "IR", "IR, designated to return", "PUP", "NFI", "Suspended", "Exempt list"}
SEVERITY = {"Questionable": "q", "Doubtful": "d", "Did not practice": "p", "Limited practice": "p"}
PRACTICE = {"Did Not Participate In Practice": "Did not practice", "Limited Participation in Practice": "Limited practice"}

# ESPN lists most kickers as PK; a few (Tyler Bass, Matt Gay, Cairo Santos) as K.
DEPTH_POS = [("QB", ("QB",), 1), ("RB", ("RB",), 2), ("WR", ("WR",), 3), ("TE", ("TE",), 2), ("K", ("PK", "K"), 1)]


def _injury_text(r: dict) -> str | None:
    parts = [r.get("report_primary_injury") or r.get("practice_primary_injury"),
             r.get("report_secondary_injury") or r.get("practice_secondary_injury")]
    seen = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    return ", ".join(seen) or None


def roster_status(status: str | None, abbr: str | None) -> str | None:
    if status == "EXE":
        return "Exempt list"
    if status == "RES":
        return ROSTER_STATUS.get(abbr)
    return None


def injury_tags(inj: pl.DataFrame, roster: pl.DataFrame | None, week: int) -> dict[str, dict]:
    """One tag per player who has one: {status, injury, week, team}.

    Order of precedence for status:
    1. The game designation on this week's report (Questionable, Doubtful, Out).
    2. A reserve status from the roster (IR, PUP, NFI, Suspended, Exempt list).
    3. This week's practice participation, before the game designation is posted
       (Did not practice, Limited practice). Full participation gets no tag.
    4. If a team has no report yet this week (Monday and Tuesday), last week's
       game designation, marked with that week so it is not mistaken for current.
    The injury is the body part on the report; for players on a reserve list it is
    the last body part listed for him this season, when there is one."""
    tags: dict[str, dict] = {}
    inj = inj.filter(pl.col("gsis_id").is_not_null() & (pl.col("week") <= week))
    teams_this_week = set(inj.filter(pl.col("week") == week)["team"].unique().to_list())
    last_injury = {}
    for r in inj.sort("week").iter_rows(named=True):
        t = _injury_text(r)
        if t and not t.lower().startswith("not injury related"):
            last_injury[r["gsis_id"]] = t

    # 4: last week's designations for teams without a report yet
    prev = inj.filter((pl.col("week") == week - 1) & ~pl.col("team").is_in(list(teams_this_week))
                      & pl.col("report_status").is_not_null())
    for r in prev.iter_rows(named=True):
        tags[r["gsis_id"]] = {"status": r["report_status"], "injury": _injury_text(r), "week": week - 1, "team": r["team"]}

    # 3 and 1: this week's report
    for r in inj.filter(pl.col("week") == week).iter_rows(named=True):
        s = r.get("report_status") or PRACTICE.get(r.get("practice_status") or "")
        if s:
            tags[r["gsis_id"]] = {"status": s, "injury": _injury_text(r), "week": week, "team": r["team"]}

    # 2: roster reserve lists override practice tags but not this week's designation
    if roster is not None and roster.height:
        rw = roster.filter(pl.col("week") == roster["week"].max())
        for r in rw.iter_rows(named=True):
            s = roster_status(r.get("status"), r.get("status_description_abbr"))
            pid = r.get("gsis_id")
            if not s or not pid:
                continue
            cur = tags.get(pid)
            if cur and cur["week"] == week and cur["status"] in ("Questionable", "Doubtful", "Out"):
                continue
            tags[pid] = {"status": s, "injury": last_injury.get(pid), "week": None, "team": r["team"]}
    for v in tags.values():
        v["level"] = "out" if v["status"] in UNAVAILABLE - {"Doubtful"} else SEVERITY.get(v["status"], "q")
    return tags


def unavailable_ids(tags: dict[str, dict], week: int) -> set[str]:
    """Players to skip when picking this week's starters. Last week's designation
    does not count: a player out last week may be back."""
    return {pid for pid, t in tags.items()
            if t["status"] in UNAVAILABLE and (t["week"] is None or t["week"] == week)}


def complete_snapshots(dc: pl.DataFrame, share: float = 0.9) -> pl.DataFrame:
    """Drop snapshots that came through partial: fewer rows than 90% of the team's
    median snapshot size. New England's of October 21 had 56 rows against a usual 78."""
    n = dc.group_by(["team", "dt"]).len()
    # Median over the team's last 14 days of snapshots, so 90-man preseason charts
    # do not set the bar.
    last = n.group_by("team").agg(pl.col("dt").max().alias("_last"))
    recent = n.join(last, on="team").filter(
        pl.col("dt").str.to_datetime(time_zone="UTC") >= pl.col("_last").str.to_datetime(time_zone="UTC") - pl.duration(days=14))
    med = recent.group_by("team").agg(pl.col("len").median().alias("_med"))
    ok = n.join(med, on="team").filter(pl.col("len") >= share * pl.col("_med")).select("team", "dt")
    return dc.join(ok, on=["team", "dt"])


def _latest(dc: pl.DataFrame, before: str | None = None) -> pl.DataFrame:
    d = dc if before is None else dc.filter(pl.col("dt") <= before)
    if not d.height:
        return d
    m = d.group_by("team").agg(pl.col("dt").max().alias("_m"))
    return d.join(m, on="team").filter(pl.col("dt") == pl.col("_m")).drop("_m")


def _ranked(snap: pl.DataFrame, abbs: tuple) -> dict[str, list[dict]]:
    """Each team's list at one position, best rank first, one row per player."""
    sub = (snap.filter(pl.col("pos_abb").is_in(list(abbs)))
           .with_columns(pl.coalesce("gsis_id", pl.col("player_name")).alias("_key"))
           .sort("pos_rank").unique(["team", "_key"], keep="first").sort(["team", "pos_rank"]))
    out: dict[str, list[dict]] = {}
    for r in sub.iter_rows(named=True):
        out.setdefault(r["team"], []).append(r)
    return out


def depth_charts(dc: pl.DataFrame, tags: dict[str, dict], out_ids: set[str], now: datetime) -> dict:
    """Per team, per position: the depth chart in order, with injury tags, who starts
    this week after skipping unavailable players, who he starts in place of, and how
    each player's spot compares with the chart from a week earlier."""
    dc = complete_snapshots(dc)
    cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    teams: dict[str, dict] = {}
    for pos, abbs, n in DEPTH_POS:
        # Latest snapshot that lists this position: some snapshots arrive partial
        # (New England's of October 21 had no receivers or kicker).
        sub = dc.filter(pl.col("pos_abb").is_in(list(abbs)))
        cur, prev = _latest(sub), _latest(sub, cutoff)
        now_lists, prev_lists = _ranked(cur, abbs), _ranked(prev, abbs) if prev.height else {}
        for team, rows in now_lists.items():
            before = {(r["gsis_id"] or r["player_name"]): i + 1 for i, r in enumerate(prev_lists.get(team, []))}
            had_prev = team in prev_lists
            entries, starters, skipped = [], 0, []
            for i, r in enumerate(rows):
                pid = r["gsis_id"]
                key = pid or r["player_name"]
                e = {"id": pid, "name": r["player_name"], "rank": i + 1,
                     "prev_rank": before.get(key) if had_prev else None, "new": had_prev and key not in before}
                if pid in out_ids:
                    e["start"] = False
                    if i < n:
                        skipped.append(r["player_name"])
                elif starters < n:
                    starters += 1
                    e["start"] = True
                    e["slot"] = pos if n == 1 else f"{pos}{starters}"
                    if i >= n and skipped:
                        e["in_for"] = skipped.pop(0)
                else:
                    e["start"] = False
                t = tags.get(pid) if pid else None
                if t:
                    e["tag"] = {k: t[k] for k in ("status", "injury", "week", "level")}
                entries.append(e)
            tm = teams.setdefault(team, {"updated": {}})
            tm[pos] = entries
            tm["updated"][pos] = rows[0]["dt"]
    return teams


def slots(teams: dict) -> dict[str, dict]:
    """Player id -> {team, pos, rank, slot}: his place on his team's chart, for other pages."""
    out = {}
    for team, t in teams.items():
        for pos in ("QB", "RB", "WR", "TE", "K"):
            for e in t.get(pos, []):
                if e["id"]:
                    out[e["id"]] = {"team": team, "pos": pos, "rank": e["rank"], "slot": e.get("slot"),
                                    "in_for": e.get("in_for")}
    return out


def starters(teams: dict) -> pl.DataFrame:
    """This week's starters from depth_charts(), in the shape projections expects."""
    rows = [{"player_id": e["id"], "player_display_name": e["name"], "position": pos, "team": team, "slot": e["slot"]}
            for team, t in teams.items() for pos, _, _ in DEPTH_POS for e in t.get(pos, []) if e.get("start") and e["id"]]
    return pl.DataFrame(rows, schema={"player_id": pl.Utf8, "player_display_name": pl.Utf8, "position": pl.Utf8,
                                      "team": pl.Utf8, "slot": pl.Utf8})


USAGE_POS = ("QB", "RB", "WR", "TE", "K")


def add_usage(depth: dict, scores: pl.DataFrame, snaps: pl.DataFrame | None, season: int) -> dict:
    """Week-by-week usage for every player on a depth chart, this season.

    A game counts if he has a stat line (nflverse player stats) or any snaps (nflverse
    snap counts, from Pro Football Reference). Snap counts matter: about one in nine
    skill-position appearances has snaps but no stat line (Case Keenum, CHI week 4,
    1% of snaps). Snap % is the share of the team's offensive snaps. Route
    participation is not published for the current season, so snap share stands in.

    Per team: `games`, the weeks the team played (byes left out), and `usage`, per
    player [week, carries, targets, snap %, Sabotage points, played]. Weeks the team
    played without him are filled with zeros and played = 0, so the usage lines run
    through every game (owner, October 22). Only his games for this team count, so a
    traded player's old team does not show as usage. Each entry also gets `last`: his
    most recent game, for any team."""
    sc = scores.filter(pl.col("season") == season).select(
        "player_id", "team", pl.col("week").cast(pl.Int64), "n_carries", "n_targets", "sabotage_pts")
    if snaps is not None and snaps.height:
        cols = ["player_id", pl.col("week").cast(pl.Int64), "offense_pct"]
        if "team" in snaps.columns:
            cols.append(pl.col("team").alias("team_snap"))
        sn = snaps.filter(pl.col("season") == season).select(*cols).unique(["player_id", "week"])
        if "team_snap" not in sn.columns:
            sn = sn.with_columns(pl.lit(None, dtype=pl.Utf8).alias("team_snap"))
        cur = sc.join(sn, on=["player_id", "week"], how="full", coalesce=True)
        cur = cur.with_columns(pl.coalesce("team", "team_snap").alias("team")).drop("team_snap")
    else:
        cur = sc.with_columns(pl.lit(None, dtype=pl.Float64).alias("offense_pct"))
    cur = cur.filter(pl.col("team").is_not_null()).with_columns(
        [pl.col(c).fill_null(0) for c in ("n_carries", "n_targets", "sabotage_pts")])
    games: dict[str, list] = {}
    team_weeks: dict[str, set] = {}
    for r in cur.sort("week").iter_rows(named=True):
        pct = None if r["offense_pct"] is None else int(round(r["offense_pct"] * 100))
        games.setdefault(r["player_id"], []).append(
            [r["week"], r["n_carries"], r["n_targets"], pct, r["sabotage_pts"], r["team"]])
        team_weeks.setdefault(r["team"], set()).add(r["week"])
    weeks = sorted({w for ws in team_weeks.values() for w in ws})
    for team, t in depth["teams"].items():
        tw = sorted(team_weeks.get(team, set()))
        usage = {}
        for pos in USAGE_POS:
            for e in t.get(pos, []):
                gs = games.get(e["id"]) if e["id"] else None
                if not gs:
                    continue
                last = gs[-1]
                e["last"] = {"week": last[0], "car": last[1], "tgt": last[2], "snap": last[3], "pts": last[4],
                             "team": last[5]}
                mine = {g[0]: g[:5] + [1] for g in gs if g[5] == team}
                if mine and pos != "K":
                    usage[e["id"]] = [mine.get(w, [w, 0, 0, 0, 0, 0]) for w in tw]
        t["usage"] = usage
        t["games"] = tw
    depth["weeks"] = weeks
    return depth


def build(season: int, week: int, now: datetime, log=print) -> tuple[dict | None, dict | None, set[str]]:
    """Returns (injuries.json, depth.json, unavailable ids). Each part fails on its own."""
    import nflreadpy as nfl
    tags, out_ids, injuries, depth = {}, set(), None, None
    try:
        inj = nfl.load_injuries(season)
    except Exception as e:
        log(f"[availability] injury report unavailable: {e}")
        inj = None
    try:
        roster = nfl.load_rosters_weekly(season)
    except Exception as e:
        log(f"[availability] rosters unavailable: {e}")
        roster = None
    if inj is not None or roster is not None:
        tags = injury_tags(inj if inj is not None else pl.DataFrame(schema={"gsis_id": pl.Utf8, "week": pl.Int32, "team": pl.Utf8}),
                           roster, week)
        out_ids = unavailable_ids(tags, week)
        injuries = {"season": season, "week": week, "generated": now.isoformat(timespec="minutes"),
                    "report_week": int(inj.filter(pl.col("week") <= week)["week"].max()) if inj is not None and inj.height else None,
                    "players": tags}
    try:
        teams = depth_charts(nfl.load_depth_charts(season), tags, out_ids, now)
        depth = {"season": season, "week": week, "generated": now.isoformat(timespec="minutes"),
                 "teams": teams, "slots": slots(teams)}
    except Exception as e:
        log(f"[availability] depth charts unavailable: {e}")
    log(f"[availability] week {week}: {len(tags)} tagged players, {len(out_ids)} unavailable, "
        f"{len(depth['teams']) if depth else 0} depth charts")
    return injuries, depth, out_ids
