# Phase 0 Findings

October 15, 2026. Data pulled with nflreadpy 0.1.5. Covers 2026 weeks 1 to 5 (79 games, all complete). Week 6 starts tonight, SEA at DEN.

## Status

| Phase 0 item | Status |
|---|---|
| Real nflverse schemas, fix 4.1 | Done. All expected columns exist. Brief section 4.1 updated |
| Scoring engine with 3.3 options | Built. `config/scoring.yml`, `pipeline/score.py`, 19 hand-computed tests passing |
| Settle 3.3 against the league | Waiting on owner: check the player-weeks listed below in Yahoo |
| NFL.com and nflverse terms | Read. Summary below. The open risk stays open |
| Video channel, title pattern, embed test | Partly done. See below. NFL Rush titles not confirmed |
| GitHub scheduled-workflow rule | Confirmed: public repos, 60 days without activity |
| Deploy path (5.2) | Waiting on owner |
| NFL Savant screenshots | Waiting on owner |

## Scoring results, weeks 1 to 5

Default settings used for the tables: fumbles and lost fumbles stack, interceptions and pick sixes stack, offense-only fumbles, blocked kicks ignored, raw points allowed.

Hand check on the top player, Justin Herbert: 58 incompletions x2 = 116, 17 sacks x5 = 85, 24 carries x1 = 24, 6 fumbles x7 = 42, 2 lost x10 = 20, 7 interceptions x10 = 70. Total 357.

Top 10 players (all QBs): Herbert LAC 357, Shough NO 332, Watson CLE 320, Willis MIA 316, Maye NE 307, Rodgers PIT 290, D. Jones IND 286, Brissett ARI 284, Stafford LA 281, Love GB 278.

Top 3 by position. RB: Gibbs DET 176, Cook BUF 157, B. Robinson ATL 152. WR: St. Brown DET 81, Lamb DAL 80, Olave NO 78. TE: McBride ARI 84, Likely NYG 73, J. Johnson NO 67. K: Smack GB 60, Pineiro SF 56, Stevens WAS 56.

Top 5 defenses (raw points allowed): ARI 182 (162 allowed), NO 168, WAS 168, DET 168, BUF 161. Under offense-only points allowed, ARI drops to 175 and the rest hold.

## Validation list for the owner

Check these in Yahoo. Each one separates the options for one question. Report the Yahoo number and I will lock the config.

Q1, stacking (fumble + lost fumble, interception + pick six):

| Player-week | Stacked | Not stacked |
|---|---|---|
| Baker Mayfield TB wk 1 | 86 | 65 |
| Matthew Stafford LA wk 3 (pick six) | 113 | 103 |
| Jacoby Brissett ARI wk 4 (pick six) | 93 | 83 |
| Jahmyr Gibbs DET wk 1 | 56 | 49 |

Q4, return and snap fumbles:

| Player-week | Offense only | All fumbles |
|---|---|---|
| KaVontae Turpin DAL wk 5 | 4 | 21 |
| Isaiah Williams NYJ wk 2 | 13 | 27 |
| Amon-Ra St. Brown DET wk 5 | 19 | 26 |

Q3, blocked kicks:

| Player-week | Blocks ignored | Blocks count as misses |
|---|---|---|
| Drew Stevens WAS wk 1 (blocked PAT) | 12 | 28 |
| Cairo Santos CHI wk 2 (blocked 23-yard FG) | 0 | 18 |

Q2, points allowed:

| Defense-week | Raw | Offense only |
|---|---|---|
| ARI wk 4 vs NYG (36 allowed, 7 off a pick six) | 42 | 35 |
| LA wk 3 vs DEN (30 allowed, 7 off a pick six) | 35 | 28 |
| TB wk 3 vs MIN (23 allowed, 7 off a punt return) | 28 | 21 |

Q5, kick distance: nflverse buckets by the kick's total distance from the spot to the goalposts, the same number broadcasts use. The kicker rows above will confirm it matches.

Q6 and Q7 checks: nflverse counts QB kneel-downs as carries (Drake Maye's 30 carries include 7 kneels; 125 kneels league-wide) and spikes as incomplete passes (24 so far). This follows official NFL stat rules. If Yahoo shows fewer points for a QB who kneeled, this is the cause.

## Terms and licensing

nflverse-data repo: CC BY 4.0. Attribution required: credit the creator, note the license, and link it. The license grants only rights the licensor holds (Section 1(g)), and its notes say use "may still be restricted for other reasons." So the CC license does not clear any NFL rights in the underlying stats.

NFL.com Terms of Service (last updated May 16, 2024): use is limited to "individual non-commercial and informational purposes." They bar "systematic retrieval of data" to build a database without written consent, and bar copying or distributing Services content. These terms bind users of NFL.com. This project never touches NFL.com directly; it reads nflverse's GitHub releases. Whether the NFL's terms or rights reach a third party who uses nflverse's republished data is a legal question these documents do not answer.

What I could not find: any nflverse statement on NFL permission for its data, or any NFL policy on game statistics published by third parties. Box score facts are widely republished by stats sites, but I have no source that settles this, and I am not a lawyer. Options: (A) launch free and ad-free with attribution and a non-affiliation disclaimer, accepting the risk; (B) ask a sports-media attorney before launch; (C) switch to a licensed feed such as SportsDataIO. I lean toward A for a free hobby site with B before any ads or paid tier.

## Video

NFL Rush channel: handle @NFLRush, ID `UC_vl8cSXLBi1tVegCKMRtTw`.

Not confirmed: whether NFL Rush posts a weekly "Worst Plays" video. Searches turned up "NFL Worst Plays of Week 5 (2026) | Top 25 Countdown" (video `UhtGp5GH7Zo`), but oEmbed shows it comes from a different channel, Trenz (@Trenz-Sports). That video returns an embed iframe through oEmbed, so it is embeddable. My workspace cannot reach youtube.com directly and YouTube blocks automated reads of the RSS feed from my fetch tool, so I could not list NFL Rush's recent titles. GitHub Actions runners can read the feed, so the pipeline plan still works.

Owner check: open youtube.com/@NFLRush/videos and tell me whether the worst-plays series is there, or whether the Trenz series is the one you meant. Third-party compilations of NFL footage can be taken down, so the manual override path in section 10 matters more if we use one.

## Owner decisions needed

1. Yahoo numbers for the validation list above.
2. Which channel carries the worst-plays video you want.
3. Deploy path A, B, or C (brief 5.2). I recommend A.
4. Public or private GitHub repo. Private avoids the 60-day rule. Before choosing private, I will check the current free Actions minutes for private repos against an hourly schedule.
5. Licensing approach A, B, or C above.
6. NFL Savant screenshots.

## Sources

- nflverse-data repo and license: https://github.com/nflverse/nflverse-data
- NFL.com Terms of Service: https://www.nfl.com/legal/terms/
- GitHub, disable and enable workflows: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- NFL Rush channel: https://www.youtube.com/@NFLRush
- Trenz worst-plays video: https://www.youtube.com/watch?v=UhtGp5GH7Zo
