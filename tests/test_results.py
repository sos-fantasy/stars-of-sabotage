"""Projected vs actual, with hand-computed examples."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import results as R  # noqa: E402
import review as RV  # noqa: E402

GAMES = [{"week": 7, "game_id": "g1", "gameday": "2026-10-22", "gametime": "20:15", "home_team": "CHI", "away_team": "NE",
          "home_score": 30, "away_score": 24},
         {"week": 7, "game_id": "g2", "gameday": "2026-10-25", "gametime": "13:00", "home_team": "ATL", "away_team": "SF",
          "home_score": None, "away_score": None},
         {"week": 7, "game_id": "g3", "gameday": "2026-10-22", "gametime": "13:00", "home_team": "DAL", "away_team": "PHI",
          "home_score": 20, "away_score": 17}]


def p(pid, team, gid, proj, lo, hi, **kw):
    return {"id": pid, "name": pid.upper(), "pos": "QB", "team": team, "opp": "X", "home": 1, "game_id": gid,
            "proj": proj, "lo": lo, "hi": hi, **kw}


def test_week_results_statuses_and_misses():
    log = {"source": "live", "players": {
        "a": p("a", "CHI", "g1", 46.9, 25, 70),           # scored 42: miss 42 - 46.9 = -4.9, inside 25-70
        "b": p("b", "NE", "g1", 52.0, 40, 80),            # scored 38: miss -14.0, below the range
        "c": p("c", "CHI", "g1", 16.2, 6, 30),            # no stat line, CHI stats are in: did not play
        "d": p("d", "CHI", "g1", 9.0, 2, 18, removed=True),  # dropped before kickoff, did not play
        "e": p("e", "ATL", "g2", 20.0, 8, 34),            # game not played yet
        "f": p("f", "DAL", "g3", 12.0, 4, 22)},           # game over, no DAL stats posted yet
        "defenses": {"CHI": {"opp": "NE", "game_id": "g1", "proj": 27.3, "lo": 14, "hi": 42}}}
    scores = [{"player_id": "a", "team": "CHI", "week": 7, "sabotage_pts": 42},
              {"player_id": "b", "team": "NE", "week": 7, "sabotage_pts": 38}]
    defense = [{"team": "CHI", "week": 7, "sabotage_pts": 28}]   # 28 - 27.3 = +0.7
    w = R.week_results(2026, 7, log, scores, defense, GAMES)
    by = {r["id"]: r for r in w["rows"]}
    assert (by["a"]["actual"], by["a"]["miss"], by["a"]["in_range"], by["a"]["status"]) == (42, -4.9, True, "final")
    assert (by["b"]["miss"], by["b"]["in_range"]) == (-14.0, False)
    assert by["c"]["status"] == "dnp" and by["d"]["status"] == "removed"
    assert by["e"]["status"] == "pending" and by["f"]["status"] == "awaiting"
    assert (by["CHI"]["miss"], by["CHI"]["home"], by["CHI"]["status"]) == (0.7, 1, "final")
    # Averages use final rows only: (4.9 + 14.0 + 0.7) / 3 = 6.53 -> 6.5; 2 of 3 inside the range.
    assert w["n_final"] == 3 and w["avg_miss"] == 6.5 and w["in_range"] == 0.667
    assert w["summary"]["QB"] == {"n": 2, "avg_miss": 9.4, "in_range": 0.5}   # (4.9 + 14.0) / 2 = 9.45 -> 9.4
    assert w["game_info"]["g1"]["kickoff"] == "2026-10-23T00:15:00+00:00"     # 8:15 PM EDT
    # Every game of the week gets a card, earliest kickoff first, with the score once final.
    assert [c["game_id"] for c in w["cards"]] == ["g3", "g1", "g2"]
    assert (w["cards"][1]["away_score"], w["cards"][1]["home_score"]) == (24, 30)


def test_replayed_week_finds_game_by_team():
    log = {"source": "replayed", "players": {"a": {**p("a", "CHI", None, 40.0, 20, 60)}}, "defenses": {}}
    w = R.week_results(2026, 7, log, [{"player_id": "a", "team": "CHI", "week": 7, "sabotage_pts": 50}], [], GAMES)
    r = w["rows"][0]
    assert (r["game_id"], r["status"], r["miss"]) == ("g1", "final", 10.0)


def test_log_flags_players_dropped_before_kickoff():
    proj = {"season": 2026, "week": 7,
            "games": [{"game_id": "g2", "gameday": "2026-10-25", "gametime": "13:00", "weather": None}],
            "players": [p("x", "ATL", "g2", 10.0, 2, 20), p("y", "ATL", "g2", 8.0, 1, 18)], "defenses": []}
    friday = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)
    log = RV.update_log({}, proj, friday)
    assert not log["players"]["x"]["removed"] and not log["players"]["y"]["removed"]
    assert log["games"]["g2"]["gametime"] == "13:00"
    # Saturday: y ruled out and dropped from the starters. He keeps Friday's projection, flagged.
    proj2 = {**proj, "players": [p("x", "ATL", "g2", 10.5, 2, 20)]}
    log = RV.update_log(log, proj2, datetime(2026, 10, 24, 18, tzinfo=timezone.utc))
    assert log["players"]["x"]["proj"] == 10.5 and log["players"]["y"]["removed"] is True
    assert log["players"]["y"]["proj"] == 8.0
    # After kickoff nothing changes, even if the starters list does.
    log = RV.update_log(log, {**proj, "players": []}, datetime(2026, 10, 25, 18, tzinfo=timezone.utc))
    assert log["players"]["x"]["removed"] is False and log["players"]["x"]["proj"] == 10.5
