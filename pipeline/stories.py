"""Weekly highlight stories: the one place on the site that gets a voice.

Tone: a witty, free-spirited announcer with a soft spot for disaster.
Smart, light schadenfreude, never mean about injuries or people off the
field. Every number comes from the scored data; the jokes wrap facts and
never replace them. House style: no em dashes, no AI filler phrases.

Each award has 18 lines, one per regular-season week, so the report reads fresh
every week and never reshuffles when the pipeline reruns.
"""
from __future__ import annotations


# One line per week of the regular season for each award: week 1 uses the first line,
# week 2 the second, and so on, so every week's report reads fresh. Playoff weeks wrap around.
TEMPLATES = {
    "top": [
        "{name} played quarterback like a man returning a rental car he never planned to see again. {line}. {pts} points.",
        "If the offense had a group chat, {name} is the reason it went quiet. {line}. {pts} points.",
        "Somewhere {a_opp} defensive coordinator is framing the tape. {name} supplied the material. {line}. {pts} points.",
        "{name} ran the offense the way a raccoon runs a campsite: leaving a mess for someone else. {line}. {pts} points.",
        "{name} took the snap, surveyed the field, and chose chaos. {line}. {pts} points.",
        "It must be getting close to Halloween because {name} kept seeing ghosts. {line}. {pts} points.",
        "{name} performed like a comedian who forgot his punchlines. {line}. {pts} points.",
        "The playbook said one thing. {name} had other plans. {line}. {pts} points.",
        "{name} turned a routine game into a group project nobody wanted to finish. {line}. {pts} points.",
        "Coaches spend all week installing a game plan. {name} uninstalled it. {line}. {pts} points.",
        "{name} brought the full toolkit of bad ideas and used every one. {line}. {pts} points.",
        "Film study this week will be short and painful, and {name} is the whole syllabus. {line}. {pts} points.",
        "{name} kept both offenses guessing, mostly his own. {line}. {pts} points.",
        "Somebody check the headset. {name} heard every call backwards. {line}. {pts} points.",
        "{name} gave a presentation on the art of going nowhere fast. {line}. {pts} points.",
        "{name} earned a starring role in next week's blooper reel. {line}. {pts} points.",
        "{name} plays quarterback the way a toddler plays Jenga. {line}. {pts} points.",
        "{name} found every way to stall a drive and invented a few more. {line}. {pts} points.",
    ],
    "top_nonqb": [
        "{name} found new and creative ways to be a problem for his own offense. {line}. {pts} points.",
        "{name} gave the opposing defense more help than its own coaching staff did. {line}. {pts} points.",
        "Every offense has a weak link. {name} applied for the job and got it. {line}. {pts} points.",
        "{name} touched the ball just enough to make everyone nervous. {line}. {pts} points.",
        "Nobody asked {name} to steal the show. He did it anyway, in the wrong direction. {line}. {pts} points.",
        "{name} kept the stat crew busy and his coaches pacing. {line}. {pts} points.",
        "{name} had the ball in his hands and the whole sideline holding its breath. {line}. {pts} points.",
        "Quarterbacks usually own this list. {name} crashed the party. {line}. {pts} points.",
        "{name} proved you do not need to throw a pass to wreck a drive. {line}. {pts} points.",
        "{name} turned every touch into a small adventure for his own team. {line}. {pts} points.",
        "Give {name} the ball and something happens. This week it was mostly bad. {line}. {pts} points.",
        "{name} spent the game auditioning for the other team's highlight package. {line}. {pts} points.",
        "{name} put in the kind of shift that makes an offensive coordinator stare at the ceiling. {line}. {pts} points.",
        "{name} collected touches the way some people collect parking tickets. {line}. {pts} points.",
        "Volume is a skill. So is chaos. {name} brought both. {line}. {pts} points.",
        "{name} gave his position coach a long week of film to explain. {line}. {pts} points.",
        "{name} never met a play he could not complicate. {line}. {pts} points.",
        "{name} made sure the quarterback was not the only one with explaining to do. {line}. {pts} points.",
    ],
    "pick_six": [
        "{name} threw a pass so well placed for the {opp} it should count as a charitable donation. Returned for six. {p6pts} points from one throw.",
        "Every quarterback has a favorite target. For one snap, {name}'s wore {a_opp} jersey and had a clear lane to the end zone. {p6pts} points, no extra charge.",
        "{name} found the open man. Wrong team, right result. Pick six, {p6pts} points in a single throw.",
        "{name} delivered a strike to the {opp} defense, which ran it back for six. {p6pts} points in one throw.",
        "Hand delivery, no signature required. {name} threw it to the {opp} and they took it the distance. {p6pts} points.",
        "{name} threw a touchdown pass. The {opp} would like to thank him for it. Pick six, {p6pts} points.",
        "The {opp} defense scored on a {name} pass, the most efficient way to rack up {p6pts} Sabotage points in one play.",
        "{name} made one throw this week that the {opp} will put on their season highlight tape. Pick six, {p6pts} points.",
        "Somewhere {a_opp} defensive back is still celebrating a gift from {name}. Pick six, {p6pts} points.",
        "{name} split the coverage, then the defender split the field. Pick six, {p6pts} points.",
        "One throw, one {opp} touchdown, {p6pts} points. {name} keeps the arithmetic simple.",
        "{name} spotted a {opp} defender wide open and found him. He scored. {p6pts} points.",
        "The fastest route to {p6pts} Sabotage points is a pick six. {name} took the express lane.",
        "{name} threw a ball the {opp} returned for a touchdown. That one play is worth {p6pts} points here.",
        "{name} threw it right to the {opp}, who went the other way for six. {p6pts} points.",
        "{name} played catch with the wrong jerseys. Pick six, {p6pts} points.",
        "Six points for the {opp}, {p6pts} for the ledger, and one long walk to the sideline for {name}.",
        "{name} threw a pick six, which in this league is a grand slam. {p6pts} points.",
    ],
    "pick_six_multi": [
        "{name} threw {n6} pick sixes to the {opp}. One is a mistake. {n6w} is a habit. {p6pts} points.",
        "The {opp} defense scored {n6} touchdowns on passes from {name}. {p6pts} points.",
        "{name} returned to the scene of the crime {n6} times. Pick sixes, {p6pts} points.",
        "Fool me once, shame on you. {name} threw {n6} pick sixes to the {opp} anyway. {p6pts} points.",
        "{name} offered the {opp} a volume discount on pick sixes. {n6} of them, {p6pts} points.",
        "The {opp} defense would like to name {name} an honorary member. {n6} pick sixes, {p6pts} points.",
        "{name} found the {opp} so open he went back for more. {n6} pick sixes, {p6pts} points.",
        "{name} threw {n6} passes that ended in the wrong end zone. {p6pts} points, a small fortune in this league.",
        "Lightning struck more than once, and {name} kept holding the umbrella. {n6} pick sixes, {p6pts} points.",
        "The {opp} defense scored like an offense this week, with plenty of help from {name}. {n6} pick sixes, {p6pts} points.",
        "{name} made the {opp} defense a scoring threat. {n6} pick sixes, {p6pts} points.",
        "{n6w} pick sixes from {name}. Somewhere {a_opp} defensive coordinator is asking for a raise. {p6pts} points.",
        "One pick six is a bad day. {name} threw {n6}. {p6pts} points.",
        "{name} kept serving the {opp} defense like it was a holiday dinner. {n6} pick sixes, {p6pts} points.",
        "The {opp} took passes from {name} the distance {n6} times. {p6pts} points.",
        "{name} turned the {opp} defense into his favorite receivers, {n6} times over. {p6pts} points.",
        "Every pick six is worth {p6one} points here. {name} threw {n6} of them. {p6pts} points.",
        "{name} threw {n6} pick sixes, the Sabotage version of a perfect game. {p6pts} points.",
    ],
    "fumbles": [
        "{name} handled the football like a bar of soap in a hot shower. {fum} fumbles, {lost} lost, {fpts} points from fumbles alone.",
        "{name} put the ball on the turf {fum} times. Gravity remains undefeated. {fpts} fumble points.",
        "{name} carried the ball like it owed him money and he wanted it gone. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} treated ball security as a suggestion. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} and the football had a falling out. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} held the ball like a waiter carrying six plates on one tray. {fum} fumbles, {lost} lost, {fpts} points.",
        "Coaches preach two hands on the ball. {name} tried zero, {fum} different times. {fpts} fumble points.",
        "{name} spent the game fumbling for answers and the football. {fum} fumbles, {lost} lost, {fpts} points.",
        "The ball came loose from {name} {fum} times, which is {fum} more than his coach wanted. {fpts} points.",
        "{name} brought butter to a game that called for glue. {fum} fumbles, {lost} lost, {fpts} points.",
        "Ball security drills exist because of games like this one from {name}. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} kept the turf crowded with footballs. {fum} fumbles, {fpts} points from fumbles alone.",
        "The {fum} fumbles from {name} gave the defense plenty to scramble for. {lost} lost, {fpts} points.",
        "{name} played hot potato with the football. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} kept a loose grip on the ball and a tight grip on this award. {fum} fumbles, {lost} lost, {fpts} points.",
        "Somebody get {name} some stickum. {fum} fumbles, {lost} lost, {fpts} points.",
        "{name} introduced the football to the turf {fum} times. {lost} lost, {fpts} points.",
        "Someone should check the football for grease after the day {name} had. {fum} fumbles, {lost} lost, {fpts} points.",
    ],
    "kicker": [
        "{name} lined up, swung, and gave the uprights a respectful amount of personal space. {kline}. {pts} points.",
        "{name} kicks the way a weather forecast predicts: confidently, and often wrong. {kline}. {pts} points.",
        "{name} was paid to split the uprights and chose diplomacy instead. {kline}. {pts} points.",
        "{name} aimed for the uprights and found everything else. {kline}. {pts} points.",
        "{name} had one job, and the job won. {kline}. {pts} points.",
        "The holder did his part. {name} took it from there. {kline}. {pts} points.",
        "{name} kicked like the goalposts had moved since warmups. {kline}. {pts} points.",
        "Points were available. {name} declined them. {kline}. {pts} points.",
        "{name} turned routine kicks into suspense, mostly the bad kind. {kline}. {pts} points.",
        "Kickers live one swing at a time. {name} had a rough day of swings. {kline}. {pts} points.",
        "{name} sent the special teams coach looking for antacids. {kline}. {pts} points.",
        "The uprights stood still. {name} still found a way around them. {kline}. {pts} points.",
        "{name} kept the scoreboard operator guessing. {kline}. {pts} points.",
        "The easy points are supposed to be easy. {name} disagreed. {kline}. {pts} points.",
        "{name} brought a strong leg and no sense of direction. {kline}. {pts} points.",
        "In a league that rewards misses, {name} was a franchise player this week. {kline}. {pts} points.",
        "{name} kicked like someone told him the uprights were a suggestion. {kline}. {pts} points.",
        "The ball went up, the ball came down, and the scoreboard did not move. Credit {name}. {kline}. {pts} points.",
    ],
    "defense": [
        "The {team} defense hosted the {opp} like an open house with free parking. {pa} points allowed, {pts} for the ledger.",
        "The {team} guarded their end zone like a revolving door at a department store sale. {pa} allowed to the {opp}. {pts} points.",
        "Somewhere {a_team} safety is still pointing at the receiver he was supposed to cover. The {opp} put up {pa}. {pts} points.",
        "The {team} defense rolled out the welcome mat and the {opp} wiped their feet on it. {pa} points allowed, {pts} points.",
        "The {team} defense let the {opp} put up {pa}. Tackling appeared optional. {pts} points.",
        "The {team} defense played like the scoreboard was somebody else's problem. {pa} allowed to the {opp}. {pts} points.",
        "If hospitality were a stat, the {team} defense would lead the league. The {opp} scored {pa}. {pts} points.",
        "The {opp} offense found the {team} defense the way a toddler finds a puddle: early and often. {pa} allowed, {pts} points.",
        "The {team} defense kept a polite distance from ball carriers. {pa} points to the {opp}. {pts} points.",
        "The {team} defense handed out points to the {opp} like free samples. {pa} allowed, {pts} for the ledger.",
        "Somebody check whether the {team} defense was told the game had started. The {opp} scored {pa}. {pts} points.",
        "The {opp} scored {pa} points and have {a_team} defense to thank for them. {pts} points.",
        "The {team} defense showed up dressed for the game and watched it like spectators. {pa} allowed to the {opp}. {pts} points.",
        "The {team} defense gave the {opp} plenty of personal space. {pa} points allowed, {pts} points.",
        "The {team} defense kept the {opp} offense comfortable all game. {pa} points allowed, {pts} points.",
        "The {opp} moved the ball on the {team} defense like it was a walkthrough. {pa} allowed, {pts} points.",
        "The {team} defense bent, then broke, then filled out the paperwork. {pa} points to the {opp}. {pts} points.",
        "The {team} defense rang up {pa} points for the {opp} and {pts} for this ledger. A team effort, in the wrong direction.",
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


NUM_WORD = {2: "Two", 3: "Three", 4: "Four", 5: "Five"}


def a_an(word: str) -> str:
    return ("an " if word[:1].upper() in "AEIOU" else "a ") + word


LABELS = {
    "top": "Saboteur of the week",
    "top_nonqb": "Best non-QB saboteur",
    "pick_six": "Pick six",
    "pick_six_multi": "Pick sixes",
    "fumbles": "Butterfingers award",
    "kicker": "Kicker of the week",
    "defense": "Defense of the week",
}


def _pick(kind: str, week: int) -> str:
    """The line for this award in this week: week 1 gets line 1, week 18 line 18."""
    opts = TEMPLATES[kind]
    return opts[(int(week) - 1) % len(opts)]


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
        n6 = int(r["n_pick_sixes"])
        if n6 >= 2:
            # Its own list: one throw lines read wrong for a quarterback who threw several.
            out.append(_story("pick_six_multi", r, key(r), name=r["player_display_name"], opp=nick(r["opponent_team"]),
                              a_opp=a_an(nick(r["opponent_team"])), n6=n6, n6w=NUM_WORD.get(n6, str(n6)),
                              p6one=r["p6_value"], p6pts=n6 * r["p6_value"]))
        else:
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
    week = int(key.split("-")[1])
    return {"kind": kind, "label": LABELS[kind], "who": who, "team": row.get("team"),
            "text": _pick(kind, week).format(**fields)}
