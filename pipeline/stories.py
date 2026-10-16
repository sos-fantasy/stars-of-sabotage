"""Weekly highlight stories: the one place on the site that gets a voice.

Tone: a witty, free-spirited announcer with a soft spot for disaster.
Smart, light schadenfreude, never mean about injuries or people off the
field. Every number comes from the scored data; the jokes wrap facts and
never replace them. House style: no em dashes, no AI filler phrases.

A template is picked by a stable hash so a story does not reshuffle every
time the pipeline reruns.
"""
from __future__ import annotations

import hashlib

TEMPLATES = {
    "top": [
        "{name} played quarterback like a man returning a rental car he never planned to see again. {line}. {pts} points.",
        "{name} treated the pocket like a hot stove and every pass like a rumor he could not confirm. {line}. {pts} points.",
        "Somewhere {a_opp} defensive coordinator is framing the tape. {name} supplied {line}, worth {pts} points.",
        "{name} ran the offense the way a raccoon runs a campsite: busy, loud, and leaving a mess for someone else. {line}. {pts} points.",
    ],
    "top_nonqb": [
        "{name} found new and creative ways to be a problem for his own offense. {line}. {pts} points.",
        "{name} gave the opposing defense more help than its own coaching staff did. {line}. {pts} points.",
        "Every offense has a weak link. {name} applied for the job and got it. {line}. {pts} points.",
    ],
    "pick_six": [
        "{name} threw a pass so well placed for the {opp} it should count as a charitable donation. Returned for six. {p6pts} points from one throw.",
        "Every quarterback has a favorite target. For one snap, {name}'s wore {a_opp} jersey and had a clear lane to the end zone. {p6pts} points, no extra charge.",
        "{name} found the open man. Wrong team, right result. Pick six, {p6pts} points in a single throw.",
    ],
    "fumbles": [
        "{name} handled the football like a bar of soap in a hot shower. {fum} fumbles, {lost} lost, {fpts} points from fumbles alone.",
        "{name} put the ball on the turf {fum} times. Gravity remains undefeated. {fpts} fumble points.",
        "{name} carried the ball like it owed him money and he wanted it gone. {fum} fumbles, {lost} lost, {fpts} points.",
    ],
    "kicker": [
        "{name} lined up, swung, and gave the uprights a respectful amount of personal space. {kline}. {pts} points.",
        "{name} kicks the way a weather forecast predicts: confidently, and often wrong. {kline}. {pts} points.",
        "{name} was paid to split the uprights and chose diplomacy instead. {kline}. {pts} points.",
    ],
    "defense": [
        "The {team} defense hosted the {opp} like an open house with free parking. {pa} points allowed, {pts} for the ledger.",
        "The {team} guarded their end zone like a revolving door at a department store sale. {pa} allowed to the {opp}. {pts} points.",
        "Somewhere {a_team} safety is still pointing at the receiver he was supposed to cover. The {opp} put up {pa}. {pts} points.",
    ],
}

NICK = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers", "CHI": "Bears",
    "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs", "LA": "Rams", "LAR": "Rams",
    "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins", "MIN": "Vikings", "NE": "Patriots", "NO": "Saints",
    "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks", "SF": "49ers",
    "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}


def nick(abbr: str, season: int | None = None) -> str:
    """Team nickname. nflverse uses current codes for old seasons, so names that
    changed are resolved by season (Washington is the only nickname change since 1999;
    relocated teams kept their nicknames)."""
    if abbr == "WAS" and season is not None:
        if season <= 2019:
            return "Redskins"
        if season <= 2021:
            return "Washington Football Team"
    return NICK.get(abbr, abbr)


def a_an(word: str) -> str:
    return ("an " if word[:1].upper() in "AEIOU" else "a ") + word


LABELS = {
    "top": "Saboteur of the week",
    "top_nonqb": "Best non-QB saboteur",
    "pick_six": "Pick six",
    "fumbles": "Butterfingers award",
    "kicker": "Kicker of the week",
    "defense": "Defense of the week",
}


def _pick(kind: str, key: str) -> str:
    opts = TEMPLATES[kind]
    h = int(hashlib.sha256(f"{kind}|{key}".encode()).hexdigest(), 16)
    return opts[h % len(opts)]


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def stat_line(r: dict) -> str:
    parts = []
    if r["n_incomplete"]:
        parts.append(_plural(r["n_incomplete"], "incompletion"))
    if r["n_sacks"]:
        parts.append(_plural(r["n_sacks"], "sack"))
    if r["n_ints"]:
        parts.append(_plural(r["n_ints"], "interception"))
    if r["n_fumbles"]:
        parts.append(_plural(r["n_fumbles"], "fumble"))
    if r["n_carries"]:
        parts.append(_plural(r["n_carries"], "carry", "carries"))
    if r["n_receptions"]:
        parts.append(_plural(r["n_receptions"], "catch", "catches"))
    parts = parts[:4]
    if len(parts) > 1:
        return (", ".join(parts[:-1]) + ", and " + parts[-1]).capitalize()
    return parts[0].capitalize() if parts else "A quiet box score"


def kick_line(r: dict) -> str:
    bits = []
    misses = [d for d in (r.get("fg_missed_list") or "").split(";") if d]
    blocks = [d for d in (r.get("fg_blocked_list") or "").split(";") if d]
    if misses:
        bits.append("Missed from " + _join([f"{d}" for d in misses]))
    if blocks:
        bits.append("blocked from " + _join(blocks))
    if r["n_pat_missed"]:
        bits.append(_plural(r["n_pat_missed"], "extra point") + " missed or blocked")
    text = ", ".join(bits) if bits else "A tidy day"
    return text[0].upper() + text[1:]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build(week: int, players: list[dict], defenses: list[dict], season: int) -> list[dict]:
    """players: scored rows for one week (dicts). defenses: defense rows for one week."""
    out = []
    key = lambda r: f"{season}-{week}-{r.get('player_id', r.get('team'))}"
    ranked = sorted(players, key=lambda r: (-r["sabotage_pts"], r["player_display_name"]))
    top_is_qb = bool(ranked) and ranked[0]["position"] == "QB"
    if ranked and ranked[0]["sabotage_pts"] > 0:
        r = ranked[0]
        kind = "top" if top_is_qb else "top_nonqb"
        s = _story(kind, r, key(r), name=r["player_display_name"], a_opp=a_an(nick(r["opponent_team"])),
                   line=stat_line(r), pts=r["sabotage_pts"])
        s["label"] = LABELS["top"]
        out.append(s)
    top_id = ranked[0]["player_id"] if ranked else None
    fum = sorted([r for r in players if r["n_fumbles"] >= 2], key=lambda r: (-r["pts_fumbles"], r["player_display_name"]))
    fum = [r for r in fum if r["player_id"] != top_id] or fum   # avoid featuring the same player twice
    fum_id = fum[0]["player_id"] if fum else None
    nonqb = [r for r in ranked if r["position"] not in ("QB", "K") and r["player_id"] != fum_id]
    if top_is_qb and nonqb and nonqb[0]["sabotage_pts"] > 0:
        r = nonqb[0]
        out.append(_story("top_nonqb", r, key(r), name=r["player_display_name"],
                          line=stat_line(r), pts=r["sabotage_pts"]))
    p6 = sorted([r for r in players if r["n_pick_sixes"] > 0], key=lambda r: (-r["n_pick_sixes"], -r["sabotage_pts"]))
    if p6:
        r = p6[0]
        out.append(_story("pick_six", r, key(r), name=r["player_display_name"], opp=nick(r["opponent_team"]),
                          a_opp=a_an(nick(r["opponent_team"])), p6pts=r["p6_value"]))
    if fum:
        r = fum[0]
        out.append(_story("fumbles", r, key(r), name=r["player_display_name"], fum=r["n_fumbles"],
                          lost=r["n_fumbles_lost"], fpts=r["pts_fumbles"]))
    ks = sorted([r for r in players if r["position"] == "K" and r["pts_kicking"] > 0],
                key=lambda r: (-r["pts_kicking"], r["player_display_name"]))
    if ks:
        r = ks[0]
        out.append(_story("kicker", r, key(r), name=r["player_display_name"], kline=kick_line(r), pts=r["pts_kicking"]))
    ds = sorted(defenses, key=lambda d: (-d["sabotage_pts"], -d["points_allowed"], d["team"]))
    if ds and ds[0]["sabotage_pts"] > 0:
        d = ds[0]
        out.append(_story("defense", d, f"{season}-{week}-{d['team']}", team=nick(d["team"]), opp=nick(d["opponent"]),
                          a_team=a_an(nick(d["team"])),
                          pa=d["points_allowed"], pts=d["sabotage_pts"]))
    return out


def _story(kind: str, row: dict, key: str, **fields) -> dict:
    who = row.get("player_display_name") or f"{nick(row['team'])} defense"
    return {"kind": kind, "label": LABELS[kind], "who": who, "team": row.get("team"),
            "text": _pick(kind, key).format(**fields)}
