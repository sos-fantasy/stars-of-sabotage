"""Hand-computed scoring examples. Each expected total is worked out in the comment above it."""
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import score  # noqa: E402

STAT_COLS = [
    "completions", "attempts", "sacks_suffered", "carries", "receptions", "passing_interceptions",
    "fg_missed_0_19", "fg_missed_20_29", "fg_missed_30_39", "fg_missed_40_49",
    "fg_missed_50_59", "fg_missed_60_", "pat_missed",
]


def stat_row(pid, position="QB", **vals):
    row = {"player_id": pid, "player_display_name": pid, "position": position, "season": 2026,
           "week": 1, "game_id": "G1", "team": "AAA", "opponent_team": "BBB"}
    row.update({c: 0 for c in STAT_COLS})
    row.update(vals)
    return row


PBP_SCHEMA = {
    "game_id": pl.Utf8, "play_id": pl.Float64, "play_type": pl.Utf8, "posteam": pl.Utf8,
    "defteam": pl.Utf8, "td_team": pl.Utf8, "touchdown": pl.Float64, "return_touchdown": pl.Float64,
    "interception": pl.Float64, "passer_player_id": pl.Utf8, "kicker_player_id": pl.Utf8,
    "kick_distance": pl.Float64, "field_goal_result": pl.Utf8, "extra_point_result": pl.Utf8,
    "two_point_conv_result": pl.Utf8, "safety": pl.Float64, "defensive_two_point_conv": pl.Float64,
    "fumbled_1_player_id": pl.Utf8, "fumbled_1_team": pl.Utf8,
    "fumbled_2_player_id": pl.Utf8, "fumbled_2_team": pl.Utf8, "fumble_lost": pl.Float64,
}


def pbp(rows):
    base = {k: None for k in PBP_SCHEMA}
    return pl.DataFrame([{**base, **r} for r in rows], schema=PBP_SCHEMA)


def fumble_play(pid, play_type="run", lost=0, team="AAA", posteam="AAA", play_id=10):
    return {"game_id": "G1", "play_id": play_id, "play_type": play_type, "posteam": posteam,
            "fumbled_1_player_id": pid, "fumbled_1_team": team, "fumble_lost": lost}


QB = stat_row("QB1", attempts=30, completions=20, sacks_suffered=3, carries=4, passing_interceptions=2)
QB_PBP = pbp([
    # One of the two interceptions was returned for a TD; then a PAT.
    {"game_id": "G1", "play_id": 1, "play_type": "pass", "posteam": "AAA", "defteam": "BBB",
     "td_team": "BBB", "touchdown": 1, "return_touchdown": 1, "interception": 1, "passer_player_id": "QB1"},
    {"game_id": "G1", "play_id": 2, "play_type": "extra_point", "posteam": "BBB", "defteam": "AAA",
     "extra_point_result": "good"},
    fumble_play("QB1", "pass", lost=1, play_id=3),   # strip sack, lost
    fumble_play("QB1", "run", lost=0, play_id=4),    # aborted snap, recovered
])


def total(stats, p, **interp):
    out = score.score_players(pl.DataFrame(stats), p, score.load_config(**interp))
    return dict(zip(out["player_id"], out["sabotage_pts"]))


def test_qb_league_rules():
    # incompletions 10*2=20, sacks 3*5=15, carries 4*1=4
    # fumbles 2*7=14 (includes the aborted snap), lost 1*10=10
    # interceptions 2*10=20, pick six 1*21=21
    # 20+15+4+14+10+20+21 = 104
    assert total([QB], QB_PBP)["QB1"] == 104


def test_qb_not_stacked():
    # fumbles: 1 not-lost *7=7, 1 lost *10=10 -> 17 (was 24)
    # interceptions: 1 plain *10=10, 1 pick six *21=21 -> 31 (was 41)
    # 20+15+4+17+31 = 87
    assert total([QB], QB_PBP, stack_fumble_lost=False, stack_pick_six=False)["QB1"] == 87


RET = stat_row("WR1", position="WR", receptions=3)
RET_PBP = pbp([
    fumble_play("WR1", "punt", lost=1, team="AAA", posteam="BBB", play_id=1),   # muffed punt return, lost
    fumble_play("WR1", "pass", lost=0, play_id=2),                               # fumble after catch, recovered
])


def test_returner_scrimmage_only():
    # receptions 3*2=6, scrimmage fumble 1*7=7 -> 13
    assert total([RET], RET_PBP, fumble_scope="scrimmage")["WR1"] == 13


def test_returner_with_returns():
    # 13 + return fumble 7 + lost 10 -> 30. League default since the owner's Yahoo check.
    assert total([RET], RET_PBP, fumble_scope="scrimmage_and_returns")["WR1"] == 30
    assert total([RET], RET_PBP)["WR1"] == 30


def test_center_snap_fumble_not_scored():
    # Centers are not offensive scoring positions under the league rules -> 0
    c = stat_row("C1", position="C")
    assert total([c], pbp([fumble_play("C1", "run", lost=1)]))["C1"] == 0


def test_defensive_team_fumble_not_scrimmage():
    # Fumbler's team is not the offense on a scrimmage play (a defender fumbling an INT return) -> 0
    lb = stat_row("RB9", position="RB")
    assert total([lb], pbp([fumble_play("RB9", "pass", lost=1, team="BBB", posteam="AAA")]))["RB9"] == 0


def test_two_fumbles_one_play_lost_to_last():
    # QB fumbles, RB picks it up and fumbles, defense recovers.
    # QB: 1*7 = 7. RB: 1*7 + lost 10 = 17
    p = pbp([{"game_id": "G1", "play_id": 1, "play_type": "run", "posteam": "AAA",
              "fumbled_1_player_id": "QB1", "fumbled_1_team": "AAA",
              "fumbled_2_player_id": "RB1", "fumbled_2_team": "AAA", "fumble_lost": 1}])
    out = total([stat_row("QB1"), stat_row("RB1", position="RB")], p)
    assert (out["QB1"], out["RB1"]) == (7, 17)


def test_lost_fumble_not_moved_to_defender():
    # Real case, 2026 wk 3 HOU at IND: Jones strip-sacked, HOU defender recovers and fumbles.
    # Jones: 1*7 + lost 10 = 17. The defender is not an offensive player and scores 0.
    p = pbp([{"game_id": "G1", "play_id": 1, "play_type": "pass", "posteam": "AAA",
              "fumbled_1_player_id": "QB1", "fumbled_1_team": "AAA",
              "fumbled_2_player_id": "DE1", "fumbled_2_team": "BBB", "fumble_lost": 1}])
    out = total([stat_row("QB1"), stat_row("DE1", position="DE")], p)
    assert (out["QB1"], out["DE1"]) == (17, 0)


K = stat_row("K1", position="K", fg_missed_30_39=1, fg_missed_50_59=1, fg_missed_60_=1, pat_missed=1)
K_PBP = pbp([
    {"game_id": "G1", "play_id": 5, "play_type": "field_goal", "kicker_player_id": "K1",
     "kick_distance": 47, "field_goal_result": "blocked"},
    {"game_id": "G1", "play_id": 6, "play_type": "extra_point", "kicker_player_id": "K1",
     "extra_point_result": "blocked"},
])


def test_kicker_league_rules_blocks_count():
    # 30-39 miss 16, 50-59 miss 12, 60+ miss 12, PAT miss 16 = 56
    # blocked 47-yarder (40-49) 14, blocked PAT 16 -> 56+14+16 = 86
    assert total([K], K_PBP)["K1"] == 86


def test_kicker_blocks_ignored():
    assert total([K], K_PBP, blocked_kicks_are_misses=False)["K1"] == 56


@pytest.mark.parametrize("d,bucket", [(19, "0-19"), (20, "20-29"), (39, "30-39"), (49, "40-49"), (50, "50+"), (66, "50+")])
def test_fg_bucket_edges(d, bucket):
    assert score.fg_bucket(d) == bucket


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
    # raw: 23 allowed -> 21-27 bucket -> 28. offense_only: 23-7-2 = 14 -> 14-20 -> 21
    assert (aaa_raw["points_allowed"], aaa_raw["sabotage_pts"]) == (23, 28)
    assert (aaa_off["points_allowed"], aaa_off["sabotage_pts"]) == (14, 21)
    # BBB allowed 10 -> 14
    assert raw.filter(pl.col("team") == "BBB")["sabotage_pts"][0] == 14


def test_defense_yahoo_points_allowed():
    # BBB scores 30: a pick six (6) + PAT (1), a safety (2), a punt return TD (6) + PAT (1),
    # and 14 from offense. Yahoo removes the pick six TD and the safety only:
    # 30 - 6 - 2 = 22 -> 21-27 bucket -> 28. Raw: 30 -> 28-34 -> 35.
    sched = pl.DataFrame({"game_id": ["G1"], "season": [2026], "week": [1], "home_team": ["AAA"],
                          "away_team": ["BBB"], "home_score": [0], "away_score": [30]})
    p = pbp([
        {"game_id": "G1", "play_id": 1, "play_type": "pass", "posteam": "AAA", "defteam": "BBB",
         "td_team": "BBB", "touchdown": 1, "return_touchdown": 1, "interception": 1},
        {"game_id": "G1", "play_id": 2, "play_type": "extra_point", "posteam": "BBB", "defteam": "AAA",
         "extra_point_result": "good"},
        {"game_id": "G1", "play_id": 3, "play_type": "run", "posteam": "AAA", "defteam": "BBB", "safety": 1},
        {"game_id": "G1", "play_id": 4, "play_type": "punt", "posteam": "AAA", "defteam": "BBB",
         "td_team": "BBB", "touchdown": 1, "return_touchdown": 1},
        {"game_id": "G1", "play_id": 5, "play_type": "extra_point", "posteam": "BBB", "defteam": "AAA",
         "extra_point_result": "good"},
    ])
    y = score.score_defenses(sched, p, score.load_config())  # league default since Oct 15, 2026
    assert score.load_config()["interpretation"]["points_allowed"] == "yahoo"
    r = score.score_defenses(sched, p, score.load_config(points_allowed="raw"))
    aaa_y = y.filter(pl.col("team") == "AAA").row(0, named=True)
    aaa_r = r.filter(pl.col("team") == "AAA").row(0, named=True)
    assert (aaa_y["points_allowed"], aaa_y["sabotage_pts"]) == (22, 28)
    assert (aaa_r["points_allowed"], aaa_r["sabotage_pts"]) == (30, 35)
    # AAA scored 0 -> BBB defense gets 0 (owner ruling: a shutout is not sabotage)
    assert y.filter(pl.col("team") == "BBB").row(0, named=True)["sabotage_pts"] == 0
