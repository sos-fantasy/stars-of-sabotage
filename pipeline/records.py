"""Super Stars: single-game and single-season records for every scored stat.

Records come from the per-season data files, so they cover 1999 to now and
update as the current season plays out. Each record gets an announcer-voice
story. House style matches stories.py: every number comes from the data,
no em dashes, teams by nickname.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import yaml

from stories import a_an, nick

ROOT = Path(__file__).resolve().parent.parent
NOTES_PATH = ROOT / "config" / "record_notes.yml"
MAX_HOLDERS = 4   # list up to this many tied holders by name

# key, label, unit (singular, plural), points-per-unit lookup in config, group
STATS = [
    ("sabotage_pts", "Total Sabotage points", ("point", "points"), None, "headline"),
    ("n_incomplete", "Incomplete passes", ("incompletion", "incompletions"), ("offense", "incomplete_pass"), "passing"),
    ("n_sacks", "Sacks taken", ("sack", "sacks"), ("offense", "sack_taken"), "passing"),
    ("n_ints", "Interceptions thrown", ("interception", "interceptions"), ("offense", "interception_thrown"), "passing"),
    ("n_pick_sixes", "Pick sixes thrown", ("pick six", "pick sixes"), ("offense", "pick_six_thrown"), "passing"),
    ("n_fumbles", "Fumbles", ("fumble", "fumbles"), ("offense", "fumble"), "ball security"),
    ("n_fumbles_lost", "Fumbles lost", ("lost fumble", "lost fumbles"), ("offense", "fumble_lost"), "ball security"),
    ("n_fg_missed", "Field goals missed or blocked", ("missed field goal", "missed field goals"), None, "kicking"),
    ("n_pat_missed", "Extra points missed or blocked", ("missed extra point", "missed extra points"), ("kicker", "pat_missed"), "kicking"),
    ("points_allowed", "Points allowed (defense)", ("point", "points"), None, "defense"),
    ("n_carries", "Rushing attempts", ("carry", "carries"), ("offense", "rush_attempt"), "workload"),
    ("n_receptions", "Receptions", ("catch", "catches"), ("offense", "reception"), "workload"),
]

GROUPS = {
    "headline": "The big one",
    "passing": "Passing disasters",
    "ball security": "Ball security",
    "kicking": "Kicking",
    "defense": "Defense",
    "workload": "Workload",
}

# One or more templates per (stat, scope). Placeholders: name, team, opp, a_opp,
# season, week, value, units, pts.
TEMPLATES = {
    ("sabotage_pts", "game"): [
        "{name} turned Week {week} of {season} against the {opp} into a one-man demolition derby. {value} Sabotage points in a single game, a mark nobody has passed since 1999.",
    ],
    ("sabotage_pts", "season"): [
        "{name}'s {season} is the Sistine Chapel of sabotage: {value} points over one season, a masterpiece nobody has topped since 1999.",
    ],
    ("n_incomplete", "game"): [
        "{name} threw {value} incomplete passes against the {opp} in Week {week}, {season}. The grass at that stadium has never felt so targeted.",
    ],
    ("n_incomplete", "season"): [
        "{name} threw {value} incompletions in {season}. He kept the clock operator busy and the punter employed all year.",
    ],
    ("n_sacks", "game"): [
        "{name} was sacked {value} times by the {opp} in Week {week}, {season}. Somewhere around the eighth one it stopped being a pass rush and became a family reunion.",
    ],
    ("n_sacks", "season"): [
        "{name} went down {value} times in {season}. His offensive line ran a strict open-door policy, and every pass rusher in the league RSVP'd.",
    ],
    ("n_ints", "game"): [
        "{name} threw {value} interceptions to the {opp} in Week {week}, {season}. Their secondary left with enough souvenirs to open a gift shop.",
    ],
    ("n_ints", "season"): [
        "{name} threw {value} interceptions in {season}, spreading the wealth around the league like a quarterback with a philanthropy budget.",
    ],
    ("n_pick_sixes", "game"): [
        "{name} handed the {opp} {value} pick sixes in Week {week}, {season}. Their defense needed no playbook that day. He brought one for them.",
    ],
    ("n_pick_sixes", "season"): [
        "{name} threw {value} pick sixes in {season}. By midseason, opposing defensive backs were stretching their hamstrings for the return before the snap.",
    ],
    ("n_fumbles", "game"): [
        "{name} fumbled {value} times against the {opp} in Week {week}, {season}. The football spent the whole game looking for a more committed relationship.",
    ],
    ("n_fumbles", "season"): [
        "{name} put the ball on the turf {value} times in {season}. Gravity remains undefeated, and he gave it plenty of chances.",
    ],
    ("n_fumbles_lost", "game"): [
        "{name} lost {value} fumbles to the {opp} in Week {week}, {season}. Every one of them changed possession, which in this league is the entire point.",
    ],
    ("n_fumbles_lost", "season"): [
        "{name} gave away {value} fumbles in {season}. Generosity on that scale usually comes with a tax receipt.",
    ],
    ("n_fg_missed", "game"): [
        "{name} came up empty on {value} field goal tries against the {opp} in Week {week}, {season}. The uprights filed for a restraining order.",
    ],
    ("n_fg_missed", "season"): [
        "{name} came up empty on {value} field goal tries in {season}. Somewhere a holder is still spinning the laces and wondering what he did wrong.",
    ],
    ("n_pat_missed", "game"): [
        "{name} failed on {value} extra points against the {opp} in Week {week}, {season}. It is the kick nobody watches, and he made the whole stadium watch.",
    ],
    ("n_pat_missed", "season"): [
        "{name} failed on {value} extra points in {season}, turning the most automatic play in football into a weekly suspense thriller.",
    ],
    ("points_allowed", "game"): [
        "The {team} defense gave up {value} points to the {opp} in Week {week}, {season}. Tackling was optional that day, and nobody opted in.",
    ],
    ("points_allowed", "season"): [
        "The {season} {team} defense allowed {value} points over the season. Opposing offenses circled the {team} on the calendar in permanent marker.",
    ],
    ("n_carries", "game"): [
        "{name} carried the ball {value} times against the {opp} in Week {week}, {season}. His coach found one play he liked and refused to apologize.",
    ],
    ("n_carries", "season"): [
        "{name} logged {value} rushing attempts in {season}, more carries than a moving company in August.",
    ],
    ("n_receptions", "game"): [
        "{name} caught {value} passes against the {opp} in Week {week}, {season}. The quarterback had one read all day, and it was him.",
    ],
    ("n_receptions", "season"): [
        "{name} caught {value} passes in {season}, the most reliable checkdown in the building and a two-point toll booth on every catch.",
    ],
}


# Record alerts: a current-season line that passes or ties an all-time record.
# "{did}" is a stat-specific verb phrase, e.g. "threw 8 interceptions".
ALERT_TEMPLATES = {
    ("broken", "game"): [
        "{name} {did} against the {opp} in Week {week}, passing {prev}. Nobody since 1999 has done it in a single game. {pending}",
        "Somebody check the record book, then check it again. {name} {did} against the {opp} in Week {week}, passing {prev}. {pending}",
    ],
    ("broken", "season"): [
        "After Week {week}, {name} has {total} this season, passing {prev}. That is the most since 1999, and the season is not over. {pending}",
    ],
    ("tied", "game"): [
        "{name} {did} against the {opp} in Week {week}, matching the all-time mark held by {prev}. {pending}",
    ],
    ("tied", "season"): [
        "After Week {week}, {name} has {total} this season, level with {prev}. One more and the record changes hands. {pending}",
    ],
}
PENDING = ("Hold the confetti: the NFL can still correct stats this week. If the numbers stand until "
           "{deadline}, it goes in the book.")
OFFICIAL = "The stat-correction window has closed, so it is official."
VERBS = {
    "sabotage_pts": "scored {v} Sabotage points",
    "n_incomplete": "threw {v} incomplete passes",
    "n_sacks": "was sacked {v} times",
    "n_ints": "threw {v} interceptions",
    "n_pick_sixes": "threw {v} pick sixes",
    "n_fumbles": "fumbled {v} times",
    "n_fumbles_lost": "lost {v} fumbles",
    "n_fg_missed": "came up empty on {v} field goal tries",
    "n_pat_missed": "failed on {v} extra points",
    "points_allowed": "gave up {v} points",
    "n_carries": "carried the ball {v} times",
    "n_receptions": "caught {v} passes",
}


def _deadline_text(iso: str) -> str:
    from datetime import datetime
    d = datetime.fromisoformat(iso)
    return f"10 AM Eastern on {d:%A, %B} {d.day}"


def _prev_phrase(prev: list[dict], value: int, unit: str, kind: str) -> str:
    """Who held the record before this season, phrased for a broken or tied record."""
    p0 = prev[0]
    others = len(prev) - 1
    if kind == "broken":
        if others == 0:
            return f"{p0['name']}'s {value:,} from {p0['season']}"
        return f"the {value:,} shared by {p0['name']} ({p0['season']}) and {others} other{'s' if others > 1 else ''}"
    if others == 0:
        return f"{p0['name']} ({p0['season']})"
    return f"{p0['name']} ({p0['season']}) and {others} other{'s' if others > 1 else ''}"


def _pick(stat: str, scope: str, key: str) -> str:
    opts = TEMPLATES[(stat, scope)]
    h = int(hashlib.sha256(f"{stat}|{scope}|{key}".encode()).hexdigest(), 16)
    return opts[h % len(opts)]


def _load(data_dir: Path, seasons: list[int]) -> tuple[pl.DataFrame, pl.DataFrame]:
    P, D = [], []
    for s in seasons:
        p = json.loads((data_dir / f"scores-{s}.json").read_text())
        P.append(pl.DataFrame(p["rows"], schema=p["cols"], orient="row", infer_schema_length=None).with_columns(pl.lit(s).alias("season")))
        d = json.loads((data_dir / f"defense-{s}.json").read_text())
        D.append(pl.DataFrame(d["rows"], schema=d["cols"], orient="row", infer_schema_length=None).with_columns(pl.lit(s).alias("season")))
    return pl.concat(P), pl.concat(D)


def _per_unit(cfg: dict, path) -> int | None:
    return None if path is None else cfg[path[0]][path[1]]


def _week_info(weeks: list[dict] | None) -> dict[int, dict]:
    """status and correction deadline for each week of the current season."""
    import schedule
    from datetime import date
    info = {}
    for w in weeks or []:
        deadline = schedule.final_at(date.fromisoformat(w["last_day"])).isoformat()
        info[w["week"]] = {"status": w["status"], "final_at": deadline}
    return info


def build(data_dir: Path, seasons: list[int], cfg: dict, current_season: int,
          weeks: list[dict] | None = None) -> dict:
    notes = yaml.safe_load(NOTES_PATH.read_text()) if NOTES_PATH.exists() else {}
    players, defense = _load(Path(data_dir), seasons)
    winfo = _week_info(weeks)
    alerts = []
    out = []
    for stat, label, (one, many), unit_path, group in STATS:
        per = _per_unit(cfg, unit_path)
        recs = []
        for scope in ("game", "season"):
            if stat == "points_allowed":
                src = defense.rename({"opponent": "opponent_team"}).with_columns(
                    pl.col("team").alias("player_display_name"), pl.col("team").alias("player_id"))
            else:
                src = players
            weekly = src
            if scope == "season":
                src = (src.sort(["season", "week"]).group_by(["season", "player_id"], maintain_order=True)
                       .agg(pl.col("player_display_name").last(), pl.col("team").last(), pl.col(stat).sum(),
                            pl.len().alias("games")))
            best = src[stat].max()
            if not best:
                continue
            holders = src.filter(pl.col(stat) == best).sort(["season"] + (["week"] if scope == "game" else []))
            hl = []
            for h in holders.to_dicts():
                wk = h.get("week") if scope == "game" else 0
                note = notes.get(f"{stat}|{h['season']}|{wk}|{h['player_display_name']}")
                hl.append({
                    "name": h["player_display_name"] if stat != "points_allowed" else f"{nick(h['team'], h['season'])} defense",
                    "team": h["team"], "season": h["season"], "week": h.get("week"),
                    "opp": h.get("opponent_team") if scope == "game" else None,
                    "games": h.get("games"), "current": h["season"] == current_season,
                    **({"note": " ".join(note.split())} if note else {}),
                })
            first = holders.row(0, named=True)
            fields = dict(
                name=first["player_display_name"], team=nick(first["team"], first["season"]), season=first["season"],
                week=first.get("week"), value=f"{best:,}", units=many if best != 1 else one,
                opp=nick(first.get("opponent_team") or "", first["season"]),
                a_opp=a_an(nick(first.get("opponent_team") or "X", first["season"])),
            )
            text = _pick(stat, scope, f"{first['season']}|{first['player_id']}").format(**fields)
            pts = None
            if stat == "points_allowed":
                pts = None
            elif stat == "sabotage_pts":
                pts = best
            elif per is not None:
                pts = best * per
            rec = {"scope": scope, "value": best, "unit": many if best != 1 else one,
                   "sabotage_pts": pts, "holders": hl[:MAX_HOLDERS], "tied": len(hl), "text": text}
            alert = _alert(stat, label, scope, src, weekly, best, one, many, current_season, winfo)
            if alert:
                rec["alert"] = alert
                alerts.append({**alert, "stat": stat, "label": label, "scope": scope})
            recs.append(rec)
        out.append({"stat": stat, "label": label, "group": group, "per": per, "records": recs})
    return {"first_season": min(seasons), "last_season": max(seasons), "current_season": current_season,
            "groups": GROUPS, "stats": out, "alerts": alerts}


def _alert(stat, label, scope, src, weekly, best, one, many, season, winfo) -> dict | None:
    """If the current season holds (alone or tied) a record set before it, describe it."""
    prior = src.filter(pl.col("season") != season)
    base = prior[stat].max() if prior.height else None
    if not base:
        return None
    cur = src.filter((pl.col("season") == season) & (pl.col(stat) == best))
    if cur.height == 0 or best < base:
        return None
    kind = "broken" if best > base else "tied"
    row = cur.sort(["week"] if scope == "game" else ["player_display_name"]).row(0, named=True)
    if scope == "game":
        week = row["week"]
    else:
        # The week this season's running total first passed (or reached) the old record.
        w = (weekly.filter((pl.col("season") == season) & (pl.col("player_id") == row["player_id"]))
             .sort("week").with_columns(pl.col(stat).cum_sum().alias("cum")))
        hit = w.filter(pl.col("cum") > base) if kind == "broken" else w.filter(pl.col("cum") >= base)
        week = hit["week"][0]
    wi = winfo.get(week, {"status": "final", "final_at": None})
    prev_rows = prior.filter(pl.col(stat) == base).sort(["season"] + (["week"] if scope == "game" else []))
    is_def = stat == "points_allowed"
    prev = [{"name": (f"the {nick(r['team'], r['season'])}" if is_def else r["player_display_name"]),
             "season": r["season"]} for r in prev_rows.to_dicts()]
    unit = many if best != 1 else one
    name = f"The {nick(row['team'], season)} defense" if is_def else row["player_display_name"]
    pending = OFFICIAL if wi["status"] == "final" else PENDING.format(deadline=_deadline_text(wi["final_at"]))
    fields = dict(name=name, opp=nick(row.get("opponent_team") or "", season), week=week,
                  did=VERBS[stat].format(v=f"{best:,}"), total=f"{best:,} {unit}",
                  prev=_prev_phrase(prev, base, unit, kind), pending=pending)
    key = f"{stat}|{scope}|{season}|{row['player_id']}|{week}"
    opts = ALERT_TEMPLATES[(kind, scope)]
    text = opts[int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(opts)].format(**fields)
    official = wi["status"] == "final"
    title = ("Record " if official else "Potential record ") + ("broken" if kind == "broken" else "tied")
    return {"kind": kind, "official": official, "title": title, "week": week, "value": best, "unit": unit,
            "previous": base, "who": name if not is_def else f"{nick(row['team'], season)} defense",
            "team": row["team"], "status": wi["status"], "final_at": wi["final_at"], "text": text}
