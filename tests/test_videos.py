"""Video ingestion: week assignment, manual overrides, carry-forward, embed checks."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import videos  # noqa: E402

# Week 5 ends Monday Oct 5, week 6 runs Thursday Oct 8 to Monday Oct 12.
GAMES = [
    {"week": 5, "gameday": "2026-10-01"}, {"week": 5, "gameday": "2026-10-04"}, {"week": 5, "gameday": "2026-10-05"},
    {"week": 6, "gameday": "2026-10-08"}, {"week": 6, "gameday": "2026-10-11"}, {"week": 6, "gameday": "2026-10-12"},
]
ENDS = videos.week_ends(GAMES)


def feed(*entries):
    items = "".join(f"""<entry><yt:videoId>{i}</yt:videoId><title>{t}</title><published>{p}</published></entry>"""
                    for i, t, p in entries)
    return f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"><title>NFL Rush</title>{items}</feed>"""


def fake_get(feed_xml, embed=None):
    embed = embed or {}
    def get(url):
        if "feeds/videos.xml" in url:
            return 200, feed_xml
        vid = url.rsplit("v=", 1)[1]
        code = embed.get(vid, 200)
        return code, json.dumps({"title": f"oEmbed title {vid}", "author_name": "NFL Rush"}) if code == 200 else ""
    return get


def test_video_id_forms():
    assert videos.video_id("https://www.youtube.com/watch?v=UhtGp5GH7Zo&t=30s") == "UhtGp5GH7Zo"
    assert videos.video_id("https://youtu.be/UhtGp5GH7Zo") == "UhtGp5GH7Zo"
    assert videos.video_id("https://www.youtube.com/shorts/UhtGp5GH7Zo") == "UhtGp5GH7Zo"
    assert videos.video_id("UhtGp5GH7Zo") == "UhtGp5GH7Zo"
    assert videos.video_id("not a link") is None


def test_assign_week_by_date():
    # Tuesday Oct 6, 2026 at 3 PM ET (19:00 UTC): week 5 ended Monday, so week 5.
    assert videos.assign_week("Worst plays of the week", "2026-10-06T19:00:00+00:00", ENDS) == 5
    # Monday Oct 12 at 8 PM ET (00:00 UTC Tuesday): week 6's last game is that day, so week 6.
    assert videos.assign_week("Worst plays", "2026-10-13T00:00:00+00:00", ENDS) == 6
    # Thursday Oct 8 at noon ET, mid week 6: still week 5.
    assert videos.assign_week("Worst plays", "2026-10-08T16:00:00+00:00", ENDS) == 5
    # Before any week has finished: no week.
    assert videos.assign_week("Worst plays", "2026-09-30T16:00:00+00:00", ENDS) is None


def test_title_week_wins_when_finished():
    # Posted Oct 14 (after week 6) but titled week 5: the title wins.
    assert videos.assign_week("NFL Worst Plays of Week 5 (2026)", "2026-10-14T16:00:00+00:00", ENDS) == 5
    # Title names a week that has not finished by the publish date: fall back to the date rule.
    assert videos.assign_week("Worst plays week 9", "2026-10-14T16:00:00+00:00", ENDS) == 6


def test_build_filters_titles_and_checks_embeds():
    xml = feed(("AAAAAAAAAAA", "NFL Worst Plays of Week 6", "2026-10-13T15:00:00+00:00"),
               ("BBBBBBBBBBB", "Best catches of Week 6", "2026-10-13T16:00:00+00:00"),
               ("CCCCCCCCCCC", "Worst Plays of Week 5", "2026-10-06T15:00:00+00:00"))
    src = [{"name": "NFL Rush", "channel_id": "X", "title_pattern": "worst plays"}]
    out = videos.build(2026, GAMES, [], src, [], get=fake_get(xml, {"CCCCCCCCCCC": 401}), log=lambda *_: None)
    assert [(v["week"], v["id"], v["embed"]) for v in out] == [(6, "AAAAAAAAAAA", "yes"), (5, "CCCCCCCCCCC", "no")]


def test_manual_row_replaces_week_and_none_hides():
    xml = feed(("AAAAAAAAAAA", "Worst Plays Week 6", "2026-10-13T15:00:00+00:00"),
               ("CCCCCCCCCCC", "Worst Plays Week 5", "2026-10-06T15:00:00+00:00"))
    src = [{"name": "NFL Rush", "channel_id": "X", "title_pattern": "worst plays"}]
    manual = [{"season": 2026, "week": 6, "id": "MMMMMMMMMMM", "title": "", "hide": False},
              {"season": 2026, "week": 5, "id": None, "title": "", "hide": True}]
    out = videos.build(2026, GAMES, [], src, manual, get=fake_get(xml), log=lambda *_: None)
    assert [(v["week"], v["id"], v["source"]) for v in out] == [(6, "MMMMMMMMMMM", "manual")]
    assert (out[0]["title"], out[0]["channel"]) == ("oEmbed title MMMMMMMMMMM", "NFL Rush")


def test_carry_forward_and_drop_removed():
    prev = [{"season": 2026, "week": 4, "id": "OLDOLDOLDOL", "title": "Worst Plays Week 4", "channel": "NFL Rush",
             "published": "2026-09-29T15:00:00+00:00", "source": "auto", "embed": "yes"},
            {"season": 2026, "week": 3, "id": "GONEGONEGON", "title": "Worst Plays Week 3", "channel": "NFL Rush",
             "published": "2026-09-22T15:00:00+00:00", "source": "auto", "embed": "yes"}]
    out = videos.build(2026, GAMES, prev, [], [], get=fake_get(feed(), {"GONEGONEGON": 404}), log=lambda *_: None)
    assert [v["id"] for v in out] == ["OLDOLDOLDOL"]


def test_feed_failure_keeps_previous():
    prev = [{"season": 2026, "week": 4, "id": "OLDOLDOLDOL", "title": "t", "channel": "c",
             "published": "2026-09-29T15:00:00+00:00", "source": "auto", "embed": "yes"}]
    def get(url):
        if "feeds" in url:
            raise OSError("network down")
        return 200, "{}"
    out = videos.build(2026, GAMES, prev, [{"name": "NFL Rush", "channel_id": "X"}], [], get=get, log=lambda *_: None)
    assert [v["id"] for v in out] == ["OLDOLDOLDOL"]


def test_playlist_feed_uses_entry_author_and_no_filter():
    xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <title>2026 Worst Plays</title>
      <entry><yt:videoId>PPPPPPPPPPP</yt:videoId><title>Week 6 disasters</title>
        <published>2026-10-14T15:00:00+00:00</published><author><name>Trenz</name></author></entry></feed>"""
    seen = []
    def get(url):
        seen.append(url)
        return (200, xml) if "feeds" in url else (200, "{}")
    out = videos.build(2026, GAMES, [], [{"name": "pl", "playlist_id": "PLX"}], [], get=get, log=lambda *_: None)
    assert seen[0].endswith("playlist_id=PLX")
    assert [(v["week"], v["channel"]) for v in out] == [(6, "Trenz")]


def test_play_on_site_flag(tmp_path):
    f = tmp_path / "s.yml"
    f.write_text("play_on_site: false\nsources: []\n")
    assert videos.play_on_site(f) is False
    f.write_text("sources: []\n")
    assert videos.play_on_site(f) is True
    assert videos.play_on_site(tmp_path / "missing.yml") is True
    assert videos.play_on_site() is False   # the live config, set Oct 18, 2026
