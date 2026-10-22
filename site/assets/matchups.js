import { $, esc, NICK } from "./common.js";
import { loadMeta, fillFooter } from "./foot.js";
import { loadInjuries, loadDepth, injTag, slotOf } from "./avail.js";

// The coming week: every game with its kickoff, roof and forecast, and projected
// Sabotage points by position. Projections are "if he plays" and come with a range.
const POS = ["QB", "RB", "WR", "TE", "K", "DEF"];
let data = null, pos = "QB";

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
    [data] = await Promise.all([
      fetch(`data/projections.json?v=${meta.data_hash}-${Math.floor(Date.now() / 300000)}`).then((r) => (r.ok ? r.json() : null)),
      loadInjuries(), loadDepth()]);
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
function games() {
  const byGame = new Map();
  for (const p of data.players) { if (!byGame.has(p.game_id)) byGame.set(p.game_id, []); byGame.get(p.game_id).push(p); }
  const defs = new Map(data.defenses.map((d) => [`${d.game_id}-${d.team}`, d]));
  const line = (p) => `<li><span class="slot">${esc(p.slot || p.pos)}</span><span><a class="plink" href="player.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a>${infor(p)}${injTag(p.id, { block: true })}</span><b>${fmt(p.proj)}</b></li>`;
  const side = (g, team) => {
    const ps = (byGame.get(g.game_id) || []).filter((p) => p.team === team)
      .sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot));
    const d = defs.get(`${g.game_id}-${team}`);
    return `<div class="gside"><p class="gteam">${esc(NICK[team] || team)}</p><ol class="glist">${ps.map(line).join("")}
      ${d ? `<li><span class="slot">D</span><a class="plink" href="defenses.html?team=${team}">${esc(NICK[team] || team)} defense</a><b>${fmt(d.proj)}</b></li>` : ""}</ol></div>`;
  };
  $("#m-games").innerHTML = data.games.map((g) => {
    const qbs = (byGame.get(g.game_id) || []).filter((p) => p.slot === "QB" || (!p.slot && p.pos === "QB"));
    const qbFor = (team) => qbs.find((p) => p.team === team);
    const dh = defs.get(`${g.game_id}-${g.home}`), da = defs.get(`${g.game_id}-${g.away}`);
    const row = (team, d) => { const q = qbFor(team); return `<li><span class="slot">${esc(team)}</span>${q ? `<span>${esc(q.name)} <b class="qb">${fmt(q.proj)}</b>${injTag(q.id)}</span>` : "<span></span>"}<span class="dim">D ${d ? fmt(d.proj) : ""}</span></li>`; };
    return `<details class="gcard"><summary>
      <h3>${esc(NICK[g.away] || g.away)} <span class="dim">at</span> ${esc(NICK[g.home] || g.home)}</h3>
      <p class="gmeta">${kickoff(g)} · ${esc(g.stadium || "")}</p>
      <p class="gmeta">${esc(sky(g))}</p>
      ${g.home_implied !== null && g.away_implied !== null ? `<p class="gmeta">Expected score from the spread and total: ${esc(g.away)} ${fmt(g.away_implied)}, ${esc(g.home)} ${fmt(g.home_implied)}</p>` : ""}
      <ol class="gqb">${row(g.away, da)}${row(g.home, dh)}</ol>
      <p class="gmore">All starters</p></summary>
      <div class="gfull">${side(g, g.away)}${side(g, g.home)}</div>
      <p class="gmore"><a href="depth.html?team=${g.away}">${esc(NICK[g.away] || g.away)} depth chart</a> · <a href="depth.html?team=${g.home}">${esc(NICK[g.home] || g.home)} depth chart</a></p></details>`;
  }).join("");
}

init();
