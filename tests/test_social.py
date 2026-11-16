"""Social cards: math check, tie cut, stat lines, schedule. Hand-computed examples."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "social"))
import post_times as schedule  # noqa: E402
import top7  # noqa: E402

CFG = top7.scoring()
ET = ZoneInfo("America/New_York")


def row(**kw):
    base = {f: 0 for f in [
        "n_incomplete", "n_sacks", "n_carries", "n_receptions", "n_targets", "n_fumbles", "n_fumbles_lost",
        "n_ints", "n_pick_sixes", "n_fg_missed", "n_pat_missed", "pts_incomplete", "pts_sacks", "pts_carries",
        "pts_receptions", "pts_fumble", "pts_fumble_lost", "pts_int", "pts_pick_six", "pts_kicking"]}
    base.update({"player_display_name": "Test Player", "position": "QB", "team": "WAS", "week": 10})
    base.update(kw)
    return base


def test_daniels_week10_adds_up():
    # Hand check: 10 inc x2 = 20, 2 INT x10 = 20, 1 sack x5 = 5, 11 carries x1 = 11. Total 56.
    r = row(n_incomplete=10, pts_incomplete=20, n_ints=2, pts_int=20, n_sacks=1, pts_sacks=5,
            n_carries=11, pts_carries=11, sabotage_pts=56)
    item = top7.player_item(r, CFG)
    assert item["pts"] == 56
    assert top7.stat_line(item) == "10 INC X2 · 2 INT X10 · 1 SACK X5 · 11 CARRIES X1"


def test_lost_fumble_and_pick_six_stack():
    # 1 fumble x7 + lost +10 = 17; 1 INT x10 + pick six +21 = 31. Total 48.
    r = row(n_fumbles=1, pts_fumble=7, n_fumbles_lost=1, pts_fumble_lost=10,
            n_ints=1, pts_int=10, n_pick_sixes=1, pts_pick_six=21, sabotage_pts=48)
    item = top7.player_item(r, CFG)
    assert top7.stat_line(item) == "1 INT X10 · 1 PICK SIX +21 · 1 FUMBLE X7 · 1 LOST +10"


def test_total_mismatch_refuses_the_card():
    # Milton's site card listed parts worth 83 against 93 points. A card like that must not build.
    r = row(n_incomplete=16, pts_incomplete=32, n_sacks=7, pts_sacks=35, n_fumbles=1, pts_fumble=7,
            n_carries=9, pts_carries=9, sabotage_pts=93)
    with pytest.raises(top7.CardError):
        top7.player_item(r, CFG)


def test_part_points_must_match_rule():
    r = row(n_incomplete=3, pts_incomplete=5, sabotage_pts=5)  # 3 x 2 is 6, not 5
    with pytest.raises(top7.CardError):
        top7.player_item(r, CFG)


def test_points_allowed_buckets():
    assert top7.bucket_points(0, CFG) == 0
    assert top7.bucket_points(24, CFG) == 28
    assert top7.bucket_points(35, CFG) == 42
    d = {"team": "NYG", "points_allowed": 24, "pa_bucket": "21-27", "sabotage_pts": 21}
    with pytest.raises(top7.CardError):
        top7.defense_item(d, CFG)


def _items(scores):
    return [{"name": f"P{i}", "pts": p} for i, p in enumerate(scores)]


def test_cut_never_ends_on_a_split_tie():
    # 7th and 8th both 20: the list shrinks to the top 6.
    out = top7.cut_top(_items([60, 50, 40, 35, 30, 25, 20, 20, 10]))
    assert [x["pts"] for x in out] == [60, 50, 40, 35, 30, 25]
    # Ties inside the list share a rank.
    out = top7.cut_top(_items([56, 47, 28, 28, 27, 25, 24, 16]))
    assert [x["rank"] for x in out] == ["1", "2", "T-3", "T-3", "5", "6", "7"]


def test_cut_floor_keeps_a_big_tie():
    # Shrinking would leave 3 rows (below the floor of 5), so the tie is kept, capped at 9 rows.
    out = top7.cut_top(_items([90, 80, 70, 20, 20, 20, 20, 20, 5]))
    assert len(out) == 8 and out[-1]["rank"] == "T-4"


def g(gid, day, t, week=10, home="NYG", away="WAS"):
    return {"game_id": gid, "gameday": day, "gametime": t, "week": week, "home_team": home, "away_team": away}


def test_schedule_slots():
    games = [
        g("thu", "2026-11-12", "20:15"),
        g("sun1", "2026-11-15", "13:00", home="DAL", away="PHI"),
        g("sun2", "2026-11-15", "16:25", home="SF", away="LA"),
        g("snf", "2026-11-15", "20:20", home="KC", away="BUF"),
        g("mnf", "2026-11-16", "20:15", home="GB", away="CHI"),
    ]
    by = {s["id"]: s["due"] for s in schedule.slots(games, 2026)}
    assert by["game-thu"] == datetime(2026, 11, 13, 9, tzinfo=ET)
    assert by["game-snf"] == datetime(2026, 11, 16, 13, tzinfo=ET)
    assert by["game-mnf"] == datetime(2026, 11, 17, 9, tzinfo=ET)
    assert by["wreckage-2026-10"] == datetime(2026, 11, 16, 9, tzinfo=ET)
    assert "game-sun1" not in by and "game-sun2" not in by


def test_thanksgiving_games_spaced_an_hour_apart():
    games = [g("t1", "2026-11-26", "12:30", 12), g("t2", "2026-11-26", "16:30", 12), g("t3", "2026-11-26", "20:20", 12)]
    hours = sorted(s["due"].hour for s in schedule.slots(games, 2026))
    assert hours == [9, 10, 11]


def test_due_window_and_done():
    s = [{"id": "a", "due": datetime(2026, 11, 13, 9, tzinfo=ET)}]
    assert schedule.due(s, datetime(2026, 11, 13, 9, 5, tzinfo=ET), set()) == s
    assert schedule.due(s, datetime(2026, 11, 13, 8, 55, tzinfo=ET), set()) == []
    assert schedule.due(s, datetime(2026, 11, 13, 21, 5, tzinfo=ET), set()) == []
    assert schedule.due(s, datetime(2026, 11, 13, 9, 5, tzinfo=ET), {"a"}) == []


def test_captions_have_no_link_text_rules():
    card = {"type": "game", "rows": [{"rank": "1", "name": "A", "team": "WAS", "pts": 9}] * 7,
            "matchup": "Commanders 24, Giants 21", "week": 10,
            "status": "provisional", "blurb": "Line."}
    caps = top7.captions(card)
    assert "link in bio" in caps["instagram"] and "https://" not in caps["instagram"]
    assert "https://starsofsabotage.com" in caps["facebook"]
    assert "—" not in caps["instagram"] + caps["facebook"]  # house style: no em dashes


def test_pinterest_caption_fits_limits_and_names_every_row():
    import json
    import pinterest
    rows = [{"rank": "1", "name": "Jayden Daniels", "team": "WAS", "pts": 56},
            {"rank": "2", "name": "Jaxson Dart", "team": "NYG", "pts": 47}]
    card = {"type": "game", "rows": rows, "matchup": "Commanders 24, Giants 21", "week": 10,
            "status": "provisional", "blurb": "Line."}
    pin = json.loads(top7.captions(card)["pinterest"])
    assert pin["title"] == "Top 2 fantasy football saboteurs from Commanders 24, Giants 21 (week 10)"
    assert ":" not in pin["title"]  # house style: no colon titles
    assert "1. Jayden Daniels WAS 56; 2. Jaxson Dart NYG 47" in pin["alt_text"]
    assert pin["link"] == "https://starsofsabotage.com/"
    out = pinterest.pin_fields(pin | {"description": "x" * 600})
    assert len(out["description"]) == 500 and len(out["title"]) <= 100


def test_pinterest_refuses_empty_fields():
    import pinterest
    with pytest.raises(SystemExit):
        pinterest.pin_fields({"title": " ", "description": "d", "alt_text": "a"})
