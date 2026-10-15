"""Hand-computed scoring examples. Each expected total is worked out in the comment above it."""
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import score  # noqa: E402

STAT_COLS = [
    "completions", "attempts", "sacks_suffered", "carries", "receptions",
    "sack_fumbles", "rushing_fumbles", "receiving_fumbles",
    "sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost",
    "fumbles_total", "fumbles_lost_total", "passing_interceptions",
    "fg_missed_0_19", "fg_missed_20_29", "fg_missed_30_39", "fg_missed_40_49",
    "fg_missed_50_59", "fg_missed_60_", "pat_missed",
]


def stat_row(pid, **vals):
    row = {"player_id": pid, "player_display_name": pid, "position": "QB", "season": 2026,
           "week": 1, "game_id": "G1", "team": "AAA", "opponent_team": "BBB"}
    row.update({c: 0 for c in STAT_COLS})
    row.update(vals)
    return row


PBP_SCHEMA = {
    "game_id": pl.Utf8, "play_id": pl.Float64, "posteam": pl.Utf8, "defteam": pl.Utf8,
    "td_team": pl.Utf8, "touchdown": pl.Float64, "return_touchdown": pl.Float64,
    "interception": pl.Float64, "passer_player_id": pl.Utf8, "kicker_player_id": pl.Utf8,
    "kick_distance": pl.Float64, "field_goal_result": pl.Utf8, "extra_point_result": pl.Utf8,
    "two_point_conv_result": pl.Utf8, "safety": pl.Float64, "defensive_two_point_conv": pl.Float64,
}


def pbp(rows):
    base = {k: None for k in PBP_SCHEMA}
    return pl.DataFrame([{**base, **r} for r in rows], schema=PBP_SCHEMA)


QB = stat_row("QB1", attempts=30, completions=20, sacks_suffered=3, carries=4,
              sack_fumbles=1, sack_fumbles_lost=1, rushing_fumbles=1,
              fumbles_total=3, fumbles_lost_total=2, passing_interceptions=2)
# One of the two interceptions was returned for a TD; then a PAT.
QB_PBP = pbp([
    {"game_id": "G1", "play_id": 1, "posteam": "AAA", "defteam": "BBB", "td_team": "BBB",
     "touchdown": 1, "return_touchdown": 1, "interception": 1, "passer_player_id": "QB1"},
    {"game_id": "G1", "play_id": 2, "posteam": "BBB", "defteam": "AAA", "extra_point_result": "good"},
])


def total(stats, p, **interp):
    out = score.score_players(pl.DataFrame(stats), p, score.load_config(**interp))
    return dict(zip(out["player_id"], out["sabotage_pts"]))


def test_qb_stacked_offense_fumbles():
    # incompletions 10*2=20, sacks 3*5=15, carries 4*1=4
    # fumbles (offense scope) 2*7=14, lost 1*10=10
    # ints 2*10=20, pick six 1*21=21  -> 20+15+4+14+10+20+21 = 104
    assert total([QB], QB_PBP, stack_fumble_lost=True, stack_pick_six=True, fumble_scope="offense")["QB1"] == 104


def test_qb_not_stacked():
    # fumbles: 1 not-lost *7=7, 1 lost *10=10 -> 17 (was 24)
    # ints: 1 non-pick-six *10=10, 1 pick six *21=21 -> 31 (was 41)
    # 20+15+4+17+31 = 87
    assert total([QB], QB_PBP, stack_fumble_lost=False, stack_pick_six=False, fumble_scope="offense")["QB1"] == 87


def test_qb_all_fumbles_scope():
    # fumbles_total 3*7=21, fumbles_lost_total 2*10=20 -> 41 instead of 24
    # 20+15+4+41+20+21 = 121
    assert total([QB], QB_PBP, stack_fumble_lost=True, stack_pick_six=True, fumble_scope="all")["QB1"] == 121


K = stat_row("K1", fg_missed_30_39=1, fg_missed_50_59=1, fg_missed_60_=1, pat_missed=1)
K_PBP = pbp([
    {"game_id": "G1", "play_id": 5, "kicker_player_id": "K1", "kick_distance": 47, "field_goal_result": "blocked"},
    {"game_id": "G1", "play_id": 6, "kicker_player_id": "K1", "extra_point_result": "blocked"},
])


def test_kicker_blocks_ignored():
    # 30-39 miss 16, 50-59 miss 12, 60+ miss 12, PAT miss 16 -> 56
    assert total([K], K_PBP, blocked_kicks_are_misses=False)["K1"] == 56


def test_kicker_blocks_count():
    # 56 + blocked 47-yarder (40-49) 14 + blocked PAT 16 -> 86
    assert total([K], K_PBP, blocked_kicks_are_misses=True)["K1"] == 86


@pytest.mark.parametrize("pa,bucket,pts", [
    (0, "0", 0), (1, "1-6", 7), (6, "1-6", 7), (7, "7-13", 14), (13, "7-13", 14),
    (14, "14-20", 21), (20, "14-20", 21), (21, "21-27", 28), (27, "21-27", 28),
    (28, "28-34", 35), (34, "28-34", 35), (35, "35+", 42), (60, "35+", 42),
])
def test_points_allowed_buckets(pa, bucket, pts):
    assert score.pa_points(pa, score.load_config()["defense"]["points_allowed"]) == (bucket, pts)


def test_defense_points_allowed_modes():
    sched = pl.DataFrame({"game_id": ["G1"], "season": [2026], "week": [1], "home_team": ["AAA"],
                          "away_team": ["BBB"], "home_score": [10], "away_score": [23]})
    # BBB scored 23, of which a pick six + PAT = 7 and a safety = 2 came without its offense.
    p = pbp([
        {"game_id": "G1", "play_id": 1, "posteam": "AAA", "defteam": "BBB", "td_team": "BBB",
         "touchdown": 1, "return_touchdown": 1, "interception": 1},
        {"game_id": "G1", "play_id": 2, "posteam": "BBB", "defteam": "AAA", "extra_point_result": "good"},
        {"game_id": "G1", "play_id": 3, "posteam": "AAA", "defteam": "BBB", "safety": 1},
    ])
    raw = score.score_defenses(sched, p, score.load_config(points_allowed="raw"))
    off = score.score_defenses(sched, p, score.load_config(points_allowed="offense_only"))
    aaa_raw = raw.filter(pl.col("team") == "AAA").row(0, named=True)
    aaa_off = off.filter(pl.col("team") == "AAA").row(0, named=True)
    # raw: 23 allowed -> 21-27 bucket -> 28. offense_only: 23-7-2 = 14 -> 14-20 bucket -> 21
    assert (aaa_raw["points_allowed"], aaa_raw["sabotage_pts"]) == (23, 28)
    assert (aaa_off["points_allowed"], aaa_off["sabotage_pts"]) == (14, 21)
    # BBB allowed 10 either way (AAA scored no non-offensive points) -> 14
    assert off.filter(pl.col("team") == "BBB")["sabotage_pts"][0] == 14
