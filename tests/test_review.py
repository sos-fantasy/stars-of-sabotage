"""Projection review: hand-computed checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import review as R  # noqa: E402

W = {"n_incomplete": 2, "n_sacks": 5, "n_carries": 1, "n_receptions": 2, "n_fumbles": 7, "n_fumbles_lost": 10,
     "n_ints": 10, "n_pick_sixes": 21, "pts_kicking": 1}


def test_luck_for_a_lost_fumble():
    # A tight end projected for 0.04 fumbles, half of them lost (0.02). A lost fumble is
    # 17 points. The projection is 0.04*7 + 0.02*10 = 0.48, so one lost fumble misses by
    # 16.52. P(at least one lost fumble) = 1 - exp(-0.02) = 1.98%. Two plain fumbles
    # (14 points) fall short of 16.5, and three are vanishingly rare.
    p = R.luck_probability({"n_receptions": 0.0, "n_fumbles": 0.04, "n_fumbles_lost": 0.02}, W, 16.5, sims=400000)
    assert 0.017 < p < 0.023


def test_range_probability_half_width():
    # 10th to 90th range of 0 to 25.6 means sd = 10. A miss of 10 is one sd: P(|z|>=1) = 31.7%.
    assert abs(R.range_probability(12.8, 0, 25.6, 10) - 0.3173) < 0.001


def test_tally_counts_and_shares():
    weeks = [{"top": [{"tags": ["volume", "turnover_luck"]}, {"tags": ["volume"]}]},
             {"top": [{"tags": ["game_script"]}, {"tags": []}]}]
    t = {r["tag"]: r for r in R.tally(weeks)}
    assert t["volume"]["count"] == 2 and t["volume"]["share"] == 0.5
    assert t["game_script"]["count"] == 1 and t["turnover_luck"]["share"] == 0.25


def test_claude_request_shape(monkeypatch):
    import io, json, urllib.request
    seen = {}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=0):
        seen["url"], seen["headers"], seen["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return Resp(json.dumps({"content": [{"type": "text", "text": "Watson threw a lot — and missed."}]}).encode())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    week = {"season": 2026, "week": 5, "summary": {}, "range_hit": 0.8, "did_not_play_n": 0, "top": []}
    text = R.claude_summary(week, [])
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["X-api-key"] == "test-key" and seen["headers"]["Anthropic-version"] == "2023-06-01"
    assert seen["body"]["model"] == "claude-sonnet-5-5" and "system" in seen["body"]
    assert "—" not in text


def test_no_key_no_call(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert R.claude_summary({"season": 2026, "week": 5, "summary": {}, "range_hit": 1, "did_not_play_n": 0, "top": []}, []) is None
