"""Download retries and the hourly gate's fallback (after the November 8, 2026 outage)."""
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import nflsafe  # noqa: E402
import run  # noqa: E402
import schedule  # noqa: E402

ET = schedule.ET
GATEWAY = ConnectionError("Failed to download games.parquet: 504 Server Error: Gateway Time-out")


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    waited = []
    monkeypatch.setattr(nflsafe, "_sleep", waited.append)
    return waited


def flaky(failures, result="ok", exc=GATEWAY):
    calls = []

    def load_thing(*args):
        calls.append(args)
        if len(calls) <= failures:
            raise exc
        return result
    return load_thing, calls


def test_retry_recovers_after_two_failures(no_waiting):
    fn, calls = flaky(2)
    assert nflsafe.retry(fn)(2026) == "ok"
    assert len(calls) == 3
    assert no_waiting == [15, 45]


def test_retry_gives_up_after_three_tries():
    fn, calls = flaky(5)
    with pytest.raises(ConnectionError):
        nflsafe.retry(fn)(2026)
    assert len(calls) == 3


def test_retry_also_covers_read_timeouts():
    fn, calls = flaky(1, exc=TimeoutError("Read timed out. (read timeout=30)"))
    assert nflsafe.retry(fn)() == "ok"
    assert len(calls) == 2


def test_non_network_errors_are_not_retried():
    fn, calls = flaky(1, exc=KeyError("gameday"))
    with pytest.raises(KeyError):
        nflsafe.retry(fn)()
    assert len(calls) == 1


def test_every_loader_is_wrapped():
    assert nflsafe.load_schedules.__wrapped__ is nflsafe._nfl.load_schedules
    assert nflsafe.load_pbp.__wrapped__ is nflsafe._nfl.load_pbp


def _deploy_copy(tmp_path, gamedays):
    rows = [[1, f"g{i}", d, "13:00", "AAA", "BBB", None, None, "outdoors", None, None]
            for i, d in enumerate(gamedays)]
    (tmp_path / "games-2026.json").write_text(json.dumps({"cols": [
        "week", "game_id", "gameday", "gametime", "home_team", "away_team",
        "home_score", "away_score", "roof", "wind", "temp"], "rows": rows}))
    return tmp_path


def test_gate_falls_back_to_deploy_copy(tmp_path):
    # Hand check: November 8, 2026 was a Sunday game day (nflverse schedule).
    prev = _deploy_copy(tmp_path, ["2026-11-05", "2026-11-08", "2026-11-09"])

    def down(season):
        raise GATEWAY
    dates = run.gate_game_dates(2026, prev, loader=down)
    assert dates == {date(2026, 11, 5), date(2026, 11, 8), date(2026, 11, 9)}
    # The three failed runs: 3:52, 4:47, 5:43 AM ET Sunday. Nothing was due.
    for h, m in [(3, 52), (4, 47), (5, 43)]:
        assert not schedule.is_due(datetime(2026, 11, 8, h, m, tzinfo=ET), dates)[0]
    # 6:40 AM daily refresh and the 7 PM game-day slot still run on the fallback dates.
    assert schedule.is_due(datetime(2026, 11, 8, 6, 40, tzinfo=ET), dates)[0]
    assert schedule.is_due(datetime(2026, 11, 8, 19, 40, tzinfo=ET), dates)[0]


def test_gate_prefers_live_schedule(tmp_path):
    prev = _deploy_copy(tmp_path, ["2026-11-01"])

    class Sched(dict):
        pass
    live = Sched(gameday=type("S", (), {"to_list": lambda self: ["2026-11-08"]})())
    assert run.gate_game_dates(2026, prev, loader=lambda s: live) == {date(2026, 11, 8)}


def test_gate_raises_when_no_copy_exists(tmp_path):
    def down(season):
        raise GATEWAY
    with pytest.raises(ConnectionError):
        run.gate_game_dates(2026, tmp_path, loader=down)
    with pytest.raises(ConnectionError):
        run.gate_game_dates(2026, None, loader=down)
