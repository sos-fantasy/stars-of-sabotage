"""Top-N saboteur lists for social cards: one game, or every Sunday afternoon game.

Reads the same JSON files the site serves (data/scores-YYYY.json,
data/defense-YYYY.json, data/games-YYYY.json) and config/scoring.yml.
Every number on a card comes from those files; check_rows() refuses to build
a card whose parts do not add up to the published Sabotage points.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

NICK = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers", "CHI": "Bears",
    "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs", "LA": "Rams", "LAR": "Rams",
    "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins", "MIN": "Vikings", "NE": "Patriots", "NO": "Saints",
    "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks", "SF": "49ers",
    "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}
DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
NIGHT = "19:00"  # kickoff at or after 7 PM ET counts as a night game


class CardError(Exception):
    """The data cannot support a correct card. The runner skips the card and fails loudly."""


def scoring() -> dict:
    return yaml.safe_load((ROOT / "config" / "scoring.yml").read_text())


def _table(path: Path) -> list[dict]:
    t = json.loads(path.read_text())
    return [dict(zip(t["cols"], r)) for r in t["rows"]]


def load(data_dir: Path, season: int) -> dict:
    return {
        "scores": _table(data_dir / f"scores-{season}.json"),
        "defense": _table(data_dir / f"defense-{season}.json"),
        "games": _table(data_dir / f"games-{season}.json"),
        "meta": json.loads((data_dir / "meta.json").read_text()),
    }


def is_night(g: dict) -> bool:
    return (g.get("gametime") or "00:00") >= NIGHT


def weekday(g: dict) -> str:
    return DAYS[date.fromisoformat(g["gameday"]).weekday()]


def is_sunday_afternoon(g: dict) -> bool:
    return weekday(g) == "SUNDAY" and not is_night(g)


def game_done(g: dict) -> bool:
    return g.get("home_score") is not None and g.get("away_score") is not None


def week_status(meta: dict, season: int, week: int) -> str:
    for w in meta.get("weeks", []):
        if w.get("week") == week and meta.get("season", season) == season:
            return w.get("status", "provisional")
    return "provisional"


# ---------- rows ----------

# (count field, points field, label, points each). "lost" and "pick six" are bonuses that stack.
PARTS = [
    ("n_incomplete", "pts_incomplete", "INC", "incomplete_pass"),
    ("n_ints", "pts_int", "INT", "interception_thrown"),
    ("n_pick_sixes", "pts_pick_six", "PICK SIX|PICK SIXES", "pick_six_thrown"),
    ("n_sacks", "pts_sacks", "SACK|SACKS", "sack_taken"),
    ("n_fumbles", "pts_fumble", "FUMBLE|FUMBLES", "fumble"),
    ("n_fumbles_lost", "pts_fumble_lost", "LOST", "fumble_lost"),
    ("n_carries", "pts_carries", "CARRY|CARRIES", "rush_attempt"),
    ("n_receptions", "pts_receptions", "REC", "reception"),
]
WORDS = {  # for captions and one-liners: (singular, plural)
    "n_incomplete": ("incompletion", "incompletions"), "n_ints": ("interception", "interceptions"),
    "n_pick_sixes": ("pick six", "pick sixes"), "n_sacks": ("sack", "sacks"),
    "n_fumbles": ("fumble", "fumbles"), "n_fumbles_lost": ("lost fumble", "lost fumbles"),
    "n_carries": ("carry", "carries"), "n_receptions": ("catch", "catches"),
    "n_fg_missed": ("missed field goal", "missed field goals"), "n_pat_missed": ("missed extra point", "missed extra points"),
}


def bucket_points(points_allowed: int, cfg: dict) -> int:
    for key, pts in cfg["defense"]["points_allowed"].items():
        k = str(key)
        if k.endswith("+"):
            if points_allowed >= int(k[:-1]):
                return pts
        elif "-" in k:
            lo, hi = (int(x) for x in k.split("-"))
            if lo <= points_allowed <= hi:
                return pts
        elif points_allowed == int(k):
            return pts
    raise CardError(f"No points-allowed bucket for {points_allowed}")


def player_item(r: dict, cfg: dict) -> dict:
    off = cfg["offense"]
    parts, check = [], 0
    for n_f, p_f, label, key in PARTS:
        n, p = int(r.get(n_f) or 0), int(r.get(p_f) or 0)
        if n * off[key] != p:
            raise CardError(f"{r['player_display_name']}: {n_f}={n} x {off[key]} != {p_f}={p}")
        check += p
        if n:
            bonus = key in ("fumble_lost", "pick_six_thrown")
            one, _, many = label.partition("|")
            parts.append({"n": n, "label": one if n == 1 or not many else many, "each": off[key], "pts": p,
                          "bonus": bonus, "field": n_f})
    kick = int(r.get("pts_kicking") or 0)
    check += kick
    fg, pat = int(r.get("n_fg_missed") or 0), int(r.get("n_pat_missed") or 0)
    if kick and not (fg or pat):
        raise CardError(f"{r['player_display_name']}: kicking points with no misses")
    if fg:
        parts.append({"n": fg, "label": "MISSED FG" if fg == 1 else "MISSED FGS", "each": None, "pts": None, "bonus": False, "field": "n_fg_missed"})
    if pat:
        parts.append({"n": pat, "label": "MISSED PAT" if pat == 1 else "MISSED PATS", "each": None, "pts": None, "bonus": False, "field": "n_pat_missed"})
    if check != int(r["sabotage_pts"]):
        raise CardError(f"{r['player_display_name']}: parts add to {check}, data says {r['sabotage_pts']}")
    return {
        "kind": "player", "name": r["player_display_name"], "pos": r["position"], "team": r["team"],
        "pts": int(r["sabotage_pts"]), "parts": parts, "kick_pts": kick,
    }


def defense_item(d: dict, cfg: dict) -> dict:
    pa = int(d["points_allowed"])
    if bucket_points(pa, cfg) != int(d["sabotage_pts"]):
        raise CardError(f"{d['team']} defense: {pa} allowed should score {bucket_points(pa, cfg)}, data says {d['sabotage_pts']}")
    return {"kind": "defense", "name": f"{NICK.get(d['team'], d['team'])} defense", "pos": "DEF", "team": d["team"],
            "pts": int(d["sabotage_pts"]), "points_allowed": pa, "bucket": d.get("pa_bucket"), "parts": []}


def stat_line(item: dict) -> str:
    """'10 INC X2 · 2 INT X10 · 1 SACK X5'. Bonuses read '+10'. Uppercase by design."""
    if item["kind"] == "defense":
        b = item.get("bucket") or ""
        return f"ALLOWED {item['points_allowed']} POINTS" + (f" ({b} BUCKET)" if b else "")
    bits = []
    for p in item["parts"]:
        if p["each"] is None:
            bits.append(f"{p['n']} {p['label']}")
        elif p["bonus"]:
            bits.append(f"{p['n']} {p['label']} +{p['each']}" if p["n"] == 1 else f"{p['n']} {p['label']} +{p['each']} EACH")
        else:
            bits.append(f"{p['n']} {p['label']} X{p['each']}")
    if item.get("kick_pts"):
        bits.append(f"= {item['kick_pts']} KICKING")
    return " · ".join(bits)


def fact_words(item: dict, limit: int = 3) -> str:
    """'2 interceptions, 10 incompletions and 11 carries', biggest point sources first."""
    if item["kind"] == "defense":
        return f"{item['points_allowed']} points allowed"
    parts = sorted([p for p in item["parts"] if not p["bonus"]], key=lambda p: -(p["pts"] or 99))[:limit]
    words = []
    for p in parts:
        one, many = WORDS[p["field"]]
        words.append(f"{p['n']} {one if p['n'] == 1 else many}")
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def cut_top(items: list[dict], n: int = 7, floor: int = 5) -> list[dict]:
    """Highest first. Never end on a split tie: shrink the list until the last
    included score beats the first excluded one. If that would go below `floor`,
    keep the whole tie instead (list may run longer than n only then... capped at n+2)."""
    items = sorted(items, key=lambda x: (-x["pts"], x["name"]))
    if len(items) <= n:
        k = len(items)
    else:
        k = n
        while k > 0 and items[k - 1]["pts"] == items[k]["pts"]:
            k -= 1
        if k < floor:
            k = n
            while k < len(items) and items[k]["pts"] == items[n - 1]["pts"] and k < n + 2:
                k += 1
    out = items[:k]
    for i, it in enumerate(out):
        first = next(j for j, x in enumerate(out) if x["pts"] == it["pts"])
        tied = sum(1 for x in items if x["pts"] == it["pts"]) > 1
        it["rank"] = f"T-{first + 1}" if tied else str(first + 1)
    return out


def _items(data: dict, week: int, teams: set[str], cfg: dict) -> list[dict]:
    rows = [player_item(r, cfg) for r in data["scores"]
            if r["week"] == week and r["team"] in teams and int(r["sabotage_pts"] or 0) > 0]
    rows += [defense_item(d, cfg) for d in data["defense"] if d["week"] == week and d["team"] in teams]
    return rows


def pick(seed: str, options: list) -> object:
    """Deterministic choice: the same card always gets the same line, different cards vary."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return options[h % len(options)]


ONE_LINERS = [
    "{name} led the wreckage with {facts}.",
    "{name} turned {facts} into {pts} Sabotage points.",
    "Nobody broke more things than {name}: {facts}, worth {pts} points.",
    "{name} put up {pts} Sabotage points on {facts}.",
    "The {nick} will want a word with {name} about {facts}.",
    "{facts}. That was {name}, and it was worth {pts} points.",
]
DEFENSE_LINERS = [
    "The {nick} defense allowed {pa} points and topped the list with {pts}.",
    "{pa} points allowed. The {nick} defense held the door open all game.",
]


def one_liner(card_id: str, top: dict) -> str:
    if top["kind"] == "defense":
        t = pick(card_id, DEFENSE_LINERS)
        return t.format(nick=NICK.get(top["team"], top["team"]), pa=top["points_allowed"], pts=top["pts"])
    t = pick(card_id, ONE_LINERS)
    s = t.format(name=top["name"], facts=fact_words(top), pts=top["pts"], nick=NICK.get(top["team"], top["team"]))
    return s[0].upper() + s[1:]


def _date_label(gameday: str) -> str:
    d = date.fromisoformat(gameday)
    return f"{MONTHS[d.month - 1]} {d.day}"


def game_card(data: dict, game: dict, season: int, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring()
    if not game_done(game):
        raise CardError(f"{game['game_id']} has no final score yet")
    teams = {game["home_team"], game["away_team"]}
    items = _items(data, game["week"], teams, cfg)
    if len({i["team"] for i in items if i["kind"] == "player"}) < 2:
        raise CardError(f"{game['game_id']}: player rows missing for one team")
    top = cut_top(items)
    status = week_status(data["meta"], season, game["week"])
    away, home = game["away_team"], game["home_team"]
    a_s, h_s = int(game["away_score"]), int(game["home_score"])
    lines = [(NICK[away], a_s), (NICK[home], h_s)]
    lines.sort(key=lambda x: -x[1])  # winner on top
    when = weekday(game) + (" NIGHT" if is_night(game) else "")
    cid = f"game-{game['game_id']}"
    return {
        "id": cid, "type": "game", "season": season, "week": game["week"], "status": status,
        "eyebrow": f"TOP {len(top)} SABOTEURS",
        "sub": f"WEEK {game['week']} · {when} · {_date_label(game['gameday'])}" + (" · PROVISIONAL" if status != "final" else ""),
        "headline": lines, "rows": top, "blurb": one_liner(cid, top[0]),
        "matchup": f"{NICK[away]} {a_s}, {NICK[home]} {h_s}" if a_s >= h_s else f"{NICK[home]} {h_s}, {NICK[away]} {a_s}",
    }


def wreckage_card(data: dict, season: int, week: int, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring()
    games = [g for g in data["games"] if g["week"] == week and is_sunday_afternoon(g)]
    if not games:
        raise CardError(f"Week {week} has no Sunday afternoon games")
    if not all(game_done(g) for g in games):
        raise CardError(f"Week {week}: Sunday afternoon games not all final")
    teams = {g["home_team"] for g in games} | {g["away_team"] for g in games}
    items = _items(data, week, teams, cfg)
    top = cut_top(items)
    status = week_status(data["meta"], season, week)
    cid = f"wreckage-{season}-{week:02d}"
    sunday = games[0]["gameday"]
    return {
        "id": cid, "type": "wreckage", "season": season, "week": week, "status": status,
        "eyebrow": f"TOP {len(top)} SABOTEURS",
        "sub": f"WEEK {week} · SUNDAY · {_date_label(sunday)} · {len(games)} GAMES" + (" · PROVISIONAL" if status != "final" else ""),
        "headline": [("Sunday", None), ("Wreckage", None)], "rows": top, "blurb": one_liner(cid, top[0]),
        "matchup": f"the {len(games)} Sunday afternoon games",
    }


# ---------- captions ----------

def captions(card: dict) -> dict:
    tail = ("Provisional until stat corrections close Thursday." if card["status"] != "final" else "Final numbers.")
    if card["type"] == "game":
        mid = f"Top {len(card['rows'])} saboteurs from {card['matchup']}. Week {card['week']}. {tail}"
    else:
        mid = f"Top {len(card['rows'])} saboteurs from {card['matchup']} of week {card['week']}. {tail}"
    return {
        "instagram": f"{card['blurb']}\n\n{mid}\n\nWeekly rankings at starsofsabotage.com (link in bio).\n\n#fantasyfootball #fantasyfootballhumor",
        "facebook": f"{card['blurb']}\n\n{mid}\n\nWeekly rankings: https://starsofsabotage.com",
        "pinterest": json.dumps(pinterest_caption(card, mid), ensure_ascii=False, indent=1),
    }


def pinterest_caption(card: dict, mid: str) -> dict:
    """Pin title, description and alt text. The Pin links to the site, so no 'link in bio'."""
    n, w = len(card["rows"]), card["week"]
    where = f"{card['matchup']} (week {w})" if card["type"] == "game" else f"{card['matchup']} of week {w}"
    rows = "; ".join(f"{r['rank']}. {r['name']} {r['team']} {r['pts']}" for r in card["rows"])
    return {
        "title": f"Top {n} fantasy football saboteurs from {where}",
        # No "provisional" note: Pins stay in search for weeks, long after stat corrections close.
        "description": f"{card['blurb']} Top {n} saboteurs from {where}. Every player ranked by the plays that hurt his team at starsofsabotage.com.",
        "link": "https://starsofsabotage.com/",
        "alt_text": f"Stars of Sabotage card ranking the top {n} saboteurs from {where}, with Sabotage points: {rows}.",
    }
