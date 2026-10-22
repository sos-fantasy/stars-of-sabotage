"""Injury tags and depth charts, with hand-built examples."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import availability as A  # noqa: E402

INJ_COLS = {"gsis_id": pl.Utf8, "team": pl.Utf8, "week": pl.Int32, "report_status": pl.Utf8,
            "report_primary_injury": pl.Utf8, "report_secondary_injury": pl.Utf8,
            "practice_primary_injury": pl.Utf8, "practice_secondary_injury": pl.Utf8, "practice_status": pl.Utf8}


def inj(rows):
    return pl.DataFrame([{**{k: None for k in INJ_COLS}, **r} for r in rows], schema=INJ_COLS)


def roster(rows):
    return pl.DataFrame(rows, schema={"gsis_id": pl.Utf8, "team": pl.Utf8, "week": pl.Int32, "status": pl.Utf8,
                                      "status_description_abbr": pl.Utf8})


def test_tag_precedence_and_labels():
    i = inj([
        # a: Questionable this week, ankle and knee
        {"gsis_id": "a", "team": "CHI", "week": 7, "report_status": "Questionable",
         "report_primary_injury": "Ankle", "report_secondary_injury": "Knee"},
        # b: no game status yet, did not practice (hamstring)
        {"gsis_id": "b", "team": "CHI", "week": 7, "practice_status": "Did Not Participate In Practice",
         "practice_primary_injury": "Hamstring"},
        # c: full practice only -> no tag
        {"gsis_id": "c", "team": "CHI", "week": 7, "practice_status": "Full Participation in Practice",
         "practice_primary_injury": "Toe"},
        # d: GB has no week 7 report yet -> last week's Out carries over, marked week 6
        {"gsis_id": "d", "team": "GB", "week": 6, "report_status": "Out", "report_primary_injury": "Calf"},
        # e: hurt in week 3, now on IR (roster R01) -> IR with last listed body part
        {"gsis_id": "e", "team": "GB", "week": 3, "report_status": "Out", "report_primary_injury": "Knee"},
        # f: rest day note only, then IR -> no body part
        {"gsis_id": "f", "team": "GB", "week": 2, "practice_status": "Did Not Participate In Practice",
         "practice_primary_injury": "Not injury related - resting player"},
    ])
    r = roster([{"gsis_id": "e", "team": "GB", "week": 7, "status": "RES", "status_description_abbr": "R01"},
                {"gsis_id": "f", "team": "GB", "week": 7, "status": "RES", "status_description_abbr": "R01"},
                {"gsis_id": "g", "team": "GB", "week": 7, "status": "RES", "status_description_abbr": "R04"},
                {"gsis_id": "h", "team": "GB", "week": 7, "status": "EXE", "status_description_abbr": "E02"},
                {"gsis_id": "k", "team": "GB", "week": 7, "status": "ACT", "status_description_abbr": "A01"}])
    t = A.injury_tags(i, r, 7)
    assert t["a"]["status"] == "Questionable" and t["a"]["injury"] == "Ankle, Knee" and t["a"]["level"] == "q"
    assert t["b"]["status"] == "Did not practice" and t["b"]["injury"] == "Hamstring" and t["b"]["level"] == "p"
    assert "c" not in t and "k" not in t
    assert t["d"] == {"status": "Out", "injury": "Calf", "week": 6, "team": "GB", "level": "out"}
    assert t["e"]["status"] == "IR" and t["e"]["injury"] == "Knee" and t["e"]["week"] is None
    assert t["f"]["status"] == "IR" and t["f"]["injury"] is None
    assert t["g"]["status"] == "PUP" and t["h"]["status"] == "Exempt list"
    # Unavailable this week: IR, PUP, exempt. Not last week's Out (d), not practice (b).
    assert A.unavailable_ids(t, 7) == {"e", "f", "g", "h"}


def test_this_weeks_designation_beats_roster_designated_to_return():
    i = inj([{"gsis_id": "a", "team": "ARI", "week": 7, "report_status": "Questionable", "report_primary_injury": "Knee"}])
    r = roster([{"gsis_id": "a", "team": "ARI", "week": 7, "status": "RES", "status_description_abbr": "R48"}])
    assert A.injury_tags(i, r, 7)["a"]["status"] == "Questionable"
    i2 = inj([{"gsis_id": "a", "team": "ARI", "week": 7, "practice_status": "Limited Participation in Practice"}])
    assert A.injury_tags(i2, r, 7)["a"]["status"] == "IR, designated to return"


def dc_rows(dt, team, rows):
    return [{"dt": dt, "team": team, "pos_abb": pos, "pos_rank": rank, "gsis_id": gid, "player_name": name}
            for pos, rank, gid, name in rows]


def test_next_man_up_and_week_over_week_moves():
    # Week earlier: WR1 w1, WR2 w2, WR3 w3, WR4 w4 (plus two deep backups). Now: w2 moved to WR1, w1 to WR2, w5 new at 5.
    # w2 is Out this week, so: w1 starts WR1, w3 WR2, w4 WR3 (in for w2), w5 backup.
    old = dc_rows("2026-10-12T12:00:00Z", "CHI", [("WR", 1, "w1", "One"), ("WR", 2, "w2", "Two"),
                                                  ("WR", 3, "w3", "Three"), ("WR", 4, "w4", "Four"),
                                                  ("WR", 5, "w0", "Zero"), ("WR", 6, "w6", "Six")])
    new = dc_rows("2026-10-20T12:00:00Z", "CHI", [("WR", 1, "w2", "Two"), ("WR", 2, "w1", "One"), ("WR", 3, "w3", "Three"),
                                                  ("WR", 4, "w4", "Four"), ("WR", 5, "w5", "Five"),
                                                  # duplicate listing in another formation keeps his best rank
                                                  ("WR", 9, "w1", "One")])
    dc = pl.DataFrame(old + new)
    tags = {"w2": {"status": "Out", "injury": "Hamstring", "week": 7, "team": "CHI", "level": "out"}}
    teams = A.depth_charts(dc, tags, {"w2"}, datetime(2026, 10, 21, tzinfo=timezone.utc))
    wr = teams["CHI"]["WR"]
    got = [(e["name"], e["rank"], e["prev_rank"], e.get("slot"), e.get("in_for"), e["new"]) for e in wr]
    assert got == [("Two", 1, 2, None, None, False), ("One", 2, 1, "WR1", None, False),
                   ("Three", 3, 3, "WR2", None, False), ("Four", 4, 4, "WR3", "Two", False),
                   ("Five", 5, None, None, None, True)]
    assert wr[0]["tag"]["status"] == "Out" and wr[0]["start"] is False
    st = A.starters(teams)
    assert sorted(zip(st["slot"], st["player_id"])) == [("WR1", "w1"), ("WR2", "w3"), ("WR3", "w4")]
    assert A.slots(teams)["w4"] == {"team": "CHI", "pos": "WR", "rank": 4, "slot": "WR3", "in_for": "Two"}


def test_partial_snapshot_is_skipped_and_kickers_listed_as_k():
    # Full snapshots have 4 rows; the latest has 2 (receivers and kicker missing), so the
    # chart comes from the earlier full one. Kicker filed as "K" still counts.
    full = dc_rows("2026-10-20T12:00:00Z", "NE", [("QB", 1, "q1", "Q"), ("WR", 1, "w1", "W"), ("TE", 1, "t1", "T"),
                                                  ("K", 1, "k1", "Kick")])
    part = dc_rows("2026-10-21T12:00:00Z", "NE", [("QB", 1, "q1", "Q"), ("TE", 1, "t1", "T")])
    older = dc_rows("2026-10-19T12:00:00Z", "NE", [("QB", 1, "q1", "Q"), ("WR", 1, "w9", "Old"), ("TE", 1, "t1", "T"),
                                                   ("K", 1, "k1", "Kick")])
    dc = pl.DataFrame(older + full + part)
    assert A.complete_snapshots(dc)["dt"].unique().sort().to_list() == ["2026-10-19T12:00:00Z", "2026-10-20T12:00:00Z"]
    teams = A.depth_charts(dc, {}, set(), datetime(2026, 10, 21, 13, tzinfo=timezone.utc))
    assert [e["name"] for e in teams["NE"]["WR"]] == ["W"]
    assert teams["NE"]["K"][0]["slot"] == "K"


def test_usage_by_week_and_last_game():
    # CHI played weeks 1, 2, 4 (bye week 3). x: CHI weeks 1 and 2, traded to GB for week 3.
    # y: CHI week 2 only. z: CHI week 4 on the field (5% of snaps) with no stat line.
    scores = pl.DataFrame({"player_id": ["x", "x", "x", "y", "w"], "season": [2026] * 5,
                           "team": ["CHI", "CHI", "GB", "CHI", "CHI"], "week": [1, 2, 3, 2, 4],
                           "n_carries": [10, 12, 3, 0, 0], "n_targets": [2, 4, 1, 6, 3],
                           "sabotage_pts": [14, 20, 5, 12, 2]})
    snaps = pl.DataFrame({"player_id": ["x", "z"], "season": [2026, 2026], "week": [1, 4],
                          "offense_pct": [0.62, 0.05], "team": ["CHI", "CHI"]})
    depth = {"teams": {"GB": {"RB": [{"id": "x", "name": "X", "rank": 1}]},
                       "CHI": {"WR": [{"id": "y", "name": "Y", "rank": 1}, {"id": None, "name": "No Id", "rank": 2}],
                               "QB": [{"id": "z", "name": "Z", "rank": 2}]}}}
    A.add_usage(depth, scores, snaps, 2026)
    chi, gb = depth["teams"]["CHI"], depth["teams"]["GB"]
    assert chi["games"] == [1, 2, 4] and gb["games"] == [3]
    x = gb["RB"][0]
    assert x["last"] == {"week": 3, "car": 3, "tgt": 1, "snap": None, "pts": 5, "team": "GB"}
    # Only his GB games count for GB.
    assert gb["usage"] == {"x": [[3, 3, 1, None, 5, 1]]}
    # y: zeros (played 0) for CHI weeks 1 and 4; nothing for the bye week 3.
    assert chi["usage"]["y"] == [[1, 0, 0, 0, 0, 0], [2, 0, 6, None, 12, 1], [4, 0, 0, 0, 0, 0]]
    # z: snaps but no stat line in week 4 still counts as a game: 5% of snaps, 0 points.
    assert chi["usage"]["z"] == [[1, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0], [4, 0, 0, 5, 0, 1]]
    assert chi["QB"][0]["last"]["snap"] == 5
    assert "last" not in chi["WR"][1]
    assert depth["weeks"] == [1, 2, 3, 4]
