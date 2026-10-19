"""Tests for week status, run scheduling, and highlight story text."""
import re
import string
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import schedule  # noqa: E402
import stories  # noqa: E402

ET = schedule.ET


def test_final_at_is_thursday_after_monday_game():
    # Week 5, 2026: last game Monday Oct 12 -> final Thursday Oct 15, 10 AM ET
    assert schedule.final_at(date(2026, 10, 12)) == datetime(2026, 10, 15, 10, tzinfo=ET)


def test_final_at_when_last_game_is_thursday():
    # A Thursday last game rolls to the next Thursday, never the same day
    assert schedule.final_at(date(2026, 10, 15)) == datetime(2026, 10, 22, 10, tzinfo=ET)


@pytest.mark.parametrize("now,done,expected", [
    (datetime(2026, 10, 14, 12, tzinfo=ET), 15, "provisional"),
    (datetime(2026, 10, 15, 9, 59, tzinfo=ET), 15, "provisional"),
    (datetime(2026, 10, 15, 10, tzinfo=ET), 15, "final"),
    (datetime(2026, 10, 11, 20, tzinfo=ET), 9, "in_progress"),
    (datetime(2026, 10, 1, 12, tzinfo=ET), 0, "upcoming"),
])
def test_week_status(now, done, expected):
    assert schedule.week_status(now, 15, done, date(2026, 10, 12)) == expected


def test_is_due():
    sunday = date(2026, 10, 18)
    assert schedule.is_due(datetime(2026, 10, 18, 19, tzinfo=ET), {sunday})[0]
    assert schedule.is_due(datetime(2026, 10, 19, 1, tzinfo=ET), {sunday})[0]       # overnight after games
    assert schedule.is_due(datetime(2026, 10, 21, 22, tzinfo=ET), set())[0]         # Wednesday corrections
    assert schedule.is_due(datetime(2026, 10, 20, 6, tzinfo=ET), set())[0]          # daily
    assert not schedule.is_due(datetime(2026, 10, 20, 14, tzinfo=ET), {sunday})[0]  # Tuesday afternoon


FIELDS = {"name": "A. Player", "opp": "Broncos", "a_opp": "a Broncos", "line": "3 sacks", "pts": 40,
          "p6pts": 31, "fum": 2, "lost": 1, "fpts": 24, "kline": "Missed from 47", "team": "Eagles",
          "a_team": "an Eagles", "pa": 30, "n6": 2, "n6w": "Two", "p6one": 31}


@pytest.mark.parametrize("kind", list(stories.TEMPLATES))
def test_templates_render_and_follow_house_style(kind):
    for t in stories.TEMPLATES[kind]:
        keys = {f for _, f, _, _ in string.Formatter().parse(t) if f}
        assert keys <= set(FIELDS), (kind, keys - set(FIELDS))
        out = t.format(**FIELDS)
        assert "—" not in out and "–" not in out          # no em or en dashes
        assert not re.search(r"\b(testament|pivotal|tapestry|moreover|furthermore)\b", out, re.I)


def test_article_helper():
    assert stories.a_an("Eagles") == "an Eagles"
    assert stories.a_an("49ers") == "a 49ers"
    assert stories.a_an("Bills") == "a Bills"


def test_kick_line_and_stat_line():
    r = {"fg_missed_list": "43;47", "fg_blocked_list": None, "n_pat_missed": 1}
    assert stories.kick_line(r) == "Missed from 43 and 47, 1 extra point missed or blocked"
    s = {"n_incomplete": 18, "n_sacks": 8, "n_ints": 0, "n_fumbles": 3, "n_carries": 6, "n_receptions": 0}
    assert stories.stat_line(s) == "18 incompletions, 8 sacks, 3 fumbles, and 6 carries"


def _p(pid, pos, pts, **kw):
    base = dict(player_id=pid, player_display_name=pid, position=pos, team="AAA", opponent_team="PHI",
                sabotage_pts=pts, n_incomplete=0, n_sacks=0, n_ints=0, n_fumbles=0, n_fumbles_lost=0,
                n_carries=0, n_receptions=0, n_pick_sixes=0, n_pat_missed=0, pts_fumbles=0, pts_kicking=0,
                p6_value=31, fg_missed_list=None, fg_blocked_list=None)
    base.update(kw)
    return base


def test_build_does_not_feature_same_player_twice():
    players = [
        _p("QB1", "QB", 100, n_incomplete=20),
        _p("RB1", "RB", 60, n_fumbles=3, n_fumbles_lost=1, pts_fumbles=31),
        _p("WR1", "WR", 30, n_receptions=15),
    ]
    out = stories.build(5, players, [], 2026)
    who = [s["who"] for s in out]
    assert who.count("RB1") == 1
    assert {"QB1", "RB1", "WR1"} <= set(who)
    assert out[0]["label"] == "Saboteur of the week"


def test_washington_nickname_by_season():
    assert stories.nick("WAS", 2007) == "Redskins"
    assert stories.nick("WAS", 2021) == "Washington Football Team"
    assert stories.nick("WAS", 2022) == "Commanders"
    assert stories.nick("WAS") == "Commanders"
    assert stories.nick("LA", 2003) == "Rams"


def test_record_templates_render_and_follow_house_style():
    import records
    fields = {"name": "A. Player", "team": "Eagles", "opp": "Broncos", "a_opp": "a Broncos", "season": 2007,
              "week": 4, "value": "12", "units": "sacks", "pts": 60}
    for (stat, scope), opts in records.TEMPLATES.items():
        for t in opts:
            out = t.format(**fields)
            assert "—" not in out and "–" not in out, (stat, scope)
            assert "{" not in out
    # every scored stat has a game and a season story
    for stat, *_ in records.STATS:
        assert (stat, "game") in records.TEMPLATES and (stat, "season") in records.TEMPLATES


def test_position_percentiles(tmp_path):
    """Per-game rate vs qualified position peers; zero is always 0; under 4 games has none."""
    import json
    import export
    cols = export.PLAYER_COLS

    def row(pid, week, **v):
        r = {c: 0 for c in cols}
        r.update(player_id=pid, player_display_name=pid, position="QB", team="AAA", opponent_team="BBB", week=week)
        r.update(v)
        return [r[c] for c in cols]
    rows = []
    for pid, ints in (("A", 1), ("B", 2), ("C", 3)):          # 4 games each, 1/2/3 INT per game
        rows += [row(pid, w, n_ints=ints, sabotage_pts=10 * ints) for w in range(1, 5)]
    rows += [row("D", 1, n_ints=9, sabotage_pts=90)]          # 1 game: not qualified
    (tmp_path / "scores-2026.json").write_text(json.dumps({"cols": cols, "rows": rows}))
    out, idx = export.player_files(tmp_path, [2026])
    pct = lambda pid, k: dict(zip(out[pid]["seasons"]["cols"], out[pid]["seasons"]["rows"][0]))[k]
    # 3 qualified peers: C is highest (100), B middle (50), A lowest (0)
    assert (pct("C", "pct_n_ints"), pct("B", "pct_n_ints"), pct("A", "pct_n_ints")) == (100, 50, 0)
    assert pct("A", "pct_n_fg_missed") == 0                     # nobody misses kicks: 0, not 100
    assert pct("D", "pct_n_ints") is None                       # under 4 games
    assert [r[0] for r in idx["rows"]][0] == "C"               # search index sorted by career points


def test_target_totals_blank_if_any_game_missing():
    import polars as pl
    import export
    df = pl.DataFrame({"p": ["a", "a", "b", "b"], "n_targets": [5, None, 4, 6]}, schema={"p": pl.Utf8, "n_targets": pl.Int64})
    out = dict(df.group_by("p").agg(export.total_expr("n_targets")).iter_rows())
    # a: one game without targets -> blank; b: 4 + 6 = 10
    assert out["a"] is None and out["b"] == 10


@pytest.mark.parametrize("kind", list(stories.TEMPLATES))
def test_eighteen_distinct_lines_per_award(kind):
    lines = stories.TEMPLATES[kind]
    assert len(lines) == 18 and len(set(lines)) == 18


def test_line_follows_week_number():
    players = [_p("QB1", "QB", 100, n_incomplete=20)]
    w1 = stories.build(1, players, [], 2026)[0]["text"]
    w2 = stories.build(2, players, [], 2026)[0]["text"]
    w19 = stories.build(19, players, [], 2026)[0]["text"]
    assert w1 != w2 and w19 == w1          # week 19 (playoffs) wraps to line 1
    assert w1.startswith("QB1 played quarterback like a man returning a rental car")


def test_multiple_pick_sixes_use_their_own_list():
    # Two pick sixes at 31 each (10 for the interception + 21 bonus) = 62 points.
    players = [_p("QB1", "QB", 120, n_incomplete=10, n_ints=2, n_pick_sixes=2)]
    s = [x for x in stories.build(1, players, [], 2026) if x["kind"].startswith("pick_six")][0]
    assert s["kind"] == "pick_six_multi" and s["label"] == "Pick sixes"
    assert s["text"] == "QB1 threw 2 pick sixes to the Eagles. One is a mistake. Two is a habit. 62 points."
    one = [x for x in stories.build(1, [_p("QB2", "QB", 80, n_ints=1, n_pick_sixes=1)], [], 2026) if x["kind"].startswith("pick_six")][0]
    assert one["kind"] == "pick_six" and "31 points" in one["text"]


def test_owner_edits_applied():
    assert stories.TEMPLATES["top"][5].startswith("It must be getting close to Halloween")
    assert stories.TEMPLATES["top"][16] == "{name} plays quarterback the way a toddler plays Jenga. {line}. {pts} points."


def test_player_files_mix_old_and_new_season_files(tmp_path):
    # A season file written before n_targets existed and one written after must load together.
    import json
    import export
    base = ["player_id", "player_display_name", "position", "team", "opponent_team", "week"]
    old_cols = [c for c in export.PLAYER_COLS if c != "n_targets"]
    row = lambda cols, w: [("P1" if c == "player_id" else "Pat" if c == "player_display_name" else "WR" if c == "position"
                            else "AAA" if c == "team" else "BBB" if c == "opponent_team" else w if c == "week" else 1) for c in cols]
    (tmp_path / "scores-2025.json").write_text(json.dumps({"cols": old_cols, "rows": [row(old_cols, 1)]}))
    (tmp_path / "scores-2026.json").write_text(json.dumps({"cols": export.PLAYER_COLS, "rows": [row(export.PLAYER_COLS, 1)]}))
    files, index = export.player_files(tmp_path, [2025, 2026])
    seasons = files["P1"]["seasons"]
    tg = seasons["cols"].index("n_targets")
    assert [r[tg] for r in seasons["rows"]] == [None, 1]
