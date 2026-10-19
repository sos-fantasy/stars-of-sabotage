"""Projection building blocks, with hand-computed examples."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import project as P  # noqa: E402
import projections as PR  # noqa: E402
import score as S  # noqa: E402
import weather as W  # noqa: E402

TABLE = S.load_config()["defense"]["points_allowed"]


def test_implied_points_from_spread_and_total():
    # Home favored by 3 (nflverse spread_line = home margin), total 47:
    # home 47/2 + 3/2 = 25.0, away 47/2 - 3/2 = 22.0.
    s = pl.DataFrame({"season": [2026], "game_type": ["REG"], "week": [7], "home_team": ["CHI"], "away_team": ["NE"],
                      "spread_line": [3.0], "total_line": [47.0], "roof": ["outdoors"], "wind": [12]})
    c = {r["team"]: r for r in P.game_context(s).iter_rows(named=True)}
    assert c["CHI"]["implied"] == 25.0 and c["NE"]["implied"] == 22.0
    assert c["CHI"]["team_spread"] == 3.0 and c["NE"]["team_spread"] == -3.0
    assert c["CHI"]["home"] == 1 and c["NE"]["home"] == 0 and c["NE"]["wind_mph"] == 12.0


def test_era_codes_map_to_today():
    s = pl.DataFrame({"season": [2015], "game_type": ["REG"], "week": [1], "home_team": ["SD"], "away_team": ["OAK"],
                      "spread_line": [1.0], "total_line": [44.0], "roof": ["dome"], "wind": [None]})
    assert sorted(P.game_context(s)["team"].to_list()) == ["LAC", "LV"]


def test_bucket_points_match_scoring_table():
    # 0 -> 0 (shutout), 6 -> 7, 13 -> 14, 20 -> 21, 27 -> 28, 34 -> 35, 35 -> 42
    got = PR.bucket_points(np.array([0, 6, 13, 20, 27, 34, 35]), TABLE).tolist()
    assert got == [0, 7, 14, 21, 28, 35, 42]


def test_defense_expected_points_hand_example():
    # Opponent implied 20 every game (total 40, even spread). Points allowed is 20 plus
    # residuals of
    # -4 and +4 in equal number. For a game with opponent implied 20: outcomes 16 and 24,
    # bucket points 21 and 28, expected 24.5.
    rows = []
    for i in range(40):
        rows.append({"team": "AAA", "opponent": "BBB", "week": (i % 17) + 1, "season": 2020 + i // 17,
                     "points_allowed": 20 + (4 if i % 2 else -4), "sabotage_pts": 0})
    hist = pl.DataFrame(rows)
    sched = pl.DataFrame([{"season": r["season"], "game_type": "REG", "week": r["week"], "home_team": "AAA",
                           "away_team": "BBB", "spread_line": 0.0, "total_line": 40.0, "roof": "dome", "wind": None}
                          for r in rows]).unique(["season", "week"])
    games = pl.DataFrame({"team": ["AAA"], "opponent_team": ["BBB"], "opp_implied": [20.0], "game_id": ["g"]})
    out = PR.defense_projections(hist, sched, games, TABLE, 202301)
    assert abs(out["proj"][0] - 24.5) < 0.6


def test_ranges_follow_similar_projections():
    rng = np.random.default_rng(0)
    pred = np.repeat(np.arange(1, 11, dtype=float), 100)
    act = pred + rng.integers(-2, 3, pred.size)
    lo, hi = PR._ranges(pred, act, np.array([5.0]))
    assert lo[0] <= 5 <= hi[0] and hi[0] - lo[0] <= 4


def test_target_week_moves_on_after_sunday():
    s = pl.DataFrame({"game_type": ["REG"] * 4, "week": [6, 6, 7, 7],
                      "gameday": ["2026-10-18", "2026-10-19", "2026-10-22", "2026-10-25"],
                      "gametime": ["13:00", "20:15", "20:15", "13:00"]})
    # Saturday with a full Sunday slate ahead: preview week 6.
    full = pl.concat([s, pl.DataFrame({"game_type": ["REG"] * 3, "week": [6] * 3,
                                       "gameday": ["2026-10-18"] * 3, "gametime": ["16:05"] * 3})])
    wk, g = PR.target_week(full, datetime(2026, 10, 17, 12, tzinfo=timezone.utc))
    assert wk == 6 and g.height == 5
    # Monday morning: only Monday night is left in week 6, so preview week 7.
    wk, g = PR.target_week(s, datetime(2026, 10, 19, 12, tzinfo=timezone.utc))
    assert wk == 7 and g.height == 2


def test_kickoff_time_is_eastern():
    assert W.kickoff_utc("2026-10-25", "13:00").hour == 17     # EDT, UTC-4
    assert W.kickoff_utc("2026-12-20", "13:00").hour == 18     # EST, UTC-5


def test_stadium_table_loads_and_is_plausible():
    by_name, by_id = W.load_stadiums()
    assert len(by_id) >= 32
    for v in by_name.values():
        assert -90 <= v["lat"] <= 90 and -180 <= v["lon"] <= 180
    assert by_name["Lambeau Field"]["city"] == "Green Bay"
