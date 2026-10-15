"""Render site/method.html from config/scoring.yml so the published rules
always match the rules the engine uses. Run: python pipeline/build_method.py"""
from html import escape
from pathlib import Path

from score import CONFIG_PATH, load_config

OUT = Path(__file__).resolve().parent.parent / "site" / "method.html"

OFFENSE_LABELS = {
    "incomplete_pass": "Incomplete pass",
    "sack_taken": "Sack taken",
    "rush_attempt": "Rushing attempt",
    "reception": "Reception",
    "fumble": "Fumble",
    "fumble_lost": "Fumble lost (adds to the fumble)",
    "interception_thrown": "Interception thrown",
    "pick_six_thrown": "Pick six thrown (adds to the interception)",
}


def rows(pairs):
    return "\n".join(f"<tr><td>{escape(a)}</td><td class=\"num\">{b}</td></tr>" for a, b in pairs)


def build() -> str:
    cfg = load_config(CONFIG_PATH)
    o, k, d = cfg["offense"], cfg["kicker"], cfg["defense"]["points_allowed"]
    offense = rows((OFFENSE_LABELS[key], val) for key, val in o.items())
    kicker = rows([(f"Field goal missed, {b} yards", v) for b, v in k["fg_missed"].items()]
                  + [("PAT missed", k["pat_missed"])])
    defense = rows((f"{b} points allowed" if b != "0" else "Shutout (0 allowed)", v) for b, v in d.items())
    lost = o["fumble"] + o["fumble_lost"]
    six = o["interception_thrown"] + o["pick_six_thrown"]
    return TEMPLATE.format(version=escape(cfg["version"]), offense=offense, kicker=kicker,
                           defense=defense, lost=lost, six=six)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scoring and Method | Stars of Sabotage</title>
<meta name="description" content="How Stars of Sabotage scores NFL players and defenses, where the data comes from, and how points allowed is counted.">
<style>
:root {{ --bg:#fbfaf7; --ink:#1d1d1b; --muted:#5c5a55; --line:#dcd8cf; --accent:#b3261e; --panel:#ffffff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141413; --ink:#ecebe6; --muted:#a9a69d; --line:#34332f; --accent:#f08a80; --panel:#1c1c1a; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:17px/1.6 Georgia, "Times New Roman", serif; }}
main {{ max-width:46rem; margin:0 auto; padding:2.5rem 1rem 4rem; }}
h1 {{ font:700 2.1rem/1.15 system-ui, sans-serif; margin:0 0 .4rem; letter-spacing:-.01em; }}
h2 {{ font:700 1.25rem/1.3 system-ui, sans-serif; margin:2.6rem 0 .6rem; padding-top:1rem; border-top:2px solid var(--ink); }}
h3 {{ font:700 1rem/1.3 system-ui, sans-serif; margin:1.6rem 0 .4rem; }}
.lede {{ color:var(--muted); margin-top:0; }}
.tag {{ display:inline-block; font:600 .75rem/1 system-ui, sans-serif; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); margin-bottom:.8rem; }}
table {{ width:100%; border-collapse:collapse; margin:.6rem 0 1.2rem; background:var(--panel); font:15px/1.4 system-ui, sans-serif; }}
th, td {{ text-align:left; padding:.5rem .7rem; border-bottom:1px solid var(--line); }}
th {{ font-weight:600; color:var(--muted); font-size:.8rem; text-transform:uppercase; letter-spacing:.05em; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.example {{ background:var(--panel); border-left:4px solid var(--accent); padding:.9rem 1.1rem; margin:1rem 0; font:15px/1.55 system-ui, sans-serif; }}
.example p {{ margin:.3rem 0; }}
.wrap {{ overflow-x:auto; }}
a {{ color:var(--accent); }}
footer {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line); color:var(--muted); font:14px/1.5 system-ui, sans-serif; }}
</style>
</head>
<body>
<main>
<span class="tag">Scoring rules v{version}</span>
<h1>How Sabotage scoring works</h1>
<p class="lede">Most fantasy formats reward good football. This one rewards the plays that hurt a team: incompletions, sacks, turnovers, missed kicks, and defenses that give up points. Higher totals mean more sabotage.</p>

<h2>The scoring table</h2>
<h3>Offense: QB, RB, WR, TE</h3>
<div class="wrap"><table><thead><tr><th>Event</th><th class="num">Points</th></tr></thead><tbody>
{offense}
</tbody></table></div>
<p>A lost fumble earns both lines: {lost} points. A pick six earns both lines too: {six} points.</p>

<h3>Kickers</h3>
<div class="wrap"><table><thead><tr><th>Event</th><th class="num">Points</th></tr></thead><tbody>
{kicker}
</tbody></table></div>

<h3>Team defense</h3>
<div class="wrap"><table><thead><tr><th>Points allowed</th><th class="num">Points</th></tr></thead><tbody>
{defense}
</tbody></table></div>
<p>A shutout scores nothing. A defense that good was not sabotaging anyone.</p>

<h2>How each stat is counted</h2>
<p>Fumbles count for any offensive player, on any play where his team has the ball or he is returning a kick or punt. That includes a quarterback who drops or botches a snap. A lost fumble goes to the last offensive player who lost control of the ball. Fumbles by defensive players never count.</p>
<p>Field goal distance is the full kick distance: from the spot of the hold to the goalposts. It is the number you hear on the broadcast.</p>
<p>Blocked field goals and blocked extra points count as misses. A blocked 23-yard try scores the same as a missed 23-yard try.</p>
<p>Rushing attempts include quarterback kneel-downs, because official NFL statistics record them as carries. Spikes to stop the clock count as incomplete passes for the same reason.</p>

<h2>Points allowed, and why it is not always the final score</h2>
<p>A defense is charged only for points it actually gave up. Points the other team scored against the offense do not count against the defense. We follow the same rule Yahoo uses, since Stars of Sabotage leagues are scored on Yahoo.</p>
<div class="wrap"><table><thead><tr><th>Opponent scores on</th><th>Counts against the defense?</th></tr></thead><tbody>
<tr><td>Offensive touchdowns and field goals</td><td>Yes</td></tr>
<tr><td>Kickoff and punt return touchdowns</td><td>Yes. Special teams belong to the defense unit</td></tr>
<tr><td>Every extra point and two-point conversion</td><td>Yes, even after a pick six</td></tr>
<tr><td>Interception return touchdowns (pick sixes)</td><td>No</td></tr>
<tr><td>Fumble return touchdowns</td><td>No</td></tr>
<tr><td>Blocked field goal return touchdowns</td><td>No</td></tr>
<tr><td>Safeties</td><td>No</td></tr>
<tr><td>Defensive two-point returns</td><td>No</td></tr>
</tbody></table></div>
<div class="example">
<p><strong>Example: Arizona at the Giants, 2026 Week 4.</strong></p>
<p>The Giants scored 36. Six of those came on a pick six with 11 seconds left, and the game ended without an extra point try. Arizona's defense is charged with 36 minus 6, which is 30. That lands in the 28-34 bucket, so Arizona scores 35 Sabotage points for the week instead of 42.</p>
</div>
<p>The other big platforms draw the line in about the same place. All of them count kick and punt return touchdowns against the defense. ESPN leaves out pick sixes and fumble return touchdowns. CBS Sports leaves out points scored against the offense, naming pick sixes and safeties. Sleeper leaves out touchdowns the defense scores itself, and charges every extra point. The help pages for ESPN and Sleeper do not say how safeties are handled.</p>

<h2>Where the data comes from</h2>
<p>Game statistics come from <a href="https://github.com/nflverse/nflverse-data">nflverse</a>, published under the <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> license. We do not use any fantasy platform's data.</p>
<p>Scores update after each game day. The NFL issues stat corrections from Monday through Wednesday, so every week is marked provisional until the Thursday morning refresh, then final.</p>

<h2>Rule versions</h2>
<p>Every score on this site records the rule version that produced it. If the league changes its rules, past seasons are rescored under a new version, and the old version stays on record. Seasons before 2026 are scored under the current rules, which may differ from the rules the league used at the time.</p>

<footer>
<p>Stars of Sabotage is not affiliated with or endorsed by the NFL, any NFL team, Yahoo, ESPN, CBS Sports, or Sleeper.</p>
<p>Data: nflverse (CC BY 4.0).</p>
</footer>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT}")
