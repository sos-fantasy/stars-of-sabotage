# Stars of Sabotage Stats Site: Project Brief

Version 0.2, October 15, 2026 (Phase 0 updates to sections 4.1 and 7; see phase0-findings.md). Add this file to a Claude project as project knowledge. Anything marked UNVERIFIED could not be confirmed when this was written and has a task in Phase 0.

## 0. Working agreements

- Accuracy matters more than speed. Verify a fact before stating it. Cite the source, and say so plainly when something is unconfirmed.
- Offer options with a recommendation. The owner picks the path.
- Lead with specifics (numbers, field names, file names), not overviews.
- Site copy and documentation avoid common AI writing patterns: no "it's not X, it's Y" contrasts, no inflated words (testament, pivotal, tapestry, legacy), no editorializing ("worth noting"), no filler transitions (moreover, furthermore), no trailing "-ing" analysis phrases, no em dashes, no bold-titled bullet points, no filler intros. Vary sentence length.
- Every change that touches scoring needs a test with a hand-computed example.

## 1. Mission

Build a public website that ranks NFL players and team defenses under the Sabotage League scoring system. In this system, points reward bad plays (fumbles, missed kicks, interceptions, sacks taken) plus a few volume stats. Anyone who wants to play this format can see who scores best, week by week and across a season, and can see context stats that help predict who scores next.

Audience: people considering or playing a Sabotage-style league, plus the league's own members.

Site domain: starsofsabotage.com, hosted on Hostinger. A coming-soon page is already live or about to be.

## 2. Decisions already made

1. Data comes from nflverse. It does not come from the Yahoo Fantasy API. The Yahoo agreement offered to the owner limits use to personal analysis of the owner's own leagues, bars displaying data to third parties, and bars storing or caching it, so Yahoo data must not appear anywhere in this project. Do not call Yahoo's API or scrape Yahoo pages. The owner may compare our computed scores to his league's Yahoo screens by eye and report differences in chat. Do not commit Yahoo-sourced numbers to the repo.
2. The site is free to run. No paid data sources in v1. No ads and no subscriptions (see the weather terms in section 11).
3. Static architecture: an automated pipeline builds JSON files, and the website is static HTML and JavaScript that reads them. Hostinger only serves files, so no server runtime is assumed.
4. Original design. NFL Savant (nflsavant.com) is a functional reference: leaderboards, comparisons, trends, sortable tables. Do not copy its layout, code, or branding. The owner will supply screenshots of the screens to mirror.
5. Scoring rules are data, not code. They live in a versioned config file so rule changes never require rewriting logic.

## 3. Scoring system

### 3.1 Rules as the league plays them

Everything not listed is worth zero. Points are positive. A higher total means more sabotage.

| Group | Event | Points |
|---|---|---|
| Offense | Incomplete pass | 2 |
| Offense | Sack taken | 5 |
| Offense | Rushing attempt | 1 |
| Offense | Reception | 2 |
| Offense | Fumble | 7 |
| Offense | Fumble lost | 10 |
| Offense | Pick six thrown | 21 |
| Offense | Interception thrown | 10 |
| Kicker | FG missed 0-19 yards | 21 |
| Kicker | FG missed 20-29 | 18 |
| Kicker | FG missed 30-39 | 16 |
| Kicker | FG missed 40-49 | 14 |
| Kicker | FG missed 50+ | 12 |
| Kicker | PAT missed | 16 |
| Defense | Points allowed 1-6 | 7 |
| Defense | Points allowed 7-13 | 14 |
| Defense | Points allowed 14-20 | 21 |
| Defense | Points allowed 21-27 | 28 |
| Defense | Points allowed 28-34 | 35 |
| Defense | Points allowed 35+ | 42 |

### 3.2 Config file (`config/scoring.yml`)

```yaml
version: "2026.1"
first_season: 2026
offense:
  incomplete_pass: 2
  sack_taken: 5
  rush_attempt: 1
  reception: 2
  fumble: 7
  fumble_lost: 10
  pick_six_thrown: 21
  interception_thrown: 10
kicker:
  fg_missed:
    "0-19": 21
    "20-29": 18
    "30-39": 16
    "40-49": 14
    "50+": 12
  pat_missed: 16
defense:
  points_allowed:
    "0": 0        # owner ruling: a shutout is not sabotage
    "1-6": 7
    "7-13": 14
    "14-20": 21
    "21-27": 28
    "28-34": 35
    "35+": 42
```

Every scored row stores the `scoring_version` that produced it. If the league changes rules, add a new version and rescore. Never edit a past version in place.

### 3.3 Interpretation rulings (owner answers, October 14, 2026)

1. Stacking: yes. A lost fumble scores 7 + 10 = 17. A pick six scores 10 + 21 = 31.
2. Points allowed follows Yahoo's rule (owner decision, October 15, 2026; help.yahoo.com/kb/SLN6441.html). Excluded from the opponent's score: interception and fumble return TDs on scrimmage plays, blocked FG return TDs, all safeties, defensive two-point returns. Still counted: kick and punt return TDs and every PAT. Verified on all 5 ARI weeks in the owner's Yahoo screens. The method page (`site/method.html`, built from the config by `pipeline/build_method.py`) explains it with the ARI wk 4 example. ESPN, CBS, and Sleeper use close variants; their help pages differ only on safeties, which ESPN and Sleeper do not address.
3. Blocked field goals and blocked PATs count as misses, bucketed by the attempt's distance.
4. Fumbles count for offensive players only (QB, RB, WR, TE; FB treated as RB). Defensive players' fumbles do not count. Counted from play-by-play, so aborted and dropped snaps by a QB count (nflverse's sack, rushing, and receiving fumble columns leave these out). Kick and punt return fumbles by an offensive player count (confirmed: Turpin wk 5 = 21 in Yahoo).
5. FG distance is the kick distance: spot of the hold to the goalposts, the number in the official play text ("54 yard field goal"). nflverse buckets are 0-19, 20-29, 30-39, 40-49, 50-59, 60+. The league's 50+ bucket combines the last two.
6. Any offensive player's rushing attempt counts. nflverse includes QB kneel-downs as carries.
7. Sacks are sacks taken by the QB. nflverse counts QB spikes as incomplete passes.

A shutout (0 points allowed) scores 0 (owner ruling, October 15, 2026).

### 3.4 Validation procedure

1. Compute Sabotage points for a sample of 5 to 10 players and 3 defenses across weeks already played this season.
2. The owner compares them to his league's Yahoo totals by eye.
3. Any mismatch gets traced to one of the questions above. Update the config or logic. Repeat until every sampled number matches.
4. Save the final hand-computed examples as unit test fixtures built from public box scores, not from Yahoo.

## 4. Data sources

All nflverse data loads through `nflreadpy` (the nflverse Python package) or directly from the nflverse-data GitHub releases. Cadence below comes from the nflverse schedule page (nflreadr.nflverse.com/articles/nflverse_data_schedule.html).

| Dataset | Loader | Update cadence | Use here |
|---|---|---|---|
| Weekly player stats | `load_player_stats` | Nightly after each game day, plus extra runs at set points on game days. No faster option exists. | Core scoring stats |
| Play-by-play | `load_pbp` | Same as above. Raw play-by-play JSON appears roughly 15 minutes after a game ends and can be parsed with nflfastR's `build_nflfastR_pbp`. | Pick sixes, field goal distance checks |
| Schedules and results | `load_schedules` | Every 5 minutes in season | Scores (points allowed), roof, surface, recorded temp and wind, betting lines (UNVERIFIED which columns exist) |
| Rosters | `load_rosters` | Daily, 7 AM UTC | Player identity, team |
| Depth charts | `load_depth_charts` | Daily, 7 AM UTC. From 2025 on, entries carry timestamps and are not assigned to a week. | Role and availability features |
| Injuries | `load_injuries` | Daily, 7 AM UTC | Availability features |
| Snap counts | `load_snap_counts` | 0, 6, 12, 18 UTC, depends on Pro Football Reference | Snap share |
| FTN charting | `load_ftn_charting` | 0, 6, 12, 18 UTC, depends on FTN | Optional extra features |
| Participation | `load_participation` | 2023 onward arrives only after the postseason ends | Do not use for in-season features |
| Weather forecast | Open-Meteo API | Each pipeline run | Forecast for upcoming outdoor games |
| Videos | YouTube channel RSS | Each pipeline run | Video section |

Corrections: the NFL folds stat corrections in from Monday through Wednesday. nflverse recommends one more refresh Wednesday night into Thursday and calls Thursday's data the cleanest. A week is "provisional" until that refresh and "final" after it.

### 4.1 Field mapping (VERIFIED October 15, 2026)

Checked against nflreadpy 0.1.5 with 2026 data (player stats: 5,506 rows, 150 columns; schedules: 272 rows, 46 columns; play-by-play: 13,842 rows, 372 columns). Every expected column exists.

| Scoring event | Source |
|---|---|
| Incomplete pass | `attempts` minus `completions` |
| Sack taken | `sacks_suffered` |
| Rush attempt | `carries` |
| Reception | `receptions` |
| Fumble | play-by-play: `fumbled_1_player_id` and `fumbled_2_player_id` on `play_type` pass, run, qb_kneel, qb_spike where the fumbler's team (`fumbled_N_team`) equals `posteam`; positions QB, RB, FB, WR, TE only. Reconciles to `sack_fumbles` + `rushing_fumbles` + `receiving_fumbles` plus QB snap fumbles (167 vs 163 through week 5) |
| Fumble lost | play-by-play `fumble_lost` = 1, credited to the last fumbler on the first fumbler's team. Reconciles exactly to `sack_fumbles_lost` + `rushing_fumbles_lost` + `receiving_fumbles_lost` (78 through week 5) |
| Return fumbles (counted) | same, with `play_type` kickoff or punt |
| Interception thrown | `passing_interceptions` (109 through week 5, matches the play-by-play count) |
| Pick six thrown | play-by-play: `interception` = 1 and `return_touchdown` = 1, credited to `passer_player_id` (6 through week 5) |
| FG missed by distance | `fg_missed_0_19`, `fg_missed_20_29`, `fg_missed_30_39`, `fg_missed_40_49`, `fg_missed_50_59` plus `fg_missed_60_` for the 50+ bucket. The buckets sum to `fg_missed` on all 146 kicker rows |
| Blocked FG and PAT | Not in `fg_missed` or `pat_missed`. Separate columns `fg_blocked`, `pat_blocked`. For distance, use play-by-play `kick_distance` where `field_goal_result` = "blocked", kicker in `kicker_player_id` |
| PAT missed | `pat_missed` |
| Points allowed, raw | schedules `home_score` / `away_score` |
| Points allowed, offense only | raw minus opponent's non-offensive points from play-by-play: TDs with `return_touchdown` = 1 or `td_team` != `posteam` (plus the try that follows), `safety` = 1 credited to `defteam`, `defensive_two_point_conv` = 1 |

Schedules also carry `spread_line`, `total_line`, moneylines, `roof`, `surface`, `temp`, `wind`, `stadium_id`, `stadium`, `away_rest`, `home_rest`, and `gametime`. Player stats include `targets`, `target_share`, and `headshot_url` (do not use headshots, see section 13).

## 5. Architecture

```
nflverse releases (GitHub)  -->  GitHub Actions (Python pipeline)
Open-Meteo forecasts        -->        |  scores, features, projections
YouTube RSS + manual list   -->        v
                                 dist/data/*.json
                                       |  deploy (SFTP/FTP)
                                       v
                          Hostinger public_html  -->  browser (static JS app)
```

### 5.1 Stack defaults (change if the owner disagrees)

- Pipeline: Python 3.11+, `nflreadpy`, pandas or polars, PyYAML, requests, feedparser. Runs on GitHub Actions.
- Front end: plain ES modules, no framework. The leaderboard table is hand-written (sorting, aria-sort, sticky header and first column) instead of Tabulator, to keep it small and fully accessible. Chart.js (MIT) remains the plan for charts in Phase 2. Fonts are self-hosted: Anton and JetBrains Mono (both OFL-1.1). No CDN dependencies.
- Data: JSON files partitioned by season, loaded on demand. Measure real file sizes in Phase 1 before deciding whether to also gzip, split further, or move to SQLite or MySQL.

### 5.2 Deploy options (decide in Phase 0)

A. GitHub Actions uploads `dist/` to Hostinger over SFTP or FTP using credentials stored as GitHub secrets. Works with the existing PHP/HTML site type. Recommended default.
B. Hostinger's own GitHub-connected deploy for static apps. The pipeline commits data files to the repo and Hostinger redeploys. It may require converting the site type in Hostinger.
C. MySQL on Hostinger. GitHub runner IP addresses change, so remote database writes are fragile. Use only if the JSON approach hits a real limit.

### 5.3 Repo layout

```
config/scoring.yml
config/stadiums.csv          # stadium_id, name, lat, lon, roof (seeded and checked by hand)
config/video_sources.yml     # channel id, title match pattern
pipeline/                    # fetch, score, features, project, export
tests/                       # scoring fixtures, schema checks
site/                        # static front end
dist/data/                   # generated JSON (gitignored or on a data branch)
.github/workflows/           # scheduled pipeline + deploy
```

## 6. Data model (JSON files)

Primary key for offensive and kicking players is the nflverse `player_id` (GSIS id). Defenses use the team abbreviation. Store the team and opponent on every weekly row, because players change teams.

| File | Contents |
|---|---|
| `meta.json` | last run time, latest completed week, per-week status (provisional or final), scoring version, data source timestamps |
| `players.json` | id, name, position, current team |
| `scores/{season}.json` | one row per player-week: team, opponent, raw event counts, points per scoring component, total Sabotage points, status |
| `defense/{season}.json` | one row per team-week: points allowed, bucket, points, opponent context |
| `games/{season}.json` | schedule, results, roof, surface, recorded temp and wind, lines, forecast fields, kickoff time |
| `projections/{season}-w{week}.json` | per player: projected total, component projections, range, top drivers |
| `videos.json` | season, week, YouTube id, title, publish date, embeddable flag, source (auto or manual) |

A bye week or inactive week produces no row. Show a blank, not a zero. Per-game averages divide by weeks with a row (open question 6 in section 15).

## 7. Pipeline schedule

GitHub Actions cron runs in UTC and ignores daylight saving. Run the workflow hourly and let the script decide, using America/New_York time, whether work is due:

- Game days (Thursday, Sunday, Monday, plus holiday games read from the schedule): refresh scores about every 2 hours from early afternoon until after the last game ends. Week status stays provisional.
- Daily, early morning ET: refresh schedules, rosters, depth charts, injuries, weather, videos, and projections for the upcoming week.
- Wednesday night and Thursday morning ET: correction refresh. After the Thursday refresh, mark the week final.
- Offseason: weekly refresh only.

Requirements:
- Idempotent. A rerun never duplicates rows.
- A failed source (for example YouTube RSS) must not block the rest. Log it, keep the last good file, and record the failure in `meta.json`.
- Failure alert: GitHub's failed-run email at minimum.
- GitHub docs (checked October 15, 2026): in a public repository, scheduled workflows are disabled automatically after 60 days with no repository activity. The docs do not say the same for private repos. Have the pipeline commit a small heartbeat file, or keep the repo private.

## 8. Site specification

### 8.1 Global

- Every number on the site is framed in Sabotage points. Raw stats appear as drivers of those points.
- Footer on every page: data attribution (section 13) and the "last updated" time with week status. Weeks that are not yet final show a "provisional until Thursday" badge.
- Views are shareable: season, week, filters, and sort live in the URL query string.
- Responsive. Tables scroll horizontally with a sticky header and sticky first column on phones.
- Accessible: keyboard-operable sort headers with `aria-sort`, readable contrast, no color-only meaning.
- Neutral team treatment: team abbreviations in text. No NFL logos, wordmarks, or player headshots in v1.

### 8.2 Pages

1. Leaderboard (home). Player table with selectors for season, week or week range, position, team, and "total / per game". Default sort: total Sabotage points, high to low.
2. Player page. Weekly log, stacked component chart (which events produced the points), rolling average, splits (dome vs outdoor, wind buckets, home vs away), and the upcoming matchup with projection.
3. Compare. Pick 2 to 4 players. Side-by-side table, overlaid weekly chart, and shared-axis component breakdown.
4. Defenses. Team table scored on the points-allowed buckets, with a week-by-week view.
5. Matchups and projections. This week's games with kickoff time, roof, forecast, spread and total (if the schedule data carries them), and the top projected Sabotage scorers by position.
6. Video. Section 10.
7. Scoring and method. The rules table, the version history, data sources, how projections work, and honest accuracy notes.

### 8.3 Table behavior (applies to every table)

- Click a column header to sort high to low, click again for low to high, click a third time to return to the default. Shift-click adds a secondary sort.
- Numeric columns right-aligned. Text columns left-aligned. Rank column reflects the current sort.
- Column picker with sensible defaults (total, per game, then the components). Column groups: Total, Components, Context (targets, carries, snap share), Projection.
- Filters: position, team, minimum games, text filter.
- CSV download of the current view.
- Tie-break on sort: total points, then name.

### 8.4 Search

- A search box in the header on every page. Type-ahead over players and teams, matches on partial names, handles apostrophes and suffixes (Jr., III), shows position and team in each result.
- Client-side index built from `players.json`. Fuse.js is an acceptable choice.

### 8.5 Player comparison

- Entry points: the compare page, plus a "compare" action on any player row.
- Up to 4 players. Mixed positions allowed, with a notice that positions score different events.
- Season and week range selectors shared across the selected players.
- Shareable URL.

## 9. Insights and projections

### 9.1 Approach

Scoring is a weighted sum of event counts, so model the counts and multiply by the point values. This keeps projections explainable ("12 projected carries, 5 projected receptions, 0.3 expected fumbles lost") and lets a scoring change reuse the same model with new weights.

- Volume events (carries, receptions, incompletions, sacks taken) are the predictable part. Rate them from rolling per-game or per-opportunity history, shrunk toward the position average when samples are small.
- Rare events (fumbles, interceptions, pick sixes, missed kicks) are noisy. Use shrunken rates, expect wide ranges, and say so in the interface.
- Kickers: expected attempts by distance bucket times miss probability by bucket, adjusted for roof and wind.
- Defenses: use opponent implied points (from the total and spread, if the data carries them) to estimate a probability for each points-allowed bucket, then take the expected points.

### 9.2 Context features

Targets and target share, carry share, snap share, depth chart role, injury status, team pace and pass rate, opponent sack rate and takeaway rate, spread and total, home or away, rest days, roof and surface, forecast temperature, wind, and precipitation.

### 9.3 Evaluation

- Walk-forward backtest: train only on data available before each week, predict that week, and compare.
- Metrics: mean absolute error and rank correlation (Spearman) by position.
- Baselines: season-to-date average and last-4-games average.
- Ship a model only if it beats the baselines on the backtest. Otherwise ship the baseline, label it as such, and keep improving.
- Publish the backtest results on the method page.

### 9.4 Interface rules

- Label as "projection," show a range, and list the top drivers.
- No betting framing. Any betting-line inputs are used only as game-context features, and the site makes no wagering recommendations.

### 9.5 Backfill

nflverse holds years of history, so past seasons can be rescored under the current rules. That gives the model a training base. Default backfill start: 2020 (owner to confirm, see section 15). Label historical views "scored under current rules" because the league's rules were different in earlier seasons.

## 10. Video section

- Layout: grouped by week, newest week first, with a week selector. Each week shows the NFL Rush "NFL Worst Plays of the Week" video.
- Automatic ingestion: read the channel's public RSS feed (`https://www.youtube.com/feeds/videos.xml?channel_id=<ID>`), match titles against the pattern in `config/video_sources.yml` (start with "Worst Plays", case-insensitive), and assign each video to an NFL week by comparing its publish date to the schedule (the week whose games finished most recently before the publish date).
- The feed lists only about the latest 15 uploads and has had reported outages, so the pipeline keeps previously ingested videos and never depends on the feed for history.
- Manual path (easy add and override): a Google Sheet published as CSV, or `config/videos_manual.csv`, with columns `season, week, youtube_url, title (optional)`. Manual rows win over auto rows.
- Embedding: use the privacy-enhanced embed domain (`youtube-nocookie.com`). Load a thumbnail first and swap in the iframe on click for page speed.
- Embeddability check (UNVERIFIED for this channel): some publishers disable embedding, and at least one football writer has stated that NFL highlights cannot be embedded on their site. The pipeline checks each video's embeddable flag (YouTube Data API `status.embeddable`, or an oEmbed request). When embedding is off, show a link card with the thumbnail that opens YouTube, with no broken player.
- Phase 0 tasks: confirm the channel's handle and ID, confirm the title pattern against the last few weeks of uploads, and test embedding on 3 real videos.

## 11. Weather

- Source: Open-Meteo forecast API. The free tier is for non-commercial use only (sites with ads or subscriptions count as commercial), allows under 10,000 calls per day, and requires CC-BY 4.0 attribution. A free, ad-free site fits. If ads or paid tiers are ever added, switch to a paid Open-Meteo plan or another source before launch. The US National Weather Service API is a possible free alternative for US venues (UNVERIFIED: confirm terms and the required request headers).
- Inputs: stadium coordinates from `config/stadiums.csv` (seed by hand, check every row, include international venues), kickoff time from the schedule, and the roof field.
- Outputs per outdoor game: temperature, wind speed and gusts, precipitation probability, and conditions for the kickoff hour. Domes and closed roofs show "Dome" with no forecast. Retractable roofs show "Roof status confirmed on game day" until known.
- Refresh forecasts daily and again within a few hours of kickoff.
- Historical weather for the model: use the temperature and wind recorded in the schedule data if present (UNVERIFIED). Avoid heavy bulk calls to Open-Meteo for history.

## 12. Quality and monitoring

- Unit tests for the scoring engine, using hand-computed examples (section 3.4).
- Schema checks on every pipeline run: required columns present, no negative counts, points equal the weighted sum of counts, week status valid.
- Reconciliation check: team-level sums of player events compare against team totals where the data allows.
- A "data health" line in `meta.json` and a small status area on the site.
- Pipeline failures email the owner. The site keeps serving the last good data.
- Performance goal: leaderboard usable within about 2 seconds on a mid-range phone. Measure in Phase 1 and report.

## 13. Legal, attribution, and IP

- nflverse data is published under CC-BY-4.0 and the nflreadr and nflfastR code under MIT. Credit nflverse in the footer and on the method page.
- Open-Meteo data requires CC-BY 4.0 attribution if used.
- OPEN RISK: nflverse builds its data from NFL.com feeds. Its license covers its own work. No source reviewed says whether the NFL's rights in the underlying data are cleared for a public site. Phase 0 task: read NFL.com's terms and nflverse's license and data notes, and report what they say. Do not treat the question as settled. Paid licensed alternatives exist (for example SportsDataIO's commercial license) if the answer is unfavorable.
- Footer disclaimer: not affiliated with or endorsed by the NFL, any team, or Yahoo. No NFL, team, or Yahoo logos or marks anywhere.
- No headshots or hotlinked images from NFL.com in v1.
- YouTube: embed only through the official embed player. Do not download or re-host video.
- Privacy: no accounts, no personal data collected. If analytics are added later, add a privacy notice first.

## 14. Build plan

Phase 0, validate (do first, small):
- Print real nflverse schemas and fix section 4.1.
- Settle the scoring questions in 3.3 using the validation procedure in 3.4.
- Choose the deploy path (5.2) and set up GitHub secrets.
- Resolve the NFL Rush channel ID, title pattern, and embedding test.
- Read the NFL.com and nflverse terms and report.
- Collect the owner's NFL Savant screenshots.
- Exit criteria: scoring matches the owner's league on the sample, and the open-risk items have written answers.

Phase 1, MVP:
- Scoring engine, config, tests, and backfill for the current season (plus the chosen history).
- Pipeline with provisional and final status, JSON export, and deploy to Hostinger.
- Leaderboard page with sortable columns, filters, URL state, and the footer attribution.
- Exit criteria: the live site shows correct current-season numbers, updates itself after a real game day, and survives one correction cycle (Thursday refresh).

Phase 2, depth:
- Player pages, search, compare, and the Defenses page.
- Exit criteria: every page works on desktop and phone, and a stranger can find a player and compare two players without instructions.

Phase 3, video:
- Auto ingestion, manual override sheet, embed check with fallback, and the Video page.
- Exit criteria: the latest worst-plays video appears for its week without manual work, and a manual add takes under a minute.

Phase 4, insights:
- Stadium table, weather forecasts, context features, count models, projections, backtest, and the Matchups page.
- Exit criteria: projections beat the baselines on the backtest, or the site ships baselines clearly labeled.

Phase 5, polish:
- Performance, accessibility pass, monitoring, method page, and optional pre-rendered player pages for search engines.

## 15. Open questions for the owner

1. How many past seasons to backfill (default 2020 onward)?
2. Which NFL Savant screens should we mirror? Send screenshots of 3 or 4.
3. Which of the scoring interpretations in 3.3 match the league?
4. Deploy path A, B, or C (5.2)?
5. Will the site ever carry ads or paid features? That changes the weather source and may change the data licensing answer.
6. Per-game averages: divide by weeks with a stat row (default), or by team games played?
7. Should a bye or inactive week appear as blank (default) or zero in charts?
8. Is a league-only section desirable later (members' standings)? It would need a separate, license-safe data source, so it is out of scope for v1.

## 16. References

- nflverse data schedule: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
- nflverse data repo: https://github.com/nflverse/nflverse-data
- nflreadr documentation: https://nflreadr.nflverse.com
- nflfastR: https://www.nflfastr.com
- nflreadpy (Python): https://nflreadpy.nflverse.com
- Open-Meteo terms: https://open-meteo.com/en/terms
- YouTube channel feed pattern: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
- NFL Savant (functional reference): https://nflsavant.com

## 17. First prompts to run in the project

1. "Start Phase 0. Print the real nflverse schemas for player stats, play-by-play, and schedules, and update the field mapping table in section 4.1."
2. "Build the scoring engine from config/scoring.yml and compute Sabotage points for weeks 1 through the latest completed week of 2026. Show me the top 10 players and top 5 defenses, plus the results under each interpretation in 3.3 so I can compare against my league."
3. "Read NFL.com's terms and nflverse's license and data notes, and summarize what they allow for a public, free, ad-free website. Quote the relevant lines (short quotes only) and tell me what you could not find."

## 18. Brand and voice (owner decisions, October 16, 2026)

Look: carried over from the coming-soon page. Near-black background (#15140f), cream text (#ece6d8), yellow accent (#f2b705), burnt-orange highlight bar (#b8421f). Headlines in Anton, uppercase. Body and tables in JetBrains Mono.

Mascot: the "Whoopsie" girl (sketch of a wide-eyed kid in a yellow beanie). Bust is the logo and hero art; the head-only version is the favicon and touch icon. Source files live in `site/assets/`.

Audience: fantasy football players, mostly men, smart, with a light schadenfreude sense of humor. Sabotage takes independent thinking, since mainstream fantasy advice assumes normal scoring.

Voice: stats pages stay plain and precise. Humor lives only in highlight stories (the weekly "wreckage report" and any future stat stories), written as a witty, free-spirited announcer with vivid metaphors. Rules for stories: every number comes from the data; jokes wrap facts, never replace them; no mocking injuries or anything off the field; no em dashes; refer to teams by nickname. Templates live in `pipeline/stories.py`, with tests enforcing style and placeholders.

Story timing: awards cover the latest week once at least half its games are final, otherwise the previous week.

## 19. Phase 1 status (October 16, 2026)

Live at starsofsabotage.com/preview/ (noindex while in preview). Hostinger deploys the `deploy` branch into `public_html/preview` on each push. GitHub Actions workflow `.github/workflows/update.yml` runs hourly at :07 UTC; `pipeline/schedule.py` decides in Eastern time whether to work (daily 6 and 10 AM; game days 4, 7, 10 PM; overnight 1 and 4 AM after game days; Wednesday 10 PM and Thursday 4 AM for corrections). It publishes only when output changed, and at least once a day via the `checked_on` date, which also keeps the public repo active. A week is final at 10 AM ET on the first Thursday after its last game.

To move off /preview: point the Hostinger deployment at `public_html`, and set `SOS_NOINDEX` to "0" in the workflow.

## 20. History backfill (October 16, 2026)

Seasons 1999 to 2026 are scored (28 seasons; nflverse play-by-play starts in 1999). Owner request. Spot-checked against the record book: Favre 2005, 29 INT; Winston 2019, 30 INT and 7 pick sixes; David Carr 2002, 76 sacks; Brady, 23 seasons and 335 games. Worst Sabotage season on record: Winston 2019, 1,367 points.

Data files per season: `data/scores-YYYY.json`, `data/defense-YYYY.json`. Index: `data/seasons.json`. Season totals for the All seasons view: `data/player-seasons.json`, `data/defense-seasons.json`. The hourly run rebuilds only the current season and carries the rest forward from the deploy branch; any season missing there is rebuilt automatically. A manual "backfill" run of the workflow rebuilds everything, which is required after any scoring rule change.

Leaderboard: season selector (each year plus All seasons), Full season button for single seasons, and in All seasons a Career or Single seasons row mode. The table shows Fumble (7) and Fumble lost (10) as separate columns, and Interception (10) and Pick six bonus (21) as separate columns.

Known data notes: nflverse uses current team codes for old seasons (2012 Chargers show as LAC, 2005 Raiders as LV). One 1999 stat row (Steve Bono, week 9) had no team; the pipeline fills missing teams from play-by-play. Seasons before 2021 had 16 games, so per-game numbers compare better across eras.

Next idea from the owner: a "Super Stars" hall-of-shame page with all-time worst by each stat (receptions and rushing attempts excluded, since they are not bad plays).

## 21. Super Stars page (October 16, 2026)

`super-stars.html`: a single-game record and a single-season record for every scored stat (total Sabotage points, incompletions, sacks, interceptions, pick sixes, fumbles, fumbles lost, missed or blocked field goals, missed or blocked extra points, points allowed by a defense, rushing attempts, receptions), 1999 to now. Owner direction: games and seasons only, no careers; presented as stories in the Wreckage Report voice. Built statically by the pipeline (`pipeline/records.py`, data in `data/records.json`) and refreshed every run, so a current-season record shows up automatically with an "Active season" badge. Ties list co-holders.

Checked against outside sources: Rudi Johnson 43 carries (Bengals record, tied the NFL mark for a regulation game), Matt Gay 3 failed extra points on Nov 24, 2019 (PFR scoring summary). Known data difference: Eli Manning's 2007 Week 15 game is 18 of 53 officially (35 incompletions) but 52 attempts in nflverse (34); the record card carries a note. Add any future differences to `config/record_notes.yml`.

Team nicknames in stories are era-correct for Washington (Redskins through 2019, Washington Football Team 2020 and 2021, Commanders 2022 on). Team codes in tables still follow nflverse.

## 22. Record alerts (October 16, 2026)

Owner request: when a current-season game or season total passes or ties an all-time record, flag it right away, with a clear note that stat corrections could still take it away.

How it works (`pipeline/records.py`, `_alert`): each run compares the current season against the best mark from all earlier seasons, for every stat and both scopes. Passing it is "broken", matching it is "tied". For season records, the alert week is the week the running total first passed (or reached) the old mark. The alert is "Potential record broken/tied" until that week is final (10 AM ET on the first Thursday after the week's last game, the same rule as the leaderboard), then "Record broken/tied". Pending text names the exact deadline, e.g. "If the numbers stand until 10 AM Eastern on Thursday, October 22, it goes in the book."

Where it shows: the home-page Wreckage Report puts alert cards first (double width) while pending, plus any record set in the week the report covers; the Super Stars card shows a badge, and while pending shows the alert text in place of the regular story. Tests: `tests/test_records.py` (broken, tied, official, season running total, no false alert).

## 23. Licensing decision (owner, October 16, 2026)

Option A: launch free and ad-free on nflverse data with CC BY 4.0 attribution, the non-affiliation disclaimer, no logos or headshots, and no direct access to NFL.com. Reason: the site is in the "build awareness of the format" stage, so it stays non-commercial.

Revisit trigger: if traffic grows and ads, subscriptions, or any revenue are considered, do option B (sports-media attorney review) first, and switch the planned weather source off Open-Meteo's free non-commercial tier. Option C (licensed feed such as SportsDataIO) stays on the table if the attorney advises it.

Background research: NBA v. Motorola, 105 F.3d 841 (2d Cir. 1997), game facts are not copyrightable; C.B.C. Distribution v. MLB Advanced Media (8th Cir. 2007), First Amendment outweighed publicity rights for fantasy use of player names and stats; NFL.com Terms (May 16, 2024) limit use of NFL.com to non-commercial purposes and bar systematic retrieval. Not legal advice.

## 24. Phone speed (October 16, 2026)

Measured in Chromium with Lighthouse's mobile preset (150 ms round trip, 1.6 Mbps down, 750 Kbps up, 4x CPU slowdown), gzip on, time until leaderboard rows appear:

| View | Before | After |
|---|---|---|
| Current season | 3.5 s | 2.1 s |
| A past season (2019) | 3.9 s | 2.5 s |
| All seasons, Career | 8.5 s | 2.5 s |
| All seasons, Single seasons | 8.4 s | 4.9 s |
| Super Stars | 0.3 s | 0.3 s |

Changes: meta and the season list are baked into index.html (two fewer round trips); the current season's data files and the foot.js module are preloaded; the Career view reads precomputed `player-careers.json` / `defense-careers.json` (107 KB gzip) instead of all 18,000 player-seasons (400 KB); totals are recomputed only when the season or week range changes; the table draws 300 rows with a "Show more" button; phones get a 240 px hero image (19 KB instead of 58 KB). Single seasons remains the slowest view; slimming that file is an option if it matters.

## 25. Phase 2 core (October 16, 2026)

Shipped to /preview on October 16. The player comparison page comes next and will also use the name Accomplishments (owner, October 16; replaces "Tale of the Tape" so the site does not echo NFL Savant), at the owner's direction.

Search. A box in the header of every page except home, and a large box under the hero on home with position chips (All, QB, RB, WR, TE, K, DEF). Matching ignores accents, apostrophes, periods, hyphens, and Jr/Sr/II/III. "smith njig" finds Jaxon Smith-Njigba. Recent and high-scoring players rank first. Team names and codes find the defense. The index is `data/search.json` (4,050 players), loaded on first focus.

Player page, `player.html?id=<gsis id>&season=<year|career>`:
- Tiles for Sabotage points, per game, games, and position rank (seasons in Career view).
- Accomplishments: count, per game, and points for each scored stat, with a percentile bar. Percentiles compare the per-game rate against the same position that season, among players with 4 or more games; FB counts as RB. A zero rate shows 0. Under 4 games, no bars.
- Weekly stacked chart: passing misfires (incompletions, sacks), turnovers (fumbles, fumbles lost, INT, pick six), touches (carries, catches), missed kicks, with a 3-game average line. Career view charts each season.
- Game log, splits (home/away, indoors/outdoors, wind under 10, 10 to 19, 20+ mph from nflverse schedules), and the next scheduled game.

Defenses page, `defenses.html?season=<year>&team=<code>`: the five most generous defenses, a sortable season table with points-allowed bucket counts, and a week grid showing points allowed, shaded by Sabotage points earned.

Leaderboard player names link to player pages; DEF rows link to the Defenses page.

Hand check (Jameis Winston, 2026 Week 5 at WAS): 21 incompletions x 2 = 42, 2 sacks x 5 = 10, 1 fumble 7 + lost 10 = 17, 5 carries = 5. Total 74, matching the chart and game log.

New data files: `games-YYYY.json` (schedule context per season), `players/<id>.json` (one per player), `search.json`.

## 26. Compare page (October 17, 2026)

Live on /preview October 17 at `compare.html?ids=<id>,<id>&season=<year|career>&from=&to=&view=pg`. Page heading Battlefield (owner, October 17: a versus theme for the compare page; Accomplishments stays as the stat section on player pages). Menu label Compare.

- Up to 4 players. Each keeps his color (chart slots 1 to 4) when another is removed.
- One season and week range, or Career, shared by everyone. Totals or per game.
- Side-by-side table of every scored stat (count, with the points it produced); the most points in each row is marked yellow, plus hidden "(most)" text for screen readers.
- Lines by week (by season in Career view) with a hover or tap tooltip listing every player, and a breakdown by event group on one scale.
- A note appears when positions differ.
- Entry points: Compare in the menu, a Compare button on player pages, and a + on leaderboard rows that fills a compare bar.

Hand checks: Winston 2019 totals 1,367 (492 + 235 + 300 + 147 + 84 + 50 + 59); Barkley career 2,711; Tucker 2019 kicking 46 = two missed PATs (32) + one missed 40 to 49 yard field goal (14).

Phase 2 exit criteria: every page works on desktop and phone (checked at 1280 and 390 px). The "stranger finds and compares two players without instructions" test still needs a real person who has not seen the site.

## 27. Video page (Phase 3, October 18, 2026)

Live on /preview at `video.html?season=&week=`, menu label Video, page heading Reel Good Sabotage (owner, October 18; was The Lowlights). Videos open on YouTube: NFL Rush uploads carry an NFL claim that blocks playback on other sites, which the oEmbed check cannot detect, so `play_on_site: false` is set. Past seasons: NFL Rush playlists for 2024 and 2023 (titles must name a week); 2025 has no playlist and goes in by hand.

Source: NFL Rush's playlist "The Worst NFL Plays - 2026 Season" (list=PLFGkcMzJRQbA), newest first, plus NFL Rush's channel uploads filtered by "worst plays" as a backup. Both are set in `config/video_sources.yml`. Week 2 was missing from the playlist and was added by hand in `config/videos_manual.csv` (`2026,2,<link>,`). A manual row replaces that week; `none` in place of a link hides it.

Each run: read the feeds, assign a week (the title's week number if that week has finished, else the latest week finished by the publish date in Eastern time), check embedding through oEmbed (200 yes, 401/403 no, 404 dropped), keep earlier finds, write `data/videos.json`. A YouTube failure never stops the score update.

First run, October 18: weeks 1 to 5 found, all embeddable, all from NFL Rush.

The page shows a thumbnail and loads the youtube-nocookie.com player only on press, a "watch on YouTube" card if embedding is off, the week's top five Sabotage scorers, and earlier weeks.

Phase 3 exit criteria: a manual add takes one line (met). "The latest video appears for its week without manual work" gets its first real test when the Week 6 video is posted.

## 28. Projections and Matchups (Phase 4, October 19, 2026)

Built on the `phase4` branch: `pipeline/project.py` (history, baselines, count model, game context, Poisson and logistic fits), `pipeline/projections.py` (the weekly build), `pipeline/weather.py` with `config/stadiums.csv`, `pipeline/backtest.py`, `matchups.html`, a projection box on player pages, and a "How projections work" section on the method page.

Walk-forward backtest of the production code, 2021 to 2025 regular seasons (`config/backtest.json`):

| Position | Avg miss, model | Season avg | Last 4 | Rank match, model | Season avg | Inside 10-90 range |
|---|---|---|---|---|---|---|
| QB | 19.54 | 20.37 | 21.00 | 0.31 | 0.26 | 82% |
| RB | 5.38 | 5.47 | 5.54 | 0.75 | 0.72 | 87% |
| WR | 3.60 | 3.77 | 3.82 | 0.61 | 0.58 | 90% |
| TE | 2.94 | 3.04 | 3.14 | 0.59 | 0.56 | 90% |
| K | 7.49 | 7.49 | 7.54 | 0.04 | 0.04 | 93% |
| DEF | 7.05 | 8.12 | | 0.37 | 0.10 | |

Kickers ship the season-to-date baseline, labeled: a distance, wind and kicker-skill model scored 8.05 average miss against the baseline's 7.50 and ran high (7.1 projected vs 5.7 actual per game).

Players: each team's starters from its latest nflverse depth chart (QB1, RB1-2, WR1-3, TE1-2, K; owner, October 19), skipping anyone listed Out, Doubtful or IR and moving the next man up. If depth charts are unavailable, players with a game in the team's last three games, one QB per team. Game cards on the Matchups page show each QB and defense and open to every starter. The preview moves to the next week once the current week is down to its last two games.

Weather: Open-Meteo free tier, non-commercial, under 10,000 calls a day, CC BY 4.0 (terms checked October 19, 2026 at open-meteo.com/en/terms). Stadium coordinates are checked against Open-Meteo's geocoder on the first run after the table changes (`data/stadium_check.json`). International venues carry a roof override, since nflverse lists some open-air stadiums as domes.
