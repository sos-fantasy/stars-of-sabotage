import { $, esc, NICK } from "./common.js?v=dd86e435db";
import { loadMeta, fillFooter } from "./foot.js?v=949d944f7b";
import { loadInjuries, loadDepth, injTag, slotOf } from "./avail.js?v=2b6f548bac";

// The coming week: every game with its kickoff, roof and forecast, and projected
// Sabotage points by position. Projections are "if he plays" and come with a range.
const POS = ["QB", "RB", "WR", "TE", "K", "DEF"];
let data = null, pos = "QB";
let RES = null, CUR = null, VER = "", resPos = "ALL", resSort = "proj", resWeek = null, resAll = false;
const weekCache = new Map();
async function weekFile(season, week) {
  const k = `${season}-${week}`;
  if (!weekCache.has(k)) {
    weekCache.set(k, fetch(`data/results/${season}-w${String(week).padStart(2, "0")}.json?v=${VER}`)
      .then((r) => (r.ok ? r.json() : null)).catch(() => null));
  }
  return weekCache.get(k);
}

const fmt = (v, d = 1) => (v === null || v === undefined ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const posOf = (p) => (p.pos === "FB" ? "RB" : p.pos);
const COMP = { n_incomplete: "inc", n_sacks: "sacks", n_carries: "carries", n_receptions: "catches",
  n_fumbles: "fumbles", n_fumbles_lost: "lost", n_ints: "INT", n_pick_sixes: "pick six" };

function kickoff(g) {
  const [h, m] = (g.gametime || "13:00").split(":").map(Number);
  const d = new Date(`${g.gameday}T12:00:00`);
  const day = d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  return `${day}, ${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"} ET`;
}
function sky(g) {
  const w = g.weather;
  if (g.roof === "dome" || g.roof === "closed" || (w && w.indoor)) return "Indoors";
  if (!w) return g.roof === "retractable" || g.roof === "open" ? "Retractable roof, forecast closer to kickoff" : "Outdoors, forecast closer to kickoff";
  const bits = [];
  if (w.temp_f !== null && w.temp_f !== undefined) bits.push(`${Math.round(w.temp_f)}°F`);
  if (w.sky) bits.push(w.sky.toLowerCase());
  if (w.wind_mph !== null && w.wind_mph !== undefined) bits.push(`wind ${Math.round(w.wind_mph)} mph${w.gust_mph ? `, gusts ${Math.round(w.gust_mph)}` : ""}`);
  if (w.precip_pct) bits.push(`${w.precip_pct}% chance of rain or snow`);
  return `Forecast: ${bits.join(", ")}`;
}

async function init() {
  let meta = null;
  try {
    meta = await loadMeta();
    const v = `${meta.data_hash}-${Math.floor(Date.now() / 300000)}`;
    [data, RES] = await Promise.all([
      fetch(`data/projections.json?v=${v}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`data/results-${meta.season}.json?v=${v}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      loadInjuries(), loadDepth()]);
    VER = v;
    // This week's frozen projections and actuals, for the game cards.
    if (data && RES && RES.weeks.some((w) => w.week === data.week)) CUR = await weekFile(data.season, data.week);
  } catch (e) { data = null; }
  if (meta) fillFooter(meta);
  if (!data || !data.players) {
    $("#m-top").innerHTML = `<p class="loading">No projections right now. They return when the next week's schedule is set.</p>`;
    return;
  }
  $("#m-week").textContent = `${data.season} week ${data.week}`;
  $("#m-tabs").innerHTML = POS.map((p) => `<button type="button" data-p="${p}" aria-pressed="${p === pos}">${p}</button>`).join("");
  $("#m-tabs").onclick = (e) => { const b = e.target.closest("[data-p]"); if (b) { pos = b.dataset.p; top(); } };
  top();
  games();
  results();
}

function top() {
  document.querySelectorAll("#m-tabs [data-p]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.p === pos)));
  let rows;
  if (pos === "DEF") {
    rows = data.defenses.slice(0, 10).map((d, i) => `<tr><td class="num dim">${i + 1}</td>
      <td><a class="plink" href="defenses.html?team=${d.team}">${esc(NICK[d.team] || d.team)}</a> <span class="dim">vs ${esc(d.opp)}</span></td>
      <td class="num total">${fmt(d.proj)}</td><td class="num dim">${fmt(d.lo, 0)} to ${fmt(d.hi, 0)}</td>
      <td class="dim">Expected to allow about ${fmt(d.pa_mean, 0)} points</td></tr>`);
  } else {
    rows = data.players.filter((p) => posOf(p) === pos).slice(0, 10).map((p, i) => `<tr><td class="num dim">${i + 1}</td>
      <td><a class="plink" href="player.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a> <span class="dim">${esc(p.team)} ${p.home ? "vs" : "at"} ${esc(p.opp)}</span>${infor(p)}${injTag(p.id, { block: true })}</td>
      <td class="num total">${fmt(p.proj)}</td><td class="num dim">${fmt(p.lo, 0)} to ${fmt(p.hi, 0)}</td>
      <td class="dim">${esc(why(p))}</td></tr>`);
  }
  $("#m-top").innerHTML = `<div class="table-wrap plain"><table><tr><th class="num">#</th><th>${pos === "DEF" ? "Defense" : "Player"}</th>
    <th class="num">Projection</th><th class="num">Likely range</th><th>Why</th></tr>${rows.join("")}</table></div>`;
}

// A backup moved up because a starter is unavailable.
function infor(p) {
  const s = slotOf(p.id);
  return s && s.in_for ? ` <span class="infor">in for ${esc(s.in_for)}</span>` : "";
}

function why(p) {
  const parts = Object.entries(p.components || {}).filter(([, v]) => v >= 0.5)
    .sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `${fmt(v)} ${COMP[k]}`);
  const d = (p.drivers || []).slice(0, 1);
  return [parts.join(", "), ...d].filter(Boolean).join(". ");
}

const SLOT_ORDER = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "TE2", "K"];
// Once a game kicks off, its card shows the projections frozen at kickoff (from the
// results file) and, after the game, what each player scored.
function started(gid) {
  const k = CUR && CUR.game_info && CUR.game_info[gid] && CUR.game_info[gid].kickoff;
  return !!k && new Date(k) <= new Date();
}
const actual = (r) => {
  if (!r) return "";
  if (r.status === "final") return `<span class="act" title="Scored ${r.actual}, ${r.miss > 0 ? "+" : ""}${fmt(r.miss)} vs projection">${r.actual}<small>${r.miss > 0 ? "+" : ""}${fmt(r.miss)}</small></span>`;
  if (r.status === "dnp") return `<span class="act"><small>did not play</small></span>`;
  if (r.status === "awaiting") return `<span class="act"><small>stats soon</small></span>`;
  return "";
};
function games() {
  const byGame = new Map();
  const add = (p) => { if (!byGame.has(p.game_id)) byGame.set(p.game_id, []); byGame.get(p.game_id).push(p); };
  const frozen = new Map();   // game_id -> rows from the results file
  for (const r of (CUR && CUR.rows) || []) if (started(r.game_id) && r.status !== "removed") frozen.set(`${r.id}`, r);
  for (const p of data.players) if (!started(p.game_id)) add(p);
  for (const r of frozen.values()) if (r.pos !== "DEF") add({ ...r, _res: r });
  const defs = new Map(data.defenses.map((d) => [`${d.game_id}-${d.team}`, d]));
  for (const r of frozen.values()) if (r.pos === "DEF") defs.set(`${r.game_id}-${r.team}`, { ...r, _res: r });
  const line = (p) => `<li><span class="slot">${esc(p.slot || p.pos)}</span><span><a class="plink" href="player.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a>${p._res ? "" : infor(p) + injTag(p.id, { block: true })}</span><b>${fmt(p.proj)}${actual(p._res)}</b></li>`;
  const side = (g, team) => {
    const ps = (byGame.get(g.game_id) || []).filter((p) => p.team === team)
      .sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot));
    const d = defs.get(`${g.game_id}-${team}`);
    return `<div class="gside"><p class="gteam">${esc(NICK[team] || team)}</p><ol class="glist">${ps.map(line).join("")}
      ${d ? `<li><span class="slot">D</span><a class="plink" href="defenses.html?team=${team}">${esc(NICK[team] || team)} defense</a><b>${fmt(d.proj)}${actual(d._res)}</b></li>` : ""}</ol></div>`;
  };
  // Every game of the week: upcoming ones from the projections, and ones that have
  // kicked off from the frozen cards in the results file (with the score once final).
  const upcoming = data.games.filter((g) => !started(g.game_id));
  const begun = ((CUR && CUR.cards) || []).filter((g) => started(g.game_id) && !upcoming.some((u) => u.game_id === g.game_id));
  const all = [...begun, ...upcoming];
  $("#m-games").innerHTML = all.map((g) => {
    const qbs = (byGame.get(g.game_id) || []).filter((p) => p.slot === "QB" || (!p.slot && p.pos === "QB"));
    const qbFor = (team) => qbs.find((p) => p.team === team);
    const dh = defs.get(`${g.game_id}-${g.home}`), da = defs.get(`${g.game_id}-${g.away}`);
    const row = (team, d) => { const q = qbFor(team); return `<li><span class="slot">${esc(team)}</span>${q ? `<span>${esc(q.name)} <b class="qb">${fmt(q.proj)}</b>${q._res ? actual(q._res) : injTag(q.id)}</span>` : "<span></span>"}<span class="dim">D ${d ? fmt(d.proj) : ""}${d && d._res ? actual(d._res) : ""}</span></li>`; };
    const gi = CUR && CUR.game_info && CUR.game_info[g.game_id];
    const score = gi && gi.home_score !== null && gi.home_score !== undefined
      ? `<span class="gscore">${esc(g.away)} ${gi.away_score}, ${esc(g.home)} ${gi.home_score}</span>` : "";
    return `<details class="gcard"><summary>
      <h3>${esc(NICK[g.away] || g.away)} <span class="dim">at</span> ${esc(NICK[g.home] || g.home)}${score}</h3>
      <p class="gmeta">${kickoff(g)}${g.stadium ? ` · ${esc(g.stadium)}` : ""}${started(g.game_id) ? (gi && gi.home_score !== null && gi.home_score !== undefined ? " · Final" : " · In progress or awaiting the final") : ""}</p>
      ${started(g.game_id) && !g.weather ? "" : `<p class="gmeta">${esc(sky(g))}</p>`}
      ${g.home_implied !== null && g.home_implied !== undefined && g.away_implied !== null ? `<p class="gmeta">Expected score from the spread and total: ${esc(g.away)} ${fmt(g.away_implied)}, ${esc(g.home)} ${fmt(g.home_implied)}</p>` : ""}
      <ol class="gqb">${row(g.away, da)}${row(g.home, dh)}</ol>
      <p class="gmore">All starters</p></summary>
      <div class="gfull">${side(g, g.away)}${side(g, g.home)}</div>
      <p class="gmore"><a href="depth.html?team=${g.away}">${esc(NICK[g.away] || g.away)} depth chart</a> · <a href="depth.html?team=${g.home}">${esc(NICK[g.home] || g.home)} depth chart</a></p></details>`;
  }).join("");
}

// ---------- projected vs actual ----------
const RES_POS = ["ALL", "QB", "RB", "WR", "TE", "K", "DEF"];
const STATUS_TEXT = { pending: "Game not over", dnp: "Did not play", removed: "Dropped before kickoff (ruled out or moved down the depth chart)",
  awaiting: "Game over, stats coming" };
async function results() {
  if (!RES || !RES.weeks.length) { $("#m-res").innerHTML = `<p class="loading">No results yet.</p>`; return; }
  const sel = $("#m-res-week");
  const weeks = [...RES.weeks].sort((a, b) => b.week - a.week);
  sel.innerHTML = weeks.map((w) => `<option value="${w.week}">Week ${w.week}${w.source === "replayed" ? " (replayed)" : ""}${w.games_final < w.games ? `, ${w.games_final} of ${w.games} games final` : ""}</option>`).join("");
  // Default: the latest week with any final result.
  const live = weeks.find((w) => w.n_final > 0) || weeks[0];
  resWeek = live.week;
  sel.value = String(resWeek);
  sel.onchange = () => { resWeek = +sel.value; resAll = false; resultsTable(); };
  $("#m-res-tabs").innerHTML = RES_POS.map((p) => `<button type="button" data-p="${p}" aria-pressed="${p === resPos}">${p}</button>`).join("");
  $("#m-res-tabs").onclick = (e) => { const b = e.target.closest("[data-p]"); if (b) { resPos = b.dataset.p; resAll = false; resultsTable(); } };
  $("#m-res-sort").innerHTML = [["proj", "Projection"], ["miss", "Biggest misses"], ["actual", "Actual"]]
    .map(([k, l]) => `<button type="button" data-s="${k}" aria-pressed="${k === resSort}">${l}</button>`).join("");
  $("#m-res-sort").onclick = (e) => { const b = e.target.closest("[data-s]"); if (b) { resSort = b.dataset.s; resultsTable(); } };
  $("#m-res").onclick = (e) => { if (e.target.closest("#m-res-more")) { resAll = true; resultsTable(); } };
  resultsTable();
}

async function resultsTable() {
  document.querySelectorAll("#m-res-tabs [data-p]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.p === resPos)));
  document.querySelectorAll("#m-res-sort [data-s]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.s === resSort)));
  const W = await weekFile(RES.season, resWeek);
  if (!W) { $("#m-res").innerHTML = `<p class="loading">That week is not available.</p>`; return; }
  let rows = W.rows.filter((r) => resPos === "ALL" || r.pos === resPos);
  const key = { proj: (r) => -r.proj, actual: (r) => (r.status === "final" ? -r.actual : 1e9),
    miss: (r) => (r.status === "final" ? -Math.abs(r.miss) : 1e9) }[resSort];
  rows = [...rows].sort((a, b) => key(a) - key(b) || b.proj - a.proj);
  const done = rows.filter((r) => r.status === "final");
  const avg = done.length ? done.reduce((a, r) => a + Math.abs(r.miss), 0) / done.length : null;
  const inr = done.length ? done.filter((r) => r.in_range).length / done.length : null;
  const per = resPos === "ALL" ? Object.entries(W.summary).map(([p, v]) => `<span>${p} ${fmt(v.avg_miss)}</span>`).join("") : "";
  const sum = `<p class="hint ressum"><span>${done.length} of ${rows.length} final.</span>${avg !== null ? `<span>Average miss ${fmt(avg)} points.</span><span>${Math.round(inr * 100)}% inside the likely range.</span>` : ""}
    ${per ? `<br><span class="dim">Average miss by position:</span> ${per}` : ""}
    ${W.source === "replayed" ? `<br>Replayed week: projections rebuilt after the fact from earlier games, for every player who played.` : ""}</p>`;
  const LIMIT = 40;
  const shown = resAll ? rows : rows.slice(0, LIMIT);
  const link = (r) => (r.pos === "DEF" ? `defenses.html?team=${r.team}` : `player.html?id=${encodeURIComponent(r.id)}`);
  const body = shown.map((r, i) => `<tr><td class="num dim">${i + 1}</td>
    <td><a class="plink" href="${link(r)}">${esc(r.pos === "DEF" ? `${NICK[r.team] || r.team} defense` : r.name)}</a> <span class="dim">${esc(r.pos)} · ${esc(r.team)} ${r.home === 0 ? "at" : "vs"} ${esc(r.opp)}</span></td>
    <td class="num">${fmt(r.proj)}</td><td class="num dim">${fmt(r.lo, 0)} to ${fmt(r.hi, 0)}</td>
    ${r.status === "final"
      ? `<td class="num total">${r.actual}</td><td class="num offby ${r.miss > 0 ? "up" : r.miss < 0 ? "down" : ""}">${r.miss > 0 ? "+" : ""}${fmt(r.miss)}${r.in_range ? "" : `<span class="inrange" title="Outside the likely range">out of range</span>`}</td>`
      : `<td colspan="2" class="dim">${esc(STATUS_TEXT[r.status] || r.status)}</td>`}</tr>`).join("");
  $("#m-res").innerHTML = `${sum}<div class="table-wrap plain"><table><tr><th class="num">#</th><th>Player</th><th class="num">Projected</th>
    <th class="num">Likely range</th><th class="num">Actual</th><th class="num" title="Actual minus projected">Off by</th></tr>${body}</table></div>
    ${rows.length > shown.length ? `<button type="button" class="btn" id="m-res-more">Show all ${rows.length}</button>` : ""}
    <p class="hint">Off by is actual minus projected: plus means he scored more Sabotage points than projected. <a href="improvements.html?season=${RES.season}&week=${resWeek}">Why the biggest misses happened</a>.</p>`;
}

init();
