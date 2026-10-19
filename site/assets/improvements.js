import { $, esc } from "./common.js";
import { loadMeta, fillFooter } from "./foot.js";

// Weekly review of projection misses: the five biggest, what drove them, and what we
// plan to test. All numbers come from pipeline/review.py.
const params = new URLSearchParams(location.search);
const POS = { QB: "Quarterbacks", RB: "Running backs", WR: "Wide receivers", TE: "Tight ends", K: "Kickers", DEF: "Defenses" };
const TAG = { playing_time: "Playing time", injury_tag: "Injury report", volume: "Volume", efficiency: "Passing efficiency",
  game_script: "Game script", pressure: "Sacks", weather: "Weather", turnover_luck: "Turnover luck", news: "Unmeasured cause" };
const STATUS = { proposed: "Proposed", testing: "Testing", adopted: "Adopted", rejected: "Tested, no gain" };
const fmt = (v, d = 1) => (v === null || v === undefined ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
let data = null;

async function init() {
  let meta = null;
  try {
    meta = await loadMeta();
    data = await fetch(`data/improvements.json?v=${meta.data_hash}-${Math.floor(Date.now() / 300000)}`).then((r) => (r.ok ? r.json() : null));
  } catch (e) { data = null; }
  if (meta) fillFooter(meta);
  if (!data || !data.weeks || !data.weeks.length) {
    $("#i-week-body").innerHTML = `<p class="loading">The first review appears after a full week of games has been projected and played.</p>`;
    return;
  }
  const sel = $("#i-week");
  sel.innerHTML = data.weeks.map((w) => `<option value="${w.season}-${w.week}">${w.season} week ${w.week}${w.source === "replayed" ? " (replayed)" : ""}</option>`).join("");
  const want = `${params.get("season")}-${params.get("week")}`;
  if (data.weeks.some((w) => `${w.season}-${w.week}` === want)) sel.value = want;
  sel.onchange = () => { history.replaceState(null, "", `?season=${sel.value.split("-")[0]}&week=${sel.value.split("-")[1]}`); week(); };
  week();
  tally();
}

function week() {
  const [s, wk] = $("#i-week").value.split("-").map(Number);
  const w = data.weeks.find((x) => x.season === s && x.week === wk);
  const rows = Object.entries(w.summary).map(([pos, v]) => `<tr><td>${POS[pos] || pos}</td><td class="num">${v.n}</td>
    <td class="num">${fmt(v.avg_miss, 2)}</td><td class="num dim">${v.backtest === null || v.backtest === undefined ? "" : fmt(v.backtest, 2)}</td></tr>`).join("");
  const replay = w.source === "replayed"
    ? `<p class="notice">This week was replayed: the projections were rebuilt after the fact from games played before it, for every player who played, including backups who only got a few snaps. Weeks from now on use the last live projection before each kickoff, for depth-chart starters only.</p>` : "";
  $("#i-week-body").innerHTML = `${replay}
    <p class="hint">${w.n} projections compared. ${Math.round(w.range_hit * 100)}% of results landed inside the likely range (the target is about 80%).${w.did_not_play_n ? ` ${w.did_not_play_n} projected players did not play and are left out.` : ""} Status: ${w.status}.</p>
    <div class="table-wrap plain"><table><tr><th>Position</th><th class="num">Players</th><th class="num">Average miss this week</th><th class="num">Average miss in testing</th></tr>${rows}</table></div>
    <h2>Five biggest misses</h2>
    <div class="misses">${w.top.map(card).join("")}</div>
    ${w.claude ? `<section class="claude"><h2>Claude's read on this week</h2>${w.claude.split(/\n{2,}/).map((p) => p.trim().startsWith("What to test next") ? `<h3>${esc(p.trim().split("\n")[0])}</h3>${esc(p.trim().split("\n").slice(1).join(" ")) ? `<p>${esc(p.trim().split("\n").slice(1).join(" "))}</p>` : ""}` : `<p>${esc(p)}</p>`).join("")}
      <p class="hint">Written by Claude (${esc(w.claude_model || "")}) from the measured numbers on this page. Anything it marks as a guess is unconfirmed.</p></section>` : ""}`;
}

function card(t) {
  const link = t.kind === "defense" ? `defenses.html?team=${t.team}` : `player.html?id=${encodeURIComponent(t.id)}`;
  const b = (t.facts && t.facts.breakdown) || [];
  const f = t.facts || {};
  const measured = [];
  if (f.snap_pct !== undefined) measured.push(`Snaps: ${f.snap_pct}%${f.snap_pct_usual !== undefined ? ` (usual ${f.snap_pct_usual}%)` : ""}`);
  if (f.attempts) measured.push(`Pass attempts: ${f.attempts}${f.attempts_usual !== undefined ? ` (usual ${fmt(f.attempts_usual)})` : ""}`);
  if (f.inc_rate !== undefined) measured.push(`Throws missed: ${f.inc_rate}%${f.inc_rate_usual !== undefined ? ` (usual ${f.inc_rate_usual}%)` : ""}`);
  if (f.carries) measured.push(`Carries: ${f.carries}${f.carries_usual !== undefined ? ` (usual ${fmt(f.carries_usual)})` : ""}`);
  if (f.targets) measured.push(`Targets: ${f.targets}${f.targets_usual !== undefined ? ` (usual ${fmt(f.targets_usual)})` : ""}`);
  if (f.injury_status) measured.push(`Injury report: ${f.injury_status}`);
  if (t.game && t.game.score) measured.push(`Final: ${t.game.score}`);
  return `<article class="miss">
    <header><p class="mname"><a class="plink" href="${link}">${esc(t.name)}</a> <span class="dim">${esc(t.pos)} · ${esc(t.team)} vs ${esc(t.opp)}</span></p>
      <p class="mnums">Projected <b>${fmt(t.proj)}</b> · scored <b>${fmt(t.actual, 0)}</b> · <span class="${t.miss > 0 ? "up" : "down"}">${t.miss > 0 ? "+" : ""}${fmt(t.miss)}</span></p></header>
    ${b.length ? `<table class="mini"><tr><th>Event</th><th class="num">Projected</th><th class="num">Actual</th><th class="num">Points</th></tr>${b.map((x) => `<tr><td>${esc(x.event)}</td><td class="num">${fmt(x.projected)}</td><td class="num">${x.actual}</td><td class="num">${x.points > 0 ? "+" : ""}${fmt(x.points)}</td></tr>`).join("")}</table>` : ""}
    ${measured.length ? `<p class="mfacts">${measured.map(esc).join(" · ")}</p>` : ""}
    <ul class="why">${t.why.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
    ${t.tags.length ? `<p class="tags">${t.tags.map((g) => `<span>${TAG[g] || g}</span>`).join("")}</p>` : ""}
  </article>`;
}

function tally() {
  if (!data.tally || !data.tally.length) return;
  $("#i-tally").innerHTML = `<div class="table-wrap plain"><table class="wrap"><tr><th>Cause</th><th class="num">Times in a top five</th><th>What we would add or change</th><th>Status</th></tr>
    ${data.tally.map((r) => `<tr><td>${TAG[r.tag] || r.tag}</td><td class="num">${r.count} <span class="dim">(${Math.round(r.share * 100)}%)</span></td>
      <td><b>${esc(r.title)}.</b> ${esc(r.plan)}${r.note ? ` <span class="dim">${esc(r.note)}</span>` : ""}</td><td>${STATUS[r.status] || r.status}</td></tr>`).join("")}</table></div>
    <p class="hint">A miss can have more than one cause. Changes go live only after they beat the current projections on the 2021 to 2025 backtest.</p>`;
}

init();
