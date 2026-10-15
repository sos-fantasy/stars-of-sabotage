# Phase 0 Findings

October 15, 2026. Data pulled with nflreadpy 0.1.5. Covers 2026 weeks 1 to 5 (79 games, all complete). Week 6 starts tonight, SEA at DEN.

## Status

| Phase 0 item | Status |
|---|---|
| Real nflverse schemas, fix 4.1 | Done. All expected columns exist. Brief section 4.1 updated |
| Scoring engine | Built. `config/scoring.yml`, `pipeline/score.py`, 30 hand-computed tests passing |
| Settle 3.3 against the league | Owner ruled on all 7 (brief 3.3). Two items left: return fumbles, and a 0-point shutout |
| NFL.com and nflverse terms | Read. Summary below. The open risk stays open |
| Video channel, title pattern, embed test | Partly done. See below. NFL Rush titles not confirmed |
| GitHub scheduled-workflow rule | Confirmed: public repos, 60 days without activity |
| Deploy path (5.2) | Waiting on owner |
| NFL Savant screenshots | Waiting on owner |

## Scoring results, weeks 1 to 5 (league rules)

Rules applied: stacking on, raw points allowed, blocked kicks count as misses, fumbles by QB/RB/FB/WR/TE on offensive plays (including QB snap fumbles), return fumbles excluded pending check.

Fumbles are counted from play-by-play. nflverse's sack, rushing, and receiving fumble columns miss aborted and dropped snaps; 4 QB snap fumbles turned up through week 5 (Jones wk 3, Maye wk 4, Hurts wk 5, Stroud wk 5). Lost fumbles reconcile exactly with the stat columns (78 = 78). Total fumbles run 167 against the columns' 163, the difference being those 4 snaps.

Hand check, Justin Herbert: 58 incompletions x2 = 116, 17 sacks x5 = 85, 24 carries x1 = 24, 6 fumbles x7 = 42, 2 lost x10 = 20, 7 interceptions x10 = 70. Total 357.

Top 10 players (all QBs): Herbert LAC 357, Shough NO 332, Watson CLE 320, Willis MIA 316, Maye NE 314, D. Jones IND 293, Rodgers PIT 290, Brissett ARI 284, Stafford LA 281, Love GB 278.

Top 5 by position. RB: Gibbs DET 176, Cook BUF 157, B. Robinson ATL 152, A. Jones MIN 145, J. Taylor IND 144. WR: St. Brown DET 81, Lamb DAL 80, Olave NO 78, McMillan CAR 76, Smith-Njigba SEA 75. TE: McBride ARI 84, Likely NYG 73, J. Johnson NO 67, Bowers LV 65, Warren IND 63. K: Smack GB 74, Stevens WAS 72, Pineiro SF 68, Carlson NO 56, Mevis LA 54.

Top 5 defenses: ARI 182 (162 allowed), NO 168, WAS 168, DET 168, BUF 161. No shutouts yet.

## Spot checks for the owner (Yahoo, by eye)

| Player-week | Our score | What it tests |
|---|---|---|
| Baker Mayfield TB wk 1 | 86 | Stacked lost fumble |
| Matthew Stafford LA wk 3 | 113 | Pick six = 31 |
| Daniel Jones IND wk 3 | 98 | Aborted snap plus 2 lost fumbles |
| Jalen Hurts PHI wk 5 | 59 | Aborted snap |
| Cairo Santos CHI wk 2 | 18 | Blocked 23-yard FG |
| Drew Stevens WAS wk 1 | 28 | Blocked PAT |
| ARI defense wk 4 | 42 | 36 allowed, raw |
| KaVontae Turpin DAL wk 5 | 4 (21 if return fumbles count) | Open: return fumbles |

## Terms and licensing

nflverse-data repo: CC BY 4.0. Attribution required: credit the creator, note the license, and link it. The license grants only rights the licensor holds (Section 1(g)), and its notes say use "may still be restricted for other reasons." So the CC license does not clear any NFL rights in the underlying stats.

NFL.com Terms of Service (last updated May 16, 2024): use is limited to "individual non-commercial and informational purposes." They bar "systematic retrieval of data" to build a database without written consent, and bar copying or distributing Services content. These terms bind users of NFL.com. This project never touches NFL.com directly; it reads nflverse's GitHub releases. Whether the NFL's terms or rights reach a third party who uses nflverse's republished data is a legal question these documents do not answer.

What I could not find: any nflverse statement on NFL permission for its data, or any NFL policy on game statistics published by third parties. Box score facts are widely republished by stats sites, but I have no source that settles this, and I am not a lawyer. Options: (A) launch free and ad-free with attribution and a non-affiliation disclaimer, accepting the risk; (B) ask a sports-media attorney before launch; (C) switch to a licensed feed such as SportsDataIO. I lean toward A for a free hobby site with B before any ads or paid tier.

## Video

NFL Rush channel: handle @NFLRush, ID `UC_vl8cSXLBi1tVegCKMRtTw`.

Not confirmed: whether NFL Rush posts a weekly "Worst Plays" video. Searches turned up "NFL Worst Plays of Week 5 (2026) | Top 25 Countdown" (video `UhtGp5GH7Zo`), but oEmbed shows it comes from a different channel, Trenz (@Trenz-Sports). That video returns an embed iframe through oEmbed, so it is embeddable. My workspace cannot reach youtube.com directly and YouTube blocks automated reads of the RSS feed from my fetch tool, so I could not list NFL Rush's recent titles. GitHub Actions runners can read the feed, so the pipeline plan still works.

Owner check: open youtube.com/@NFLRush/videos and tell me whether the worst-plays series is there, or whether the Trenz series is the one you meant. Third-party compilations of NFL footage can be taken down, so the manual override path in section 10 matters more if we use one.

## Owner decisions needed

1. Turpin wk 5 in Yahoo (4 or 21) to settle return fumbles, plus the other spot checks.
2. Shutout scoring: 0 points (current assumption) or something else.
3. Which channel carries the worst-plays video you want.
4. Deploy path A, B, or C (brief 5.2). I recommend A.
5. Public or private GitHub repo. Private avoids the 60-day rule. Before choosing private, I will check the current free Actions minutes for private repos against an hourly schedule.
6. Licensing approach A, B, or C above.
7. NFL Savant screenshots.

## Sources

- nflverse-data repo and license: https://github.com/nflverse/nflverse-data
- NFL.com Terms of Service: https://www.nfl.com/legal/terms/
- GitHub, disable and enable workflows: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- NFL Rush channel: https://www.youtube.com/@NFLRush
- Trenz worst-plays video: https://www.youtube.com/watch?v=UhtGp5GH7Zo
