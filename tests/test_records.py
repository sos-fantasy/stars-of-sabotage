"""Record alerts: a current-season line that passes or ties an all-time record."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import export  # noqa: E402
import records  # noqa: E402
import score  # noqa: E402


def _row(pid, name, week, **vals):
    r = {c: 0 for c in export.PLAYER_COLS}
    r.update(player_id=pid, player_display_name=name, position="QB", team="DET", opponent_team="CLE", week=week)
    r.update(vals)
    return [r[c] for c in export.PLAYER_COLS]


def _write(d: Path, season: int, rows, drows=()):
    (d / f"scores-{season}.json").write_text(json.dumps({"cols": export.PLAYER_COLS, "rows": rows}))
    (d / f"defense-{season}.json").write_text(json.dumps({"cols": export.DEF_COLS, "rows": list(drows)}))


WEEKS = [  # current season: week 1 final, week 2 provisional (last game Mon Sep 21, 2026)
    {"week": 1, "status": "final", "last_day": "2026-09-14"},
    {"week": 2, "status": "provisional", "last_day": "2026-09-21"},
]


def _alerts(tmp_path, cur_rows):
    _write(tmp_path, 2001, [_row("old", "Ty Detmer", 2, n_ints=7)])
    _write(tmp_path, 2026, cur_rows)
    r = records.build(tmp_path, [2001, 2026], score.load_config(), 2026, WEEKS)
    return {(a["stat"], a["scope"]): a for a in r["alerts"]}, r


def test_broken_game_record_is_pending_until_thursday(tmp_path):
    a, r = _alerts(tmp_path, [_row("new", "New Guy", 2, n_ints=8)])
    g = a[("n_ints", "game")]
    assert g["kind"] == "broken" and not g["official"] and g["title"] == "Potential record broken"
    assert g["value"] == 8 and g["previous"] == 7 and g["week"] == 2
    # Monday Sep 21 last game -> final 10 AM ET Thursday Sep 24
    assert "Thursday, September 24" in g["text"] and "Ty Detmer's 7 from 2001" in g["text"]
    rec = next(s for s in r["stats"] if s["stat"] == "n_ints")["records"][0]
    assert rec["alert"]["title"] == "Potential record broken"


def test_tied_record_names_the_holder(tmp_path):
    a, _ = _alerts(tmp_path, [_row("new", "New Guy", 2, n_ints=7)])
    g = a[("n_ints", "game")]
    assert g["kind"] == "tied" and g["title"] == "Potential record tied" and "Ty Detmer (2001)" in g["text"]


def test_record_in_final_week_is_official(tmp_path):
    a, _ = _alerts(tmp_path, [_row("new", "New Guy", 1, n_ints=9)])
    g = a[("n_ints", "game")]
    assert g["official"] and g["title"] == "Record broken" and "official" in g["text"]


def test_season_record_week_is_when_running_total_passed_it(tmp_path):
    # old season record: 7 (Detmer's only game). New Guy: 4 in week 1, 4 in week 2 -> passes in week 2
    a, _ = _alerts(tmp_path, [_row("new", "New Guy", 1, n_ints=4), _row("new", "New Guy", 2, n_ints=4)])
    s = a[("n_ints", "season")]
    assert s["kind"] == "broken" and s["week"] == 2 and not s["official"] and "8 interceptions" in s["text"]


def test_no_alert_when_record_not_reached(tmp_path):
    a, _ = _alerts(tmp_path, [_row("new", "New Guy", 2, n_ints=6)])
    assert ("n_ints", "game") not in a


def test_alert_text_house_style(tmp_path):
    a, _ = _alerts(tmp_path, [_row("new", "New Guy", 2, n_ints=8, n_sacks=20)])
    for al in a.values():
        assert "—" not in al["text"] and "–" not in al["text"] and "{" not in al["text"]
