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


NAV = (("board", "./", "Leaderboard"), ("compare", "compare.html", "Compare"), ("defenses", "defenses.html", "Defenses"), ("video", "video.html", "Video"), ("matchups", "matchups.html", "Matchups"),
       ("depth", "depth.html", "Depth Charts"), ("supers", "super-stars.html", "Super Stars"), ("method", "method.html", "Scoring"))

HEAD_SEARCH = """<div class="hsearch" data-search role="search">
    <label class="sr-only" for="q-head">Search players and teams</label>
    <input id="q-head" type="search" placeholder="Search players, teams" autocomplete="off" spellcheck="false"
      role="combobox" aria-expanded="false" aria-controls="q-head-list" aria-autocomplete="list">
    <ul id="q-head-list" role="listbox" class="results" hidden></ul>
  </div>"""

BIG_SEARCH = """<section class="bigsearch" data-search role="search" aria-label="Find a player or defense">
  <div class="field">
    <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    <label class="sr-only" for="q-big">Search players and teams</label>
    <input id="q-big" type="search" placeholder="Find a player or defense, any season since 1999" autocomplete="off" spellcheck="false"
      role="combobox" aria-expanded="false" aria-controls="q-big-list" aria-autocomplete="list">
    <div class="spos" role="group" aria-label="Limit to a position">
      <button type="button" data-spos="ALL" aria-pressed="true">All</button><button type="button" data-spos="QB" aria-pressed="false">QB</button><button type="button" data-spos="RB" aria-pressed="false">RB</button><button type="button" data-spos="WR" aria-pressed="false">WR</button><button type="button" data-spos="TE" aria-pressed="false">TE</button><button type="button" data-spos="K" aria-pressed="false">K</button><button type="button" data-spos="DEF" aria-pressed="false">DEF</button>
    </div>
  </div>
  <ul id="q-big-list" role="listbox" class="results" hidden></ul>
</section>"""


def layout(title: str, body: str, *, page: str, noindex: bool, scripts: str = "", dv: str = "") -> str:
    robots = '<meta name="robots" content="noindex">\n' if noindex else ""
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if key == page else ""}>{label}</a>'
        for key, href, label in NAV
    )
    search = "" if page == "board" else HEAD_SEARCH   # the home page has the big search instead
    scripts = '<script type="module" src="assets/common.js"></script>\n' + scripts
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
<body class="page-{page}" data-dv="{escape(dv)}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <a class="brand" href="./" aria-label="Stars of Sabotage home">
    <picture><source srcset="assets/whoopsie-sm.webp" type="image/webp"><img src="assets/whoopsie-sm.png" alt="" width="44" height="49"></picture>
    <span class="wordmark">Stars of <em>Sabotage</em></span>
  </a>
  <nav aria-label="Main">{nav}</nav>
  {search}
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
  <picture class="hero-art"><source srcset="assets/whoopsie-240.webp 240w, assets/whoopsie.webp 480w" sizes="(max-width: 720px) 120px, 168px" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267" fetchpriority="low"></picture>
  <div>
    <p class="eyebrow">A fantasy football league for everything that goes <span>wrong</span></p>
    <h1>The <span class="hl">Leaderboard</span></h1>
    <p class="lede">Every NFL player and defense since 1999, ranked by Sabotage points. <a href="method.html">How scoring works</a>.</p>
    <p class="weekline" id="weekline" aria-live="polite"></p>
  </div>
</section>

__BIG_SEARCH__

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
  <p class="more-row"><button type="button" id="b-more" class="ghost" hidden>Show more</button></p>
  <p class="hint">Click a column to sort. Click again to flip it, a third time to reset. Shift-click adds a second sort.</p>
</section>
"""


PLAYER_BODY = """
<section class="phero">
  <div>
    <p class="eyebrow">Player</p>
    <h1 id="p-name">Loading&hellip;</h1>
    <p class="pmeta" id="p-meta"></p>
  </div>
  <div class="pctl">
    <div class="ctl">
      <label for="p-season">Season</label>
      <select id="p-season"></select>
    </div>
    <a class="btn" id="p-compare" href="compare.html">Compare</a>
  </div>
</section>
<div id="p-body">
  <div class="next-box" id="p-next" hidden></div>
  <section class="tiles" id="p-tiles" aria-label="Summary"></section>
  <section class="tape" aria-labelledby="tape-h">
    <h2 id="tape-h">Accomplishments</h2>
    <p class="hint" id="p-tape-note"></p>
    <div class="tape-head"><span>Stat</span><span class="r">Count</span><span class="r">Sabotage</span><span class="ph">Position percentile</span></div>
    <div id="p-tape"></div>
  </section>
  <section aria-labelledby="p-chart-title">
    <h2 id="p-chart-title">By week</h2>
    <div class="chart-box" id="p-chart"></div>
  </section>
  <section aria-labelledby="p-log-title">
    <h2 id="p-log-title">Game log</h2>
    <div id="p-log"></div>
  </section>
  <section aria-labelledby="splits-h">
    <h2 id="splits-h">Splits</h2>
    <div id="p-splits"></div>
  </section>
</div>
"""

COMPARE_BODY = """
<section class="phero">
  <div>
    <p class="eyebrow">Compare players</p>
    <h1>Battlefield</h1>
    <p class="pmeta">Up to four players, one season or whole careers, side by side.</p>
  </div>
</section>
<section class="picker" aria-label="Players">
  <ul class="cmp-chips" id="c-chips"></ul>
  <div class="hsearch cpick" id="c-pick" role="search">
    <label class="sr-only" for="q-cmp">Add a player</label>
    <input id="q-cmp" type="search" placeholder="Add a player" autocomplete="off" spellcheck="false"
      role="combobox" aria-expanded="false" aria-controls="q-cmp-list" aria-autocomplete="list">
    <ul id="q-cmp-list" role="listbox" class="results" hidden></ul>
  </div>
  <p class="hint" id="c-pick-hint"></p>
  <p class="hint" id="c-try">Or try <a href="compare.html?ids=00-0031503,00-0023682&amp;season=career">Jameis Winston vs Ryan Fitzpatrick, careers</a>. On the <a href="./">leaderboard</a>, the + next to any name adds that player here.</p>
</section>
<div id="c-body" hidden>
  <form class="controls" onsubmit="return false" aria-label="Range">
    <div class="ctl"><label for="c-season">Season</label><select id="c-season"></select></div>
    <div class="ctl" id="c-weeks"><label for="c-from">Weeks</label>
      <div class="pair"><select id="c-from"></select><span>to</span><label class="sr-only" for="c-to">To week</label><select id="c-to"></select>
        <button type="button" id="c-full" class="toggle" aria-pressed="true">Full season</button></div></div>
    <fieldset class="ctl seg"><legend>Show</legend><div class="segbtns">
      <button type="button" data-cview="tot" aria-pressed="true">Totals</button>
      <button type="button" data-cview="pg" aria-pressed="false">Per game</button></div></fieldset>
  </form>
  <p class="notice" id="c-mixed" hidden>These players play different positions, and each position scores different events. Compare the rows that apply to both before reading much into the totals.</p>
  <p class="hint" id="c-scope"></p>
  <section aria-labelledby="c-table-h">
    <h2 id="c-table-h">Side by side</h2>
    <div id="c-table"></div>
  </section>
  <section aria-labelledby="c-chart-title">
    <h2 id="c-chart-title">By week</h2>
    <div class="chart-box" id="c-chart"></div>
  </section>
  <section aria-labelledby="c-break-h">
    <h2 id="c-break-h">Where the points come from</h2>
    <div id="c-break"></div>
  </section>
</div>
"""

MATCHUPS_BODY = """
<section class="hero">
  <picture class="hero-art"><source srcset="assets/whoopsie-240.webp 240w, assets/whoopsie.webp 480w" sizes="(max-width: 720px) 120px, 168px" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267" fetchpriority="low"></picture>
  <div>
    <p class="eyebrow">Projections, <span id="m-week">this week</span></p>
    <h1>The <span class="hl">Matchups</span></h1>
    <p class="lede">Who is set up to sabotage this week, if they play. Every projection comes with a likely range, because this league runs on things going wrong. <a href="method.html#projections">How projections work</a> · <a href="improvements.html">How they did last week</a>.</p>
  </div>
</section>
<section aria-labelledby="m-top-h">
  <h2 id="m-top-h">Top projections</h2>
  <div class="segbtns mtabs" id="m-tabs" role="group" aria-label="Position"></div>
  <div id="m-top"><p class="loading">Loading&hellip;</p></div>
</section>
<section aria-labelledby="m-games-h">
  <h2 id="m-games-h">Every game</h2>
  <div class="ggrid" id="m-games"></div>
</section>
<p class="hint">Forecasts from <a href="https://open-meteo.com/">Open-Meteo.com</a> (<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>). Expected scores come from the betting spread and total and are shown as game context only.</p>
"""

DEPTH_BODY = """
<section class="phero">
  <div>
    <p class="eyebrow">Depth charts, <span id="d-week">this week</span></p>
    <h1>Depth Charts</h1>
    <p class="pmeta">Who starts at quarterback, running back, receiver, tight end and kicker, with today's injury designations. Anyone ruled out is crossed off and the next man up is marked as starting. The <a href="matchups.html">Matchups</a> page projects the same starters.</p>
  </div>
  <div class="ctl"><label for="d-team">Team</label><select id="d-team"></select></div>
</section>
<div id="d-body"><p class="loading">Loading&hellip;</p></div>
<section aria-labelledby="d-changes-h">
  <h2 id="d-changes-h">Changes in the last week</h2>
  <p class="hint">Moves among the starters compared with the chart from seven days earlier, plus anyone starting in place of an injured teammate.</p>
  <div id="d-changes"></div>
</section>
<p class="hint">Depth charts and injury reports from <a href="https://github.com/nflverse">nflverse</a>, refreshed through the day. Questionable, Doubtful and Out come from the team's final injury report of the week, usually posted two days before the game. Earlier in the week a player can show Did not practice or Limited practice. IR, PUP, NFI (non-football injury) and Suspended come from the league's roster lists. A designation from last week is labeled with its week until the new report is out. Doubtful players are counted as not playing.</p>
"""

IMPROVE_BODY = """
<section class="phero">
  <div>
    <p class="eyebrow">Projection review</p>
    <h1>Room for Improvement</h1>
    <p class="pmeta">Every week, our five biggest projection misses, what drove them, and what we plan to test next. <a href="method.html#projections">How projections work</a>.</p>
  </div>
  <div class="ctl"><label for="i-week">Week</label><select id="i-week"></select></div>
</section>
<div id="i-week-body"><p class="loading">Loading&hellip;</p></div>
<section aria-labelledby="i-tally-h">
  <h2 id="i-tally-h">What keeps causing misses</h2>
  <p class="hint">Every reviewed week so far. Some of each miss is plain randomness. Fumbles and interceptions especially do not repeat, so projections will never be perfect. The goal is to shrink the part we can explain.</p>
  <div id="i-tally"></div>
</section>
"""

VIDEO_BODY = """
<section class="hero">
  <picture class="hero-art"><source srcset="assets/whoopsie-240.webp 240w, assets/whoopsie.webp 480w" sizes="(max-width: 720px) 120px, 168px" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267" fetchpriority="low"></picture>
  <div>
    <p class="eyebrow">Worst plays of the week</p>
    <h1>Reel Good <span class="hl">Sabotage</span></h1>
    <p class="lede">The week's worst plays on video, next to the players who scored the most Sabotage points.</p>
    <div class="ctl inline" id="v-pick"><label for="v-week">Week</label><select id="v-week"></select></div>
  </div>
</section>
<div class="vlayout">
  <section id="v-main" aria-live="polite"><p class="loading">Loading&hellip;</p></section>
  <aside class="topcard" id="v-culprits" aria-label="Top five that week"></aside>
</div>
<section aria-labelledby="v-more-h">
  <h2 id="v-more-h" hidden>Earlier weeks</h2>
  <div class="vgrid" id="v-more"></div>
</section>
<p class="hint">Videos are hosted on YouTube and made by their channels, not by Stars of Sabotage.</p>
"""

DEFENSES_BODY = """
<section class="hero">
  <picture class="hero-art"><source srcset="assets/whoopsie-240.webp 240w, assets/whoopsie.webp 480w" sizes="(max-width: 720px) 120px, 168px" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267" fetchpriority="low"></picture>
  <div>
    <p class="eyebrow">Points allowed, Yahoo rule</p>
    <h1>The <span class="hl">Defenses</span></h1>
    <p class="lede">Every team defense, ranked by Sabotage points from points allowed. <a href="method.html">How points allowed is counted</a>.</p>
    <div class="ctl inline"><label for="d-season">Season</label><select id="d-season"></select></div>
  </div>
</section>
<section class="topcard" aria-labelledby="d-top-title">
  <p class="label">Top five</p>
  <h2 id="d-top-title">Most generous defenses</h2>
  <ol class="top5" id="d-top"></ol>
</section>
<section aria-labelledby="d-table-h">
  <h2 id="d-table-h">Season table</h2>
  <p class="hint">Bucket columns count games in each points-allowed range. Click a header to sort.</p>
  <div id="d-table"></div>
</section>
<section aria-labelledby="d-grid-h">
  <h2 id="d-grid-h">Week by week</h2>
  <p class="hint">Points allowed each week. Darker cells earned more Sabotage points (up to 42 for 35 or more allowed).</p>
  <div id="d-grid"></div>
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
                              defense=defense, lost=lost, six=six, projections=projections_section())


POS_NAMES = {"QB": "Quarterbacks", "RB": "Running backs", "WR": "Wide receivers", "TE": "Tight ends",
             "K": "Kickers", "DEF": "Defenses"}


def projections_section() -> str:
    """How projections work, with the backtest table from config/backtest.json."""
    import json
    p = ROOT / "config" / "backtest.json"
    if not p.exists():
        return ""
    bt = json.loads(p.read_text())
    rows = []
    for grp in ("players", "defenses"):
        for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
            v = bt[grp].get(pos)
            if not v:
                continue
            m, b, l4 = v["proj"], v["b_std"], v.get("b_last4")
            rng = f'{round(v["range_hit"] * 100)}%' if "range_hit" in v else ""
            rows.append(f"<tr><td>{POS_NAMES[pos]}</td><td class=\"num\">{m['mae']:.2f}</td><td class=\"num\">{b['mae']:.2f}</td>"
                        f"<td class=\"num\">{'' if not l4 else format(l4['mae'], '.2f')}</td>"
                        f"<td class=\"num\">{m['spearman']:.2f}</td><td class=\"num\">{b['spearman']:.2f}</td><td class=\"num\">{rng}</td></tr>")
    s = bt["seasons"]
    return f"""
<h2 id="projections">How projections work</h2>
<p>Sabotage points are a sum of events, so we project the events and multiply by their point values. For each player we estimate incompletions, sacks, carries, catches, fumbles, lost fumbles, interceptions and pick sixes from his recent games, weighting the latest games most and pulling small samples toward the average for his position. Then we adjust for the game and his role: the betting spread and total (a team expected to trail throws more), what the opponent's defense has allowed, home or away, roof, the wind forecast, and his share of offensive snaps over his last three games. We also tested the injury report (Questionable, limited practice); it did not improve the projections once snap share was in, so it is not used.</p>
<p>Defenses get a range of likely points allowed, centered on the opponent's expected score from the spread and total, and we average the Sabotage points across that range.</p>
<p>Kickers get their season average. A model built on kick distance, wind and the kicker's track record did worse than the plain average in testing, because missed kicks barely repeat from one week to the next.</p>
<p>Every projection assumes the player plays. Players listed out, doubtful, or on injured reserve are left off. The likely range runs from the 10th to the 90th percentile of what happened to players with similar projections. Betting lines are used only as game context. This site does not give betting advice.</p>
<h3>How well it worked</h3>
<p>We replayed every regular-season week from {s[0]} to {s[-1]}. Each week's projections used only games played before that week, then we compared them with what happened. Average miss is the typical gap between projection and result, in Sabotage points (lower is better). Rank match measures how well the projected order of players matched the real order, from 0 (random) to 1 (perfect).</p>
<div class="table-wrap plain"><table><thead><tr><th>Position</th><th class="num">Average miss, ours</th><th class="num">Season average</th><th class="num">Last 4 games</th><th class="num">Rank match, ours</th><th class="num">Season average</th><th class="num">Results inside range</th></tr></thead><tbody>
{"".join(rows)}
</tbody></table></div>
<p>The spread and total in the test are the lines nflverse records for each game. Live projections use the current lines, which can move before kickoff.</p>
<p>Each week we review the five biggest misses on the <a href="improvements.html">projection review page</a>, with what drove them and what we plan to test.</p>
<p>Forecasts come from <a href="https://open-meteo.com/">Open-Meteo.com</a>, licensed under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
"""


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
<p>Targets (passes thrown his way) are shown in the Stats view and game logs but score nothing. They show how often a team tries to get a player the ball. nflverse has no target counts for 2003 to 2008, so those seasons show a blank.</p>
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

{projections}
<h2>Rule versions</h2>
<p>Every score on this site records the rule version that produced it. If the league changes its rules, past seasons are rescored under a new version, and the old version stays on record.</p>
<p>The archive goes back to 1999, the first season nflverse has play-by-play for. Every past season is scored under the current rules, including Yahoo's points-allowed rule, so a 2005 score means what it would mean today. Seasons before 2021 had 16 games, so compare per-game numbers across eras.</p>
</article>
"""


def _q(**kw) -> str:
    from urllib.parse import urlencode
    return "./?" + urlencode({k: v for k, v in kw.items() if v not in (None, "")})


def _holder_line(h: dict, scope: str, is_def: bool) -> str:
    when = f"{h['season']} Week {h['week']}" if scope == "game" else f"{h['season']} season"
    vs = f" vs {escape(h['opp'])}" if scope == "game" and h.get("opp") else ""
    team = "" if is_def else f" <span class=\"tm\">{escape(h['team'])}</span>"
    if scope == "game":
        link = _q(season=h["season"], **{"from": h["week"], "to": h["week"]}, pos="DEF" if is_def else None,
                  q=h["team"].lower() if is_def else h["name"])
    else:
        link = _q(season=h["season"], pos="DEF" if is_def else None, q=h["team"].lower() if is_def else h["name"])
    live = ' <span class="badge in_progress">Active season</span>' if h.get("current") else ""
    return f'<a href="{escape(link)}">{escape(h["name"])}</a>{team} <span class="when">{when}{vs}</span>{live}'


def supers_body(rec: dict) -> str:
    first, last = rec["first_season"], rec["last_season"]
    parts = [f"""
<section class="hero">
  <picture class="hero-art"><source srcset="assets/whoopsie-240.webp 240w, assets/whoopsie.webp 480w" sizes="(max-width: 720px) 120px, 168px" type="image/webp"><img src="assets/whoopsie-sm.png" alt="Sketch of a wide-eyed kid in a yellow beanie, mouth open in an O" width="240" height="267" fetchpriority="low"></picture>
  <div>
    <p class="eyebrow">Hall of shame, {first} to {last}</p>
    <h1>Super <span class="hl">Stars</span></h1>
    <p class="lede">The worst single game and the worst single season since {first} for every stat Sabotage scores. Every number is real. The commentary is ours.</p>
    <p class="weekline"><span>Seasons before 2021 had 16 games, so some season records had one fewer game to work with. Records update as the current season plays.</span></p>
  </div>
</section>"""]
    group_order = list(rec["groups"])
    for g in group_order:
        stats = [s for s in rec["stats"] if s["group"] == g]
        if not stats:
            continue
        parts.append(f'<section class="rec-group" aria-labelledby="g-{g.replace(" ", "-")}">'
                     f'<h2 id="g-{g.replace(" ", "-")}">{escape(rec["groups"][g])}</h2>')
        for s in stats:
            is_def = s["stat"] == "points_allowed"
            parts.append(f'<div class="rec-row"><h3 class="rec-stat">{escape(s["label"])}'
                         f'{f" <small>{s["per"]} Sabotage pts each</small>" if s["per"] else ""}</h3><div class="rec-cards">')
            for r in s["records"]:
                h0 = r["holders"][0]
                tied = ""
                if r["tied"] > 1:
                    others = "; ".join(_holder_line(h, r["scope"], is_def) for h in r["holders"][1:])
                    more = r["tied"] - len(r["holders"])
                    tied = (f'<p class="tied">Shared with {others}'
                            f'{f" and {more} more" if more > 0 else ""}.</p>')
                worth = (f'<span class="worth">{r["sabotage_pts"]:,} Sabotage pts</span>'
                         if r["sabotage_pts"] is not None and s["stat"] != "sabotage_pts" else "")
                notes = "".join(f'<p class="note">{escape(h["note"])}</p>' for h in r["holders"] if h.get("note"))
                label = "Single game" if r["scope"] == "game" else "Single season"
                al = r.get("alert")
                badge = (f'<span class="badge {"final" if al["official"] else "provisional"}">{escape(al["title"])}</span>'
                         if al else "")
                # While a record is pending, the alert text replaces the story (it carries the same
                # facts plus the correction deadline). Once official, the regular story returns.
                pending = al and not al["official"]
                body = (f'<p class="alert-note">{escape(al["text"])}</p>' if pending
                        else f'<p class="text">{escape(r["text"])}</p>')
                parts.append(f"""<article class="story rec{" alert" if al else ""}{" official" if al and al["official"] else ""}">
  <p class="label">{label} {badge}</p>
  <p class="big"><span class="num">{r["value"]:,}</span> <span class="unit">{escape(r["unit"])}</span>{worth}</p>
  <p class="holder">{_holder_line(h0, r["scope"], is_def)}</p>
  {body}
  {tied}{notes}
</article>""")
            parts.append("</div></div>")
        parts.append("</section>")
    parts.append('<p class="hint">Records use nflverse play-by-play, which can differ from an official box score by a play in rare cases. Known differences are noted on the record. Defensive points allowed follow the Yahoo rule on the <a href="method.html">scoring page</a>.</p>')
    return "\n".join(parts)


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


def _boot_tags(boot: dict | None) -> tuple[str, str]:
    """Inline meta + season list, and preload the current season's data so the
    browser fetches it in parallel with the script instead of after it."""
    if not boot:
        return "", ""
    import json
    m = boot["meta"]
    payload = json.dumps(boot, separators=(",", ":")).replace("</", "<\\/")
    pre = "".join(f'<link rel="preload" href="data/{n}-{m["season"]}.json?v={m["data_hash"]}" as="fetch" crossorigin>\n'
                  for n in ("scores", "defense"))
    return pre, f'<script id="boot" type="application/json">{payload}</script>\n'


def build(out: Path, noindex: bool = True, records: dict | None = None, boot: dict | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SITE / "assets", out / "assets", dirs_exist_ok=True)
    shutil.copy2(SITE / "favicon.ico", out / "favicon.ico")
    (out / ".htaccess").write_text(HTACCESS)
    # Version tags: a new release can never pair new HTML with an old cached script.
    # Leaf modules first, then modules that import them get rewritten and hashed.
    a = out / "assets"
    v = {"css": _hash(a / "styles.css")}
    # In dependency order: each module's imports are already hashed when it is rewritten.
    for mod in ("foot", "common", "stats", "avail", "app", "player", "defenses", "compare", "videos", "matchups",
                "improvements", "depth"):
        src = (a / f"{mod}.js").read_text()
        for dep in [d for d in v if d != "css"]:
            src = src.replace(f'from "./{dep}.js"', f'from "./{dep}.js?v={v[dep]}"')
        (a / f"{mod}.js").write_text(src)
        v[mod] = _hash(a / f"{mod}.js")

    def tag(html: str) -> str:
        html = html.replace('href="assets/styles.css"', f'href="assets/styles.css?v={v["css"]}"')
        for mod in ("foot", "common", "app", "player", "defenses", "compare", "videos", "matchups", "improvements", "depth"):
            html = html.replace(f'src="assets/{mod}.js"', f'src="assets/{mod}.js?v={v[mod]}"')
        return html
    import json
    version = escape(load_config()["version"])
    if boot is None:
        mp, sp = out / "data" / "meta.json", out / "data" / "seasons.json"
        if mp.exists() and sp.exists():
            boot = {"meta": json.loads(mp.read_text()), "seasons": json.loads(sp.read_text())}
    dv = (boot or {}).get("meta", {}).get("data_hash", "")
    pre, boot_tag = _boot_tags(boot)
    page = lambda title, body, key, script: tag(layout(
        title, body, page=key, noindex=noindex, dv=dv,
        scripts=f'<script type="module" src="assets/{script}.js"></script>' if script else ""))

    home = page("Stars of Sabotage | Sabotage fantasy football leaderboard",
                BOARD_BODY.replace("{version}", version).replace("__BIG_SEARCH__", BIG_SEARCH), "board", "app")
    home = home.replace("</script>\n<script type=\"module\" src=\"assets/app.js", "</script>\n" + boot_tag
                        + "<script type=\"module\" src=\"assets/app.js", 1)
    home = home.replace('<link rel="stylesheet"', pre + f'<link rel="modulepreload" href="assets/foot.js?v={v["foot"]}">\n'
                        + '<link rel="stylesheet"', 1)
    (out / "index.html").write_text(home)
    if records is None:
        rp = out / "data" / "records.json"
        records = json.loads(rp.read_text()) if rp.exists() else None
    if records:
        (out / "super-stars.html").write_text(page("Super Stars | Stars of Sabotage", supers_body(records), "supers", "foot"))
    (out / "method.html").write_text(page("How Sabotage scoring works | Stars of Sabotage", method_body(), "method", "foot"))
    (out / "player.html").write_text(page("Player | Stars of Sabotage", PLAYER_BODY, "player", "player"))
    (out / "defenses.html").write_text(page("Defenses | Stars of Sabotage", DEFENSES_BODY, "defenses", "defenses"))
    (out / "compare.html").write_text(page("Compare players | Stars of Sabotage", COMPARE_BODY, "compare", "compare"))
    (out / "matchups.html").write_text(page("Matchups and projections | Stars of Sabotage", MATCHUPS_BODY, "matchups", "matchups"))
    (out / "improvements.html").write_text(page("Projection review | Stars of Sabotage", IMPROVE_BODY, "matchups", "improvements"))
    (out / "depth.html").write_text(page("Depth charts | Stars of Sabotage", DEPTH_BODY, "depth", "depth"))
    (out / "video.html").write_text(page("Reel Good Sabotage | Stars of Sabotage", VIDEO_BODY, "video", "videos"))


if __name__ == "__main__":
    import sys
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "dist"))
