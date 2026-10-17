import { $, esc, toObjs, dataVersion, getJSON, NICK, initSearch } from "./common.js";
import { STAT, BY_POS, GROUPS, fmt, sum, niceMax, wireTips, statPoints } from "./stats.js";
import { loadMeta, fillFooter } from "./foot.js";

// Compare up to 4 players over one shared season and week range.
// Each player keeps the color slot he was added with, so removing someone never repaints the rest.
const MAX = 4;
const SLOT_COLOR = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
const params = new URLSearchParams(location.search);
const state = {
  players: [],                       // { slot, id, name, position, team, seasons, weeks }
  season: params.get("season") || "",
  from: +params.get("from") || null,
  to: +params.get("to") || null,
  view: params.get("view") === "pg" ? "pg" : "tot",
};
const cache = new Map();

async function loadPlayer(id) {
  if (!cache.has(id)) {
    cache.set(id, getJSON(`data/players/${encodeURIComponent(id)}.json?v=${dataVersion()}`).then((P) => ({
      id: P.id, name: P.name, position: P.position, team: P.team, first: P.first, last: P.last,
      seasons: toObjs(P.seasons), weeks: toObjs(P.weeks),
    })));
  }
  return cache.get(id);
}

async function init() {
  loadMeta().then(fillFooter).catch(() => {});
  initSearch($("#c-pick"), {
    playersOnly: true,
    skip: (e) => state.players.some((p) => p.id === e.id),
    onPick: (e) => addPlayer(e.id),
  });
  $("#c-season").onchange = () => { state.season = $("#c-season").value; state.from = state.to = null; update(); };
  $("#c-from").onchange = () => { state.from = +$("#c-from").value; if (state.to < state.from) state.to = state.from; update(); };
  $("#c-to").onchange = () => { state.to = +$("#c-to").value; if (state.from > state.to) state.from = state.to; update(); };
  $("#c-full").onclick = () => { state.from = state.to = null; update(); };
  document.querySelectorAll("[data-cview]").forEach((b) => (b.onclick = () => { state.view = b.dataset.cview; update(); }));
  $("#c-chips").onclick = (e) => {
    const b = e.target.closest("[data-remove]");
    if (!b) return;
    state.players = state.players.filter((p) => p.id !== b.dataset.remove);
    update();
  };
  const ids = (params.get("ids") || "").split(",").map((s) => s.trim()).filter(Boolean).slice(0, MAX);
  const loaded = await Promise.all(ids.map((id) => loadPlayer(id).catch(() => null)));
  loaded.forEach((p, i) => p && state.players.push({ ...p, slot: i }));
  update(false);
}

async function addPlayer(id) {
  if (state.players.length >= MAX || state.players.some((p) => p.id === id)) return;
  let p;
  try { p = await loadPlayer(id); } catch (e) { return; }
  const used = new Set(state.players.map((x) => x.slot));
  const slot = [0, 1, 2, 3].find((s) => !used.has(s));
  state.players.push({ ...p, slot });
  // A new player who never played the chosen season moves the page to a season everyone shares.
  if (state.season && state.season !== "career" && !p.seasons.some((s) => String(s.season) === state.season)) state.season = "";
  update();
}

// ---------- state and URL ----------
function seasonsOffered() {
  const all = new Set();
  state.players.forEach((p) => p.seasons.forEach((s) => all.add(s.season)));
  return [...all].sort((a, b) => b - a);
}
function defaultSeason(list) {
  const shared = list.filter((s) => state.players.every((p) => p.seasons.some((x) => x.season === s)));
  return String(shared[0] ?? list[0] ?? "");
}
const weeksIn = (season) => (season >= 2021 ? 18 : 17);

function update(push = true) {
  const list = seasonsOffered();
  if (!state.season || (state.season !== "career" && !list.includes(+state.season))) state.season = defaultSeason(list);
  if (state.season === "career" && list.length === 0) state.season = "";
  // Built by hand so the id list keeps plain commas and reads cleanly when shared.
  const q = [];
  if (state.players.length) q.push("ids=" + ordered().map((p) => encodeURIComponent(p.id)).join(","));
  if (state.season) q.push(`season=${state.season}`);
  if (state.season !== "career" && state.from) q.push(`from=${state.from}`);
  if (state.season !== "career" && state.to) q.push(`to=${state.to}`);
  if (state.view === "pg") q.push("view=pg");
  history[push ? "pushState" : "replaceState"](null, "", `${location.pathname}${q.length ? "?" + q.join("&") : ""}`);
  render(list);
}
window.addEventListener("popstate", () => location.reload());

// ---------- render ----------
const ordered = () => [...state.players].sort((a, b) => a.slot - b.slot);

function render(list) {
  const players = ordered();
  document.title = players.length ? `${players.map((p) => p.name).join(" vs ")} | Stars of Sabotage` : "Compare players | Stars of Sabotage";
  // chips and picker
  $("#c-chips").innerHTML = players.map((p) => `<li class="chip" style="--c:${SLOT_COLOR[p.slot]}">
      <i aria-hidden="true"></i><a href="player.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a>
      <span class="meta">${esc(p.position)} · ${esc(p.team)}</span>
      <button type="button" data-remove="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">×</button></li>`).join("");
  $("#c-pick").hidden = players.length >= MAX;
  $("#c-pick-hint").textContent = players.length >= MAX ? "Four players is the limit. Remove one to add another."
    : players.length === 0 ? "Search for a player to start. Add up to four."
      : players.length === 1 ? "Add a second player to compare." : `Add up to ${MAX - players.length} more.`;
  $("#c-body").hidden = players.length === 0;
  $("#c-try").hidden = players.length > 0;
  if (!players.length) return;

  // controls
  const sel = $("#c-season");
  sel.innerHTML = list.map((s) => `<option value="${s}">${s}</option>`).join("") + `<option value="career">Career</option>`;
  sel.value = state.season;
  const career = state.season === "career";
  const season = career ? null : +state.season;
  $("#c-weeks").hidden = career;
  if (!career) {
    const n = weeksIn(season);
    const from = Math.min(state.from || 1, n), to = Math.min(state.to || n, n);
    const opts = (v) => Array.from({ length: n }, (_, i) => `<option value="${i + 1}"${i + 1 === v ? " selected" : ""}>Wk ${i + 1}</option>`).join("");
    $("#c-from").innerHTML = opts(from);
    $("#c-to").innerHTML = opts(to);
    $("#c-full").setAttribute("aria-pressed", String(!state.from && !state.to));
  }
  document.querySelectorAll("[data-cview]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.cview === state.view)));

  // rows in range for each player
  const range = (p) => {
    if (career) return p.weeks;
    const n = weeksIn(season), from = state.from || 1, to = state.to || n;
    return p.weeks.filter((w) => w.season === season && w.week >= from && w.week <= to);
  };
  const data = players.map((p) => ({ p, wk: range(p) }));

  // mixed positions notice
  const posGroup = (pos) => (pos === "FB" ? "RB" : pos);
  const groupsSeen = new Set(data.map((d) => posGroup(posOf(d.p, season))));
  $("#c-mixed").hidden = groupsSeen.size < 2;

  const scope = career ? "Career totals" : (!state.from && !state.to) ? `${season} full season` :
    `${season}, ${(state.from || 1) === (state.to || weeksIn(season)) ? `week ${state.from || 1}` : `weeks ${state.from || 1} to ${state.to || weeksIn(season)}`}`;
  $("#c-scope").textContent = `${scope}${state.view === "pg" ? ", per game" : ""}.`;

  $("#c-table").innerHTML = sideBySide(data, season);
  $("#c-chart-title").textContent = career ? "Sabotage points by season" : `${season} by week`;
  $("#c-chart").innerHTML = career ? seasonLines(data) : weekLines(data, season);
  wireTips($("#c-chart"));
  $("#c-break").innerHTML = breakdown(data);
}

function posOf(p, season) {
  const s = season ? p.seasons.find((x) => x.season === season) : null;
  return (s || p.seasons[p.seasons.length - 1] || { position: p.position }).position;
}

// Side-by-side table. The player with the most Sabotage in a row is marked.
function sideBySide(data, season) {
  const pg = state.view === "pg";
  const keys = [];
  for (const d of data) for (const k of BY_POS[posOf(d.p, season)] || []) if (!keys.includes(k)) keys.push(k);
  for (const k of Object.keys(STAT)) if (!keys.includes(k) && data.some((d) => sum(d.wk, STAT[k].n) > 0)) keys.push(k);
  const per = (v, g) => (pg ? (g ? v / g : null) : v);
  const dec = pg ? 1 : 0;
  const cell = (vals, render) => {
    const max = Math.max(...vals.filter((v) => v !== null));
    const lead = data.length > 1 && max > 0 && vals.filter((v) => v === max).length === 1;
    return vals.map((v, i) => {
      const on = lead && v === max;
      return `<td class="num${on ? " lead" : ""}${v === 0 ? " zero" : ""}">${render(v, i)}${on ? `<span class="sr-only"> (most)</span>` : ""}</td>`;
    }).join("");
  };
  const games = data.map((d) => d.wk.length);
  const head = `<tr><th scope="col">Stat</th>${data.map((d) => `<th scope="col" class="num pcol" style="--c:${SLOT_COLOR[d.p.slot]}"><i aria-hidden="true"></i>${esc(d.p.name)}</th>`).join("")}</tr>`;
  let body = `<tr><th scope="row">Games</th>${games.map((g) => `<td class="num">${g || `<span class="dim">none</span>`}</td>`).join("")}</tr>`;
  const totals = data.map((d) => sum(d.wk, "sabotage_pts"));
  body += `<tr class="totrow"><th scope="row">Sabotage points${pg ? " per game" : ""}</th>${cell(totals.map((t, i) => per(t, games[i])), (v) => (v === null ? "" : fmt(v, dec)))}</tr>`;
  for (const k of keys) {
    const s = STAT[k];
    const pts = data.map((d) => statPoints(d.wk, k));
    const ns = data.map((d) => sum(d.wk, s.n));
    body += `<tr><th scope="row">${esc(s.label)}</th>${cell(pts.map((v, i) => per(v, games[i])), (v, i) =>
      v === null ? "" : `${fmt(per(ns[i], games[i]), dec)}<small>${fmt(v, dec)} pts</small>`)}</tr>`;
  }
  return `<div class="table-wrap plain"><table class="cmp">${head}${body}</table></div>
    <p class="hint">Each cell shows the count, with the Sabotage points it produced underneath. Yellow marks the player with the most points in that row.</p>`;
}

// ---------- charts ----------
const W = 760, H = 280, M = { t: 16, r: 14, b: 34, l: 44 };

function lineChart(xs, xLabel, series, label) {
  const ymax = niceMax(Math.max(10, ...series.flatMap((s) => s.pts.map((p) => p.v))));
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const step = iw / xs.length;
  const X = (i) => M.l + step * i + step / 2;
  const Y = (v) => M.t + ih - (v / ymax) * ih;
  let s = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="${esc(label)}">`;
  for (let i = 0; i <= 4; i++) {
    const v = (ymax / 4) * i;
    s += `<line class="grid" x1="${M.l}" x2="${W - M.r}" y1="${Y(v)}" y2="${Y(v)}"/><text class="axis" x="${M.l - 6}" y="${Y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
  }
  const every = xs.length > 14 ? 2 : 1;
  xs.forEach((x, i) => { if (i % every === 0 || i === xs.length - 1) s += `<text class="axis" x="${X(i)}" y="${H - 14}" text-anchor="middle">${xLabel(x)}</text>`; });
  for (const sr of series) {
    // break the line where a player has no game (bye, injury, not on a roster yet)
    let run = [];
    const flush = () => { if (run.length > 1) s += `<polyline class="pline" stroke="${sr.color}" points="${run.join(" ")}"/>`; run = []; };
    xs.forEach((x, i) => {
      const p = sr.pts.find((q) => q.x === x);
      if (!p) return flush();
      run.push(`${X(i)},${Y(p.v)}`);
    });
    flush();
    for (const p of sr.pts) {
      const i = xs.indexOf(p.x);
      if (i >= 0) s += `<circle class="pdot" cx="${X(i)}" cy="${Y(p.v)}" r="4" fill="${sr.color}"/>`;
    }
  }
  xs.forEach((x, i) => {
    const lines = series.map((sr) => { const p = sr.pts.find((q) => q.x === x); return `${sr.name}: ${p ? `${fmt(p.v)} pts${p.note ? ` ${p.note}` : ""}` : "no game"}`; });
    s += `<rect class="hit" x="${M.l + step * i}" y="${M.t}" width="${step}" height="${ih}" data-tip="${esc(`${xLabel(x, true)}\n${lines.join("\n")}`)}"/>`;
  });
  s += `</svg>`;
  const legend = series.map((sr) => `<span><i style="background:${sr.color}"></i>${esc(sr.name)}</span>`).join("");
  return `<div class="legend">${legend}</div>${s}`;
}

function weekLines(data, season) {
  const n = weeksIn(season), from = state.from || 1, to = state.to || n;
  const xs = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  const series = data.map((d) => ({
    name: d.p.name, color: SLOT_COLOR[d.p.slot],
    pts: d.wk.map((w) => ({ x: w.week, v: w.sabotage_pts, note: `(${w.home === 0 ? "at" : "vs"} ${w.opponent_team})` })),
  }));
  return lineChart(xs, (x, long) => (long ? `Week ${x}` : String(x)), series, `Sabotage points by week, ${season}`);
}

function seasonLines(data) {
  const all = data.flatMap((d) => d.p.seasons.map((s) => s.season));
  const lo = Math.min(...all), hi = Math.max(...all);
  const xs = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  const series = data.map((d) => ({
    name: d.p.name, color: SLOT_COLOR[d.p.slot],
    pts: d.p.seasons.map((s) => ({ x: s.season, v: state.view === "pg" ? s.sabotage_pts / s.g : s.sabotage_pts, note: `in ${s.g} games` })),
  }));
  return lineChart(xs, (x, long) => (long ? String(x) : `'${String(x).slice(2)}`), series,
    `Sabotage points by season${state.view === "pg" ? ", per game" : ""}`);
}

// Where the points come from: one row per event group, one bar per player, all on one scale.
function breakdown(data) {
  const pg = state.view === "pg";
  const val = (d, gp) => { const t = d.wk.reduce((a, r) => a + gp.f(r), 0); return pg ? (d.wk.length ? t / d.wk.length : 0) : t; };
  const used = GROUPS.filter((gp) => data.some((d) => val(d, gp) > 0));
  if (!used.length) return `<p class="hint">No Sabotage points in this range.</p>`;
  const max = Math.max(...used.flatMap((gp) => data.map((d) => val(d, gp))));
  return `<div class="brk">${used.map((gp) => `<div class="brk-group"><p class="brk-label">${gp.label}</p>${data.map((d) => {
    const v = val(d, gp);
    return `<div class="brk-row"><span class="brk-name">${esc(d.p.name)}</span><span class="brk-bar"><span style="width:${max ? (v / max) * 100 : 0}%;background:${SLOT_COLOR[d.p.slot]}"></span></span><span class="brk-v">${fmt(v, pg ? 1 : 0)}</span></div>`;
  }).join("")}</div>`).join("")}</div>
  <p class="hint">${pg ? "Points per game" : "Total points"} from each kind of mistake. Every bar uses the same scale.</p>`;
}

init();
