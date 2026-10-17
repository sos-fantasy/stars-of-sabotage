import { loadMeta, fillFooter, fmtET, STATUS_TEXT } from "./foot.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K", "DEF"];
const posGroup = (p) => (p === "FB" ? "RB" : p);

// ---------- columns ----------
const RANK = { key: "rank", label: "#", cls: "rank sticky", sortable: false };
const NAME = { key: "name", label: "Player", cls: "player sticky", text: true };
const SEASON_COL = { key: "season", label: "Year", num: true, cls: "grp-start", title: "Season" };
const YRS_COL = { key: "yrs", label: "Yrs", num: true, title: "Seasons with a stat line" };
const TOTALS = [
  { key: "total", label: "Total", num: true, group: "Sabotage pts", cls: "total grp-start" },
  { key: "pergame", label: "Per G", num: true, group: "Sabotage pts", dec: 1 },
];
const INFO = [
  { key: "pos", label: "Pos", text: true, cls: "grp-start" },
  { key: "team", label: "Team", text: true },
  { key: "g", label: "G", num: true, title: "Games with a stat line" },
];
const PTS = [
  { key: "pts_incomplete", label: "Inc", title: "Points from incomplete passes (2 each)" },
  { key: "pts_sacks", label: "Sack", title: "Points from sacks taken (5 each)" },
  { key: "pts_carries", label: "Rush", title: "Points from rushing attempts (1 each)" },
  { key: "pts_receptions", label: "Rec", title: "Points from receptions (2 each)" },
  { key: "pts_fumble", label: "Fum", title: "Points from fumbles (7 each, lost or not)" },
  { key: "pts_fumble_lost", label: "Lost", title: "Extra points when a fumble is lost (10 each)" },
  { key: "pts_int", label: "INT", title: "Points from interceptions (10 each)" },
  { key: "pts_pick_six", label: "Pk6", title: "Extra points when an interception is returned for a TD (21 each)" },
  { key: "pts_kicking", label: "Kick", title: "Points from missed and blocked field goals and PATs" },
  { key: "pts_def", label: "Def", title: "Points from points allowed (defenses)" },
].map((c) => ({ ...c, num: true, pg: true, group: "Points by event" }));
const CNT = [
  { key: "n_incomplete", label: "Inc", title: "Incomplete passes" },
  { key: "n_sacks", label: "Sk", title: "Sacks taken" },
  { key: "n_carries", label: "Car", title: "Rushing attempts" },
  { key: "n_receptions", label: "Rec", title: "Receptions" },
  { key: "n_fumbles", label: "Fum", title: "Fumbles" },
  { key: "n_fumbles_lost", label: "Lost", title: "Fumbles lost" },
  { key: "n_ints", label: "INT", title: "Interceptions thrown" },
  { key: "n_pick_sixes", label: "Pk6", title: "Pick sixes thrown" },
  { key: "n_fg_missed", label: "FGx", title: "Field goals missed or blocked" },
  { key: "n_pat_missed", label: "PATx", title: "Extra points missed or blocked" },
  { key: "points_allowed", label: "PA", title: "Points allowed (Yahoo rule; defenses)" },
].map((c) => ({ ...c, num: true, pg: true, group: "Raw stats" }));
PTS[0].cls = CNT[0].cls = "grp-start";

const DEF_ONLY = new Set(["pts_def", "points_allowed"]);
const PLAYER_ONLY = new Set([...PTS, ...CNT].map((c) => c.key).filter((k) => !DEF_ONLY.has(k)));

// ---------- state ----------
const DEFAULTS = { season: null, from: null, to: null, rows: "career", pos: "ALL", team: "", view: "total", cols: "pts", min: 0, q: "", sort: [] };
const state = { ...DEFAULTS };
const DATA = { meta: null, seasons: [], weekly: new Map(), careerRows: null, seasonRows: null };
const isAll = () => state.season === "all";
const seasonInfo = (s) => DATA.seasons.find((x) => x.season === s);

// ---------- load ----------
const toObjs = ({ cols, rows }) => rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
// Current-season and summary files change with the data, so they carry the data hash.
// Past seasons only change when the scoring rules do, so they carry the rules version.
const dv = () => DATA.meta?.data_hash || "";
const sv = (s) => (s === DATA.meta?.season ? dv() : DATA.meta?.scoring_version || "");
const getJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });

async function ensureData() {
  if (isAll()) {
    // Career view reads a small precomputed file; single-season rows need the full list.
    const key = state.rows === "season" ? "seasonRows" : "careerRows";
    if (!DATA[key]) {
      const [pf, df] = state.rows === "season" ? ["player-seasons", "defense-seasons"] : ["player-careers", "defense-careers"];
      const [p, d] = await Promise.all([getJSON(`data/${pf}.json?v=${dv()}`), getJSON(`data/${df}.json?v=${dv()}`)]);
      DATA[key] = { players: toObjs(p), defense: toObjs(d) };
    }
    return;
  }
  if (!DATA.weekly.has(state.season)) {
    const [p, d] = await Promise.all([getJSON(`data/scores-${state.season}.json?v=${sv(state.season)}`), getJSON(`data/defense-${state.season}.json?v=${sv(state.season)}`)]);
    DATA.weekly.set(state.season, { players: toObjs(p), defense: toObjs(d) });
  }
}

async function init() {
  try {
    // The page ships with meta and the season list baked in, saving two round trips.
    const boot = document.getElementById("boot");
    const baked = boot ? JSON.parse(boot.textContent) : null;
    const meta = baked?.meta || (await loadMeta());
    DATA.meta = meta;
    DATA.seasons = baked?.seasons || (await getJSON(`data/seasons.json?v=${dv()}`));
    DEFAULTS.season = meta.season;
  } catch (e) {
    return fail();
  }
  fillFooter(DATA.meta);
  renderStories(DATA.meta);
  setupControls();
  initTray();
  readURL();
  await go();
  window.addEventListener("popstate", async () => { readURL(); await go(null); });
}
function fail() {
  $("#board tbody").innerHTML = `<tr><td class="loading">Could not load the data. Try again in a minute.</td></tr>`;
}

async function go(push = true) {
  limit = PAGE;
  $("#board").setAttribute("aria-busy", "true");
  try { await ensureData(); } catch (e) { return fail(); }
  fixWeeks();
  syncControls();
  if (push !== null) writeURL(push);
  renderWeekline();
  render();
  $("#board").removeAttribute("aria-busy");
}

// ---------- header bits ----------
function weeksPlayed(season) {
  if (season === DATA.meta.season) return DATA.meta.weeks.filter((w) => w.status !== "upcoming").map((w) => w.week);
  const n = seasonInfo(season)?.weeks || 0;
  return Array.from({ length: n }, (_, i) => i + 1);
}

function renderWeekline() {
  const meta = DATA.meta;
  const parts = [];
  if (isAll()) {
    const first = DATA.seasons[DATA.seasons.length - 1].season;
    parts.push(`<span class="badge final">${first} to ${meta.season}, ${DATA.seasons.length} seasons</span>`);
  } else if (state.season !== meta.season) {
    parts.push(`<span class="badge final">${state.season} season final, ${seasonInfo(state.season).weeks} weeks</span>`);
  } else {
    const played = meta.weeks.filter((w) => w.status !== "upcoming");
    const finals = played.filter((w) => w.status === "final").map((w) => w.week);
    if (finals.length) parts.push(`<span class="badge final">Weeks ${rangeText(finals)} final</span>`);
    for (const w of played.filter((w) => w.status !== "final")) {
      let t = `Week ${w.week} ${STATUS_TEXT[w.status]}`;
      if (w.status === "in_progress") t += `: ${w.games_done} of ${w.games} games`;
      if (w.status === "provisional" && w.final_at) t += ` until ${fmtET(w.final_at, false)}`;
      parts.push(`<span class="badge ${w.status}">${esc(t)}</span>`);
    }
  }
  parts.push(`<span>Updated ${esc(fmtET(meta.updated_at))}</span>`);
  $("#weekline").innerHTML = parts.join("");
  const past = isAll() || state.season !== meta.season;
  $("#histnote").hidden = !past;
  $("#wreck").hidden = past || !((meta.highlights?.stories?.length || 0) + (meta.highlights?.records?.length || 0));
}
function rangeText(ws) {
  ws = [...ws].sort((a, b) => a - b);
  const contiguous = ws.every((w, i) => i === 0 || w === ws[i - 1] + 1);
  return contiguous && ws.length > 1 ? `${ws[0]} to ${ws[ws.length - 1]}` : ws.join(", ");
}

function renderStories(meta) {
  const h = meta.highlights;
  const alerts = h?.records || [];
  if (!h || (!(h.stories || []).length && !alerts.length)) return;
  $("#wreck-week").textContent = h.week ? `Week ${h.week}` : "This week's";
  if (h.status && h.status !== "final") $("#wreck-week").textContent += ` (${STATUS_TEXT[h.status]})`;
  const recCards = alerts.map((a) => `<article class="story alert${a.official ? " official" : ""}">
      <p class="label">${esc(a.title)}<span class="scope">${a.scope === "game" ? "Single game" : "Single season"}, Week ${a.week}</span></p>
      <h3 class="who">${esc(a.who)}${a.team && !a.who.endsWith("defense") ? `<small>${esc(a.team)}</small>` : ""}</h3>
      <p class="rec-line"><span class="num">${a.value.toLocaleString()}</span> ${esc(a.unit)} <span class="was">old mark ${a.previous.toLocaleString()}</span></p>
      <p class="text">${esc(a.text)}</p>
      <p class="more"><a href="super-stars.html">See every record</a></p></article>`);
  const storyCards = (h.stories || []).map((s) => `<article class="story"><p class="label">${esc(s.label)}</p>
      <h3 class="who">${esc(s.who)}${s.team && !s.who.endsWith("defense") ? `<small>${esc(s.team)}</small>` : ""}</h3>
      <p class="text">${esc(s.text)}</p></article>`);
  $("#wreck-grid").innerHTML = [...recCards, ...storyCards].join("");
}

// ---------- controls ----------
function setupControls() {
  $("#f-season").innerHTML =
    DATA.seasons.map((s) => `<option value="${s.season}">${s.season}${s.season === DATA.meta.season ? " (current)" : ""}</option>`).join("") +
    `<option value="all">All seasons</option>`;
  const box = document.createElement("div");
  box.innerHTML = POSITIONS.map((p) => `<button type="button" data-pos="${p}" aria-pressed="false">${p === "ALL" ? "All" : p}</button>`).join("");
  $("#f-pos").appendChild(box);

  $("#f-season").onchange = (e) => {
    state.season = e.target.value === "all" ? "all" : +e.target.value;
    state.from = state.to = null;   // full season by default
    state.team = "";
    state.sort = state.sort.filter((s) => colDefs().some((c) => c.key === s.key));
    go();
  };
  $("#f-from").onchange = (e) => { state.from = +e.target.value; if (state.to < state.from) state.to = state.from; update(); };
  $("#f-to").onchange = (e) => { state.to = +e.target.value; if (state.from > state.to) state.from = state.to; update(); };
  $("#b-full").onclick = () => { state.from = state.to = null; fixWeeks(); update(); };
  $("#f-team").onchange = (e) => { state.team = e.target.value; update(); };
  $("#f-min").oninput = (e) => { state.min = Math.max(0, +e.target.value || 0); update(); };
  let t;
  $("#f-q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); update(); }, 120); };
  box.onclick = (e) => { const b = e.target.closest("button"); if (b) { state.pos = b.dataset.pos; update(); } };
  document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; state.sort = []; update(); }));
  document.querySelectorAll("[data-cols]").forEach((b) => (b.onclick = () => { state.cols = b.dataset.cols; dropBadSorts(); update(); }));
  document.querySelectorAll("[data-rows]").forEach((b) => (b.onclick = () => { state.rows = b.dataset.rows; dropBadSorts(); go(false); }));
  $("#b-reset").onclick = () => { Object.assign(state, { ...DEFAULTS, sort: [] }); go(); };
  $("#b-csv").onclick = downloadCSV;
  $("#b-more").onclick = () => { limit += PAGE; render(); };
}
function dropBadSorts() { state.sort = state.sort.filter((s) => colDefs().some((c) => c.key === s.key)); }

function fixWeeks() {
  if (isAll()) return;
  const ws = weeksPlayed(state.season);
  const lo = ws[0] ?? 1, hi = ws[ws.length - 1] ?? 1;
  if (state.from === null || !ws.includes(state.from)) state.from = lo;
  if (state.to === null || !ws.includes(state.to)) state.to = hi;
  if (state.from > state.to) [state.from, state.to] = [state.to, state.from];
  const opts = ws.map((w) => `<option value="${w}">Wk ${w}</option>`).join("");
  if ($("#f-from").dataset.season !== String(state.season)) {
    $("#f-from").innerHTML = $("#f-to").innerHTML = opts;
    $("#f-from").dataset.season = String(state.season);
  }
}
function isFullSeason() {
  if (isAll()) return true;
  const ws = weeksPlayed(state.season);
  return state.from === ws[0] && state.to === ws[ws.length - 1];
}

function syncControls() {
  $("#f-season").value = String(state.season);
  $("#weeks-ctl").hidden = isAll();
  $("#rows-ctl").hidden = !isAll();
  if (!isAll()) { $("#f-from").value = state.from; $("#f-to").value = state.to; }
  $("#b-full").setAttribute("aria-pressed", isFullSeason());
  const teams = teamList();
  const cur = $("#f-team").dataset.list;
  if (cur !== teams.join(",")) {
    $("#f-team").innerHTML = `<option value="">All teams</option>` + teams.map((t) => `<option>${esc(t)}</option>`).join("");
    $("#f-team").dataset.list = teams.join(",");
  }
  if (state.team && !teams.includes(state.team)) state.team = "";
  $("#f-team").value = state.team;
  $("#f-min").value = state.min;
  if ($("#f-q").value !== state.q) $("#f-q").value = state.q;
  document.querySelectorAll("[data-pos]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.pos === state.pos));
  document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === state.view));
  document.querySelectorAll("[data-cols]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.cols === state.cols));
  document.querySelectorAll("[data-rows]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.rows === state.rows));
}
function teamList() {
  const src = isAll() ? (state.rows === "season" ? DATA.seasonRows : DATA.careerRows) : DATA.weekly.get(state.season);
  if (!src) return [];
  return [...new Set([...src.players.map((r) => r.team), ...src.defense.map((r) => r.team)])].filter(Boolean).sort();
}

function update() { limit = PAGE; syncControls(); writeURL(false); render(); }

// ---------- URL state ----------
function readURL() {
  Object.assign(state, { ...DEFAULTS, sort: [] });
  const p = new URLSearchParams(location.search);
  const s = p.get("season");
  if (s === "all") state.season = "all";
  else if (s && seasonInfo(+s)) state.season = +s;
  if (p.has("from")) state.from = +p.get("from") || null;
  if (p.has("to")) state.to = +p.get("to") || null;
  if (p.get("rows") === "season") state.rows = "season";
  if (POSITIONS.includes(p.get("pos"))) state.pos = p.get("pos");
  if (p.get("team")) state.team = p.get("team");
  if (p.get("view") === "pg") state.view = "pg";
  if (p.get("cols") === "cnt") state.cols = "cnt";
  if (p.get("min")) state.min = Math.max(0, +p.get("min") || 0);
  if (p.get("q")) state.q = p.get("q");
  if (p.get("sort")) {
    const keys = new Set(colDefs().map((c) => c.key));
    state.sort = p.get("sort").split(",").map((x) => { const [key, d] = x.split("."); return { key, dir: d === "a" ? "asc" : "desc" }; })
      .filter((x) => keys.has(x.key)).slice(0, 3);
  }
}
function writeURL(push) {
  const p = new URLSearchParams();
  if (state.season !== DEFAULTS.season) p.set("season", state.season);
  if (!isAll() && !isFullSeason()) { p.set("from", state.from); p.set("to", state.to); }
  if (isAll() && state.rows === "season") p.set("rows", "season");
  if (state.pos !== "ALL") p.set("pos", state.pos);
  if (state.team) p.set("team", state.team);
  if (state.view !== "total") p.set("view", "pg");
  if (state.cols !== "pts") p.set("cols", "cnt");
  if (state.min) p.set("min", state.min);
  if (state.q) p.set("q", state.q);
  if (state.sort.length) p.set("sort", state.sort.map((s) => `${s.key}.${s.dir[0]}`).join(","));
  const qs = p.toString();
  const url = qs ? `?${qs}` : location.pathname;
  const now = location.search || location.pathname;
  if (url === now) return;
  history[push ? "pushState" : "replaceState"](null, "", url);
}

// ---------- aggregation ----------
function blankPlayer(r, id) {
  const a = { id, pid: r.player_id, name: r.player_display_name, pos: r.position, team: r.team, g: 0, total: 0, isDef: false, last: -1 };
  for (const k of PLAYER_ONLY) a[k] = 0;
  return a;
}
function addPlayer(a, r, order) {
  a.g += r.g ?? 1;
  a.total += r.sabotage_pts;
  for (const k of PLAYER_ONLY) a[k] += r[k] ?? 0;
  if (order >= a.last) { a.last = order; a.team = r.team; a.name = r.player_display_name; a.pos = r.position; }
}
function addDef(a, r) {
  a.g += r.g ?? 1;
  a.total += r.sabotage_pts;
  a.pts_def += r.sabotage_pts;
  a.points_allowed += r.points_allowed;
}
const blankDef = (team, id) => ({ id, name: `${team} Defense`, pos: "DEF", team, g: 0, total: 0, pts_def: 0, points_allowed: 0, isDef: true });

let aggKey = "", aggRows = [];
function aggregate() {
  // Filters and sorts don't change the totals, so only re-total when the data scope changes.
  const key = isAll() ? `all|${state.rows}` : `${state.season}|${state.from}|${state.to}`;
  if (key === aggKey) return aggRows.slice();
  aggKey = key;
  aggRows = computeAggregate();
  return aggRows.slice();
}
function computeAggregate() {
  const out = new Map();
  if (isAll()) {
    const bySeason = state.rows === "season";
    const { players, defense } = bySeason ? DATA.seasonRows : DATA.careerRows;
    for (const r of players) {
      const id = bySeason ? `${r.player_id}|${r.season}` : r.player_id;
      let a = out.get(id);
      if (!a) { a = blankPlayer(r, id); a.seasons = new Set(); if (bySeason) a.season = r.season; out.set(id, a); }
      addPlayer(a, r, r.season ?? 0);
      if (r.season) a.seasons.add(r.season);
      if (r.yrs) a.yrsFile = r.yrs;
    }
    for (const r of defense) {
      const id = bySeason ? `DEF-${r.team}|${r.season}` : `DEF-${r.team}`;
      let a = out.get(id);
      if (!a) { a = blankDef(r.team, id); a.seasons = new Set(); if (bySeason) a.season = r.season; out.set(id, a); }
      addDef(a, r);
      if (r.season) a.seasons.add(r.season);
      if (r.yrs) a.yrsFile = r.yrs;
    }
    for (const a of out.values()) a.yrs = a.yrsFile ?? a.seasons.size;
  } else {
    const { players, defense } = DATA.weekly.get(state.season);
    const inRange = (r) => r.week >= state.from && r.week <= state.to;
    for (const r of players) {
      if (!inRange(r)) continue;
      let a = out.get(r.player_id);
      if (!a) { a = blankPlayer(r, r.player_id); out.set(r.player_id, a); }
      addPlayer(a, r, r.week);
    }
    for (const r of defense) {
      if (!inRange(r)) continue;
      const id = "DEF-" + r.team;
      let a = out.get(id);
      if (!a) { a = blankDef(r.team, id); out.set(id, a); }
      addDef(a, r);
    }
  }
  const rows = [...out.values()];
  for (const a of rows) a.pergame = a.g ? a.total / a.g : 0;
  return rows;
}

function filtered(rows) {
  const q = state.q.toLowerCase();
  return rows.filter((r) =>
    (state.pos === "ALL" || posGroup(r.pos) === state.pos) &&
    (!state.team || r.team === state.team) &&
    r.g >= state.min &&
    (!q || r.name.toLowerCase().includes(q) || r.team.toLowerCase() === q)
  );
}

// ---------- columns, values ----------
function colDefs() {
  const lead = [RANK, NAME, ...TOTALS];
  if (isAll() && state.rows === "season") lead.push(SEASON_COL);
  const info = [...INFO];
  if (isAll() && state.rows === "career") info.push(YRS_COL);
  return [...lead, ...info, ...(state.cols === "pts" ? PTS : CNT)];
}
function value(r, c) {
  if (c.key === "pergame") return r.pergame;
  if (r.isDef && PLAYER_ONLY.has(c.key)) return null;
  if (!r.isDef && DEF_ONLY.has(c.key)) return null;
  const v = r[c.key];
  if (c.pg && state.view === "pg" && typeof v === "number") return r.g ? v / r.g : 0;
  return v;
}
function fmt(v, c) {
  if (v === null || v === undefined) return "";
  if (typeof v !== "number") return esc(v);
  if (c.key === "season") return String(v);
  const dec = c.dec ?? (c.pg && state.view === "pg" ? 1 : 0);
  return v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

// ---------- sorting ----------
function defaultSort() { return [{ key: state.view === "pg" ? "pergame" : "total", dir: "desc" }]; }
function sortRows(rows) {
  const keys = (state.sort.length ? state.sort : defaultSort()).concat([{ key: "total", dir: "desc" }, { key: "name", dir: "asc" }]);
  const defs = Object.fromEntries(colDefs().map((c) => [c.key, c]));
  return rows.sort((a, b) => {
    for (const s of keys) {
      const c = defs[s.key] || { key: s.key };
      const x = value(a, c), y = value(b, c);
      if (x === y) continue;
      if (x === null || x === undefined) return 1;   // blanks always last
      if (y === null || y === undefined) return -1;
      const d = typeof x === "string" ? x.localeCompare(y) : x - y;
      if (d) return s.dir === "asc" ? d : -d;
    }
    return 0;
  });
}
function onSort(key, shift) {
  const c = colDefs().find((d) => d.key === key);
  const first = c.text ? "asc" : "desc";
  const flip = first === "asc" ? "desc" : "asc";
  const cur = state.sort.length ? state.sort : defaultSort();
  const i = cur.findIndex((s) => s.key === key);
  if (shift && state.sort.length) {
    if (i === -1) state.sort = [...state.sort, { key, dir: first }].slice(0, 3);
    else if (state.sort[i].dir === first) state.sort[i] = { key, dir: flip };
    else state.sort.splice(i, 1);
  } else if (i === 0) {
    state.sort = cur[0].dir === first ? [{ key, dir: flip }] : [];
  } else {
    state.sort = [{ key, dir: first }];
  }
  update();
}

// ---------- render ----------
const PAGE = 300;   // rows drawn at a time; phones slow down past a few hundred
let limit = PAGE;
let lastRows = [];
function render() {
  const defs = colDefs();
  const rows = sortRows(filtered(aggregate()));
  lastRows = rows;
  const shown = rows.slice(0, limit);
  const active = state.sort.length ? state.sort : defaultSort();

  const groups = [];
  for (const c of defs) {
    const g = c.group || "";
    if (groups.length && groups[groups.length - 1].g === g) groups[groups.length - 1].n++;
    else groups.push({ g, n: 1 });
  }
  const groupRow = `<tr class="groups">${groups.map((g, i) => `<th colspan="${g.n}" class="${i ? "grp-start" : ""}">${esc(g.g)}</th>`).join("")}</tr>`;
  const headRow = `<tr class="cols">${defs.map((c) => {
    const s = active.findIndex((x) => x.key === c.key);
    const sortAttr = c.sortable === false ? "" : ` aria-sort="${s === -1 ? "none" : active[s].dir === "asc" ? "ascending" : "descending"}"`;
    const arrow = s === -1 ? "" : `<span class="arrow" aria-hidden="true">${active[s].dir === "asc" ? "▲" : "▼"}</span>${state.sort.length > 1 ? `<span class="ord">${s + 1}</span>` : ""}`;
    const inner = c.sortable === false ? esc(c.label)
      : `<button type="button" data-sort="${c.key}"${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}${arrow}</button>`;
    return `<th scope="col" class="${c.cls || ""}${c.num ? " num" : ""}"${sortAttr}>${inner}</th>`;
  }).join("")}</tr>`;
  $("#board thead").innerHTML = groupRow + headRow;
  $("#board").style.setProperty("--grp-h", $("#board thead tr.groups").getBoundingClientRect().height + "px");

  if (!rows.length) {
    $("#board tbody").innerHTML = `<tr><td colspan="${defs.length}" class="loading">No one matches these filters. Rare, in this league.</td></tr>`;
  } else {
    $("#board tbody").innerHTML = shown.map((r, i) => `<tr>${defs.map((c) => {
      if (c.key === "rank") return `<td class="rank sticky">${i + 1}</td>`;
      const v = value(r, c);
      const cls = [c.cls || "", c.num ? "num" : "", v === null ? "blank" : v === 0 ? "zero" : ""].join(" ").trim();
      if (c.key === "name") return `<td class="${cls}"><a class="plink" href="${esc(rowLink(r))}">${esc(r.name)}</a>${r.isDef ? "" :
        `<button type="button" class="cadd" data-cmp="${esc(r.pid)}" data-name="${esc(r.name)}" aria-pressed="${tray.has(r.pid)}" title="Add to compare" aria-label="Compare ${esc(r.name)}">+</button>`}</td>`;
      return `<td class="${cls}">${fmt(v, c)}</td>`;
    }).join("")}</tr>`).join("");
  }
  const what = state.pos === "ALL" ? "players and defenses" : state.pos === "DEF" ? "defenses" : `${state.pos}s`;
  let scope;
  if (isAll()) scope = state.rows === "season" ? "single seasons, all years" : "career totals, all seasons";
  else scope = isFullSeason() ? `${state.season} full season` : `${state.season}, ${state.from === state.to ? `week ${state.from}` : `weeks ${state.from} to ${state.to}`}`;
  const capped = rows.length > shown.length ? ` Showing the top ${shown.length.toLocaleString()}.` : "";
  const more = $("#b-more");
  more.hidden = rows.length <= shown.length;
  more.textContent = `Show ${Math.min(PAGE, rows.length - shown.length).toLocaleString()} more`;
  $("#count").textContent = `${rows.length.toLocaleString()} ${isAll() && state.rows === "season" ? "rows" : what}, ${scope}${state.view === "pg" ? ", per game" : ""}.${capped}`;
  document.querySelectorAll("#board [data-sort]").forEach((b) => (b.onclick = (e) => onSort(b.dataset.sort, e.shiftKey)));
  if (tray.size) paintTray();
}

// ---------- compare tray: pick up to 4 players from the table ----------
const tray = new Map();
function initTray() {
  const el = document.createElement("div");
  el.id = "cmp-tray"; el.className = "tray"; el.hidden = true;
  el.setAttribute("role", "region"); el.setAttribute("aria-label", "Players to compare");
  document.body.appendChild(el);
  $("#board tbody").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cmp]");
    if (!b) return;
    const id = b.dataset.cmp;
    if (tray.has(id)) tray.delete(id); else if (tray.size < 4) tray.set(id, b.dataset.name);
    b.setAttribute("aria-pressed", String(tray.has(id)));
    paintTray();
  });
  el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-untray]");
    if (b) { tray.delete(b.dataset.untray); paintTray(); render(); }
    if (e.target.closest("[data-clear]")) { tray.clear(); paintTray(); render(); }
  });
}
function paintTray() {
  const el = $("#cmp-tray");
  el.hidden = tray.size === 0;
  const season = isAll() ? "career" : state.season;
  const href = `compare.html?ids=${[...tray.keys()].map(encodeURIComponent).join(",")}&season=${season}`;
  el.innerHTML = `<div class="tray-in"><span class="lbl">Compare</span>${[...tray].map(([id, n]) =>
    `<span class="tchip">${esc(n)}<button type="button" data-untray="${esc(id)}" aria-label="Remove ${esc(n)}">×</button></span>`).join("")}
    <span class="tnote">${tray.size < 2 ? "Pick one more with +" : tray.size === 4 ? "Four is the limit" : ""}</span>
    <button type="button" class="tclear" data-clear>Clear</button>
    <a class="btn${tray.size < 2 ? " off" : ""}" href="${href}">Compare ${tray.size}</a></div>`;
}

function rowLink(r) {
  const season = isAll() ? (state.rows === "season" ? r.season : null) : state.season;
  if (r.isDef) return `defenses.html?team=${r.team}${season ? `&season=${season}` : ""}`;
  return `player.html?id=${encodeURIComponent(r.pid)}${isAll() && state.rows === "career" ? "&season=career" : season ? `&season=${season}` : ""}`;
}

function downloadCSV() {
  const defs = colDefs();
  const cell = (s) => (/[",\n]/.test(s) ? `"${String(s).replace(/"/g, '""')}"` : s);
  const lines = [defs.map((c) => cell(c.title || c.label)).join(",")];
  lastRows.forEach((r, i) => lines.push(defs.map((c) => {
    if (c.key === "rank") return i + 1;
    const v = value(r, c);
    if (v === null || v === undefined) return "";
    return typeof v === "number" ? +v.toFixed(c.dec ?? (c.pg && state.view === "pg" ? 2 : 0)) : cell(v);
  }).join(",")));
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const span = isAll() ? `all-${state.rows}` : isFullSeason() ? `${state.season}` : `${state.season}-wk${state.from}-${state.to}`;
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: `sabotage-${span}${state.pos !== "ALL" ? "-" + state.pos : ""}.csv`,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

init();
