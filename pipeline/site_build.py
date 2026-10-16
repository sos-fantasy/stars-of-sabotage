"""Render the static site into an output folder.

Pages share one layout so the header, footer, fonts, and icons match.
The scoring tables on the method page come from config/scoring.yml, so
the published rules always match the rules the engine uses.
"""
from __future__ import annotations

import shutil
from html import escape
from pathlib import Path

from score import load_config

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

DESCRIPTION = ("Sabotage fantasy football stats: NFL players and defenses ranked by incompletions, "
               "sacks, turnovers, missed kicks, and points allowed.")


def layout(title: str, body: str, *, page: str, noindex: bool, scripts: str = "") -> str:
    robots = '<meta name="robots" content="noindex">\n' if noindex else ""
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if key == page else ""}>{label}</a>'
        for key, href, label in (("board", "./", "Leaderboard"), ("method", "method.html", "Scoring"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{robots}<title>{escape(title)}</title>
<meta name="description" content="{escape(DESCRIPTION)}">
<meta name="theme-color" content="#15140f">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(DESCRIPTION)}">
<meta property="og:image" content="assets/og-image.jpg">
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<link rel="preload" href="assets/fonts/anton-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/jetbrains-mono-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/styles.css">
</head>
<body class="page-{page}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <a class="brand" href="./" aria-label="Stars of Sabotage home">
    <picture><source srcset="assets/whoopsie-sm.webp" type="image/webp"><img src="assets/whoopsie-sm.png" alt="" width="44" height="49"></picture>
    <span class="wordmark">Stars of <em>Sabotage</em></span>
  </a>
  <nav aria-label="Main">{nav}</nav>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <p id="foot-status" class="foot-status"></p>
  <p>Data: <a href="https://github.com/nflverse/nflverse-data">nflverse</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Scores are computed by Stars of Sabotage and are not official.</p>
  <p>Not affiliated with or endorsed by the NFL, any NFL team, Yahoo, ESPN, CBS Sports, or Sleeper.</p>
</footer>
{scripts}
</body>
</html>
"""


BOARD_BODY = """
<section class="hero">
  <picture class="hero-art"><source srcset="assets/whoopsie.webp" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267"></picture>
  <div>
    <p class="eyebrow">A fantasy football league for everything that goes <span>wrong</span></p>
    <h1>The <span class="hl">Leaderboard</span></h1>
    <p class="lede">Every NFL player and defense since 1999, ranked by Sabotage points. <a href="method.html">How scoring works</a>.</p>
    <p class="weekline" id="weekline" aria-live="polite"></p>
  </div>
</section>

<section class="wreck" id="wreck" aria-labelledby="wreck-title" hidden>
  <h2 id="wreck-title"><span id="wreck-week"></span> wreckage report</h2>
  <div class="wreck-grid" id="wreck-grid"></div>
</section>

<section class="board" aria-labelledby="board-title">
  <h2 id="board-title" class="sr-only">Player and defense rankings</h2>
  <form class="controls" id="controls" onsubmit="return false">
    <div class="ctl">
      <label for="f-season">Season</label>
      <select id="f-season"></select>
    </div>
    <div class="ctl" id="weeks-ctl">
      <label for="f-from">Weeks</label>
      <div class="pair"><select id="f-from"></select><span>to</span><select id="f-to"></select>
        <button type="button" id="b-full" class="toggle" aria-pressed="true">Full season</button></div>
    </div>
    <fieldset class="ctl seg" id="rows-ctl" hidden>
      <legend>Rows</legend>
      <div class="segbtns">
        <button type="button" data-rows="career" aria-pressed="true">Career</button>
        <button type="button" data-rows="season" aria-pressed="false">Single seasons</button>
      </div>
    </fieldset>
    <fieldset class="ctl chips" id="f-pos">
      <legend>Position</legend>
    </fieldset>
    <div class="ctl">
      <label for="f-team">Team</label>
      <select id="f-team"><option value="">All teams</option></select>
    </div>
    <fieldset class="ctl seg">
      <legend>Show</legend>
      <div class="segbtns">
        <button type="button" data-view="total" aria-pressed="true">Totals</button>
        <button type="button" data-view="pg" aria-pressed="false">Per game</button>
      </div>
    </fieldset>
    <fieldset class="ctl seg">
      <legend>Columns</legend>
      <div class="segbtns">
        <button type="button" data-cols="pts" aria-pressed="true">Points</button>
        <button type="button" data-cols="cnt" aria-pressed="false">Stats</button>
      </div>
    </fieldset>
    <div class="ctl small">
      <label for="f-min">Min games</label>
      <input id="f-min" type="number" min="0" max="18" inputmode="numeric" value="0">
    </div>
    <div class="ctl grow">
      <label for="f-q">Find</label>
      <input id="f-q" type="search" placeholder="Player or team" autocomplete="off">
    </div>
    <div class="ctl actions">
      <button type="button" id="b-reset" class="ghost">Reset</button>
      <button type="button" id="b-csv" class="ghost">CSV</button>
    </div>
  </form>
  <p class="histnote" id="histnote" hidden>Past seasons are scored under the current Sabotage rules (v{version}) using Yahoo's points-allowed rule. Team codes follow nflverse, which uses today's abbreviations, so the 2012 Chargers show as LAC.</p>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="table-wrap" id="table-wrap" tabindex="0" aria-label="Leaderboard table, scrolls sideways on small screens">
    <table id="board">
      <thead></thead>
      <tbody><tr><td class="loading">Loading the damage report&hellip;</td></tr></tbody>
    </table>
  </div>
  <p class="hint">Click a column to sort. Click again to flip it, a third time to reset. Shift-click adds a second sort.</p>
</section>
"""


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


def _rows(pairs):
    return "\n".join(f'<tr><td>{escape(a)}</td><td class="num">{b}</td></tr>' for a, b in pairs)


def method_body() -> str:
    cfg = load_config()
    o, k, d = cfg["offense"], cfg["kicker"], cfg["defense"]["points_allowed"]
    offense = _rows((OFFENSE_LABELS[key], val) for key, val in o.items())
    kicker = _rows([(f"Field goal missed, {b} yards", v) for b, v in k["fg_missed"].items()]
                   + [("PAT missed", k["pat_missed"])])
    defense = _rows((f"{b} points allowed" if b != "0" else "Shutout (0 allowed)", v) for b, v in d.items())
    lost = o["fumble"] + o["fumble_lost"]
    six = o["interception_thrown"] + o["pick_six_thrown"]
    return METHOD_BODY.format(version=escape(cfg["version"]), offense=offense, kicker=kicker,
                              defense=defense, lost=lost, six=six)


METHOD_BODY = """
<article class="prose">
<p class="eyebrow">Scoring rules v{version}</p>
<h1>How Sabotage <span class="hl">scoring</span> works</h1>
<p class="lede">Most fantasy formats reward good football. This one rewards the plays that hurt a team: incompletions, sacks, turnovers, missed kicks, and defenses that give up points. Higher totals mean more sabotage.</p>

<h2>The scoring table</h2>
<h3>Offense: QB, RB, WR, TE</h3>
<div class="table-wrap plain"><table><thead><tr><th>Event</th><th class="num">Points</th></tr></thead><tbody>
{offense}
</tbody></table></div>
<p>A lost fumble earns both lines: {lost} points. A pick six earns both lines too: {six} points.</p>

<h3>Kickers</h3>
<div class="table-wrap plain"><table><thead><tr><th>Event</th><th class="num">Points</th></tr></thead><tbody>
{kicker}
</tbody></table></div>

<h3>Team defense</h3>
<div class="table-wrap plain"><table><thead><tr><th>Points allowed</th><th class="num">Points</th></tr></thead><tbody>
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
<div class="table-wrap plain"><table><thead><tr><th>Opponent scores on</th><th>Counts against the defense?</th></tr></thead><tbody>
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
<p class="eyebrow">Example</p>
<p><strong>Arizona at the Giants, 2026 Week 4.</strong> The Giants scored 36. Six of those came on a pick six with 11 seconds left, and the game ended without an extra point try. Arizona's defense is charged with 36 minus 6, which is 30. That lands in the 28-34 bucket, so Arizona scores 35 Sabotage points for the week instead of 42.</p>
</div>
<p>The other big platforms draw the line in about the same place. All of them count kick and punt return touchdowns against the defense. ESPN leaves out pick sixes and fumble return touchdowns. CBS Sports leaves out points scored against the offense, naming pick sixes and safeties. Sleeper leaves out touchdowns the defense scores itself, and charges every extra point. The help pages for ESPN and Sleeper do not say how safeties are handled.</p>

<h2>Where the data comes from</h2>
<p>Game statistics come from <a href="https://github.com/nflverse/nflverse-data">nflverse</a>, published under the <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> license. We do not use any fantasy platform's data.</p>
<p>Scores update several times on game days and once each morning. The NFL issues stat corrections from Monday through Wednesday, so every week is marked provisional until 10 AM Eastern on the Thursday after its last game, then final.</p>

<h2>Rule versions</h2>
<p>Every score on this site records the rule version that produced it. If the league changes its rules, past seasons are rescored under a new version, and the old version stays on record.</p>
<p>The archive goes back to 1999, the first season nflverse has play-by-play for. Every past season is scored under the current rules, including Yahoo's points-allowed rule, so a 2005 score means what it would mean today. Seasons before 2021 had 16 games, so compare per-game numbers across eras.</p>
</article>
"""


def _hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


HTACCESS = """# Written by pipeline/site_build.py
# Pages revalidate every visit; data refreshes within 5 minutes; versioned assets cache long.
<IfModule mod_headers.c>
  <FilesMatch "\\.(html)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  <FilesMatch "\\.(json)$">
    Header set Cache-Control "public, max-age=300"
  </FilesMatch>
  <FilesMatch "\\.(js|css|woff2|png|webp|jpg|ico)$">
    Header set Cache-Control "public, max-age=2592000"
  </FilesMatch>
</IfModule>
"""


def build(out: Path, noindex: bool = True) -> None:
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SITE / "assets", out / "assets", dirs_exist_ok=True)
    shutil.copy2(SITE / "favicon.ico", out / "favicon.ico")
    (out / ".htaccess").write_text(HTACCESS)
    # Version tags: a new release can never pair new HTML with an old cached script.
    a = out / "assets"
    foot_v = _hash(a / "foot.js")
    app = (a / "app.js").read_text().replace('from "./foot.js"', f'from "./foot.js?v={foot_v}"')
    (a / "app.js").write_text(app)
    v = {"css": _hash(a / "styles.css"), "app": _hash(a / "app.js"), "foot": foot_v}
    tag = lambda html: html.replace('href="assets/styles.css"', f'href="assets/styles.css?v={v["css"]}"')
    version = escape(load_config()["version"])
    (out / "index.html").write_text(tag(layout(
        "Stars of Sabotage | Sabotage fantasy football leaderboard", BOARD_BODY.replace("{version}", version),
        page="board", noindex=noindex,
        scripts=f'<script type="module" src="assets/app.js?v={v["app"]}"></script>')))
    (out / "method.html").write_text(tag(layout(
        "How Sabotage scoring works | Stars of Sabotage", method_body(), page="method", noindex=noindex,
        scripts=f'<script type="module" src="assets/foot.js?v={v["foot"]}"></script>')))


if __name__ == "__main__":
    import sys
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "dist"))
