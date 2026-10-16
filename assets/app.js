import { loadMeta, fillFooter, fmtET, STATUS_TEXT } from "./foot.js";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K", "DEF"];
const posGroup = (p) => (p === "FB" ? "RB" : p);

// Column definitions. `f` is the field on an aggregated row. `pg` = can show per game.
const BASE = [
  { key: "rank", label: "#", cls: "rank sticky", sortable: false },
  { key: "name", label: "Player", cls: "player sticky", text: true },
  { key: "total", label: "Total", num: true, group: "Sabotage pts", cls: "total grp-start" },
  { key: "pergame", label: "Per G", num: true, group: "Sabotage pts", dec: 1 },
  { key: "pos", label: "Pos", text: true, cls: "grp-start" },
  { key: "team", label: "Team", text: true },
  { key: "g", label: "G", num: true, title: "Games with a stat line in the selected weeks" },
];
const PTS = [
  { key: "pts_incomplete", label: "Inc", title: "Points from incomplete passes" },
  { key: "pts_sacks", label: "Sack", title: "Points from sacks taken" },
  { key: "pts_carries", label: "Rush", title: "Points from rushing attempts" },
  { key: "pts_receptions", label: "Rec", title: "Points from receptions" },
  { key: "pts_fumbles", label: "Fum", title: "Points from fumbles and lost fumbles" },
  { key: "pts_ints", label: "INT", title: "Points from interceptions and pick sixes" },
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

const PLAYER_ONLY = new Set([...PTS, ...CNT].map((c) => c.key).filter((k) => !["pts_def", "points_allowed"].includes(k)));
const DEF_ONLY = new Set(["pts_def", "points_allowed"]);

const DEFAULTS = { from: null, to: null, pos: "ALL", team: "", view: "total", cols: "pts", min: 0, q: "", sort: [] };
const state = { ...DEFAULTS };
let DATA = null;

// ---------- load ----------
async function init() {
  let meta;
  try {
    meta = await loadMeta();
    const season = meta.season;
    const [s, d] = await Promise.all([
      fetch(`data/scores-${season}.json`).then((r) => r.json()),
      fetch(`data/defense-${season}.json`).then((r) => r.json()),
    ]);
    DATA = { meta, players: toObjs(s), defense: toObjs(d) };
  } catch (e) {
    $("#board tbody").innerHTML = `<tr><td class="loading">Could not load the data. Try again in a minute.</td></tr>`;
    return;
  }
  fillFooter(meta);
  renderWeekline(meta);
  renderStories(meta);
  setupControls(meta);
  readURL();
  syncControls();
  render();
}
const toObjs = ({ cols, rows }) => rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));

// ---------- header bits ----------
function renderWeekline(meta) {
  const played = meta.weeks.filter((w) => w.status !== "upcoming");
  const finals = played.filter((w) => w.status === "final").map((w) => w.week);
  const parts = [];
  if (finals.length) parts.push(`<span class="badge final">Weeks ${rangeText(finals)} final</span>`);
  for (const w of played.filter((w) => w.status !== "final")) {
    let t = `Week ${w.week} ${STATUS_TEXT[w.status]}`;
    if (w.status === "in_progress") t += `: ${w.games_done} of ${w.games} games`;
    if (w.status === "provisional" && w.final_at) t += ` until ${fmtET(w.final_at, false)}`;
    parts.push(`<span class="badge ${w.status}">${esc(t)}</span>`);
  }
  parts.push(`<span>Updated ${esc(fmtET(meta.updated_at))}</span>`);
  $("#weekline").innerHTML = parts.join("");
}
function rangeText(ws) {
  ws = [...ws].sort((a, b) => a - b);
  const contiguous = ws.every((w, i) => i === 0 || w === ws[i - 1] + 1);
  return contiguous && ws.length > 1 ? `${ws[0]} to ${ws[ws.length - 1]}` : ws.join(", ");
}

function renderStories(meta) {
  const h = meta.highlights;
  if (!h || !h.stories || !h.stories.length) return;
  $("#wreck-week").textContent = `Week ${h.week}`;
  if (h.status && h.status !== "final") $("#wreck-week").textContent += ` (${STATUS_TEXT[h.status]})`;
  $("#wreck-grid").innerHTML = h.stories
    .map(
      (s) => `<article class="story"><p class="label">${esc(s.label)}</p>
      <h3 class="who">${esc(s.who)}${s.team && !s.who.endsWith("defense") ? `<small>${esc(s.team)}</small>` : ""}</h3>
      <p class="text">${esc(s.text)}</p></article>`
    )
    .join("");
  $("#wreck").hidden = false;
}

// ---------- controls ----------
function setupControls(meta) {
  const weeks = meta.weeks.filter((w) => w.status !== "upcoming").map((w) => w.week);
  DEFAULTS.from = weeks[0] ?? 1;
  DEFAULTS.to = weeks[weeks.length - 1] ?? 1;
  const opts = weeks.map((w) => `<option value="${w}">Wk ${w}</option>`).join("");
  $("#f-from").innerHTML = opts;
  $("#f-to").innerHTML = opts;
  const teams = [...new Set([...DATA.players.map((r) => r.team), ...DATA.defense.map((r) => r.team)])].sort();
  $("#f-team").innerHTML += teams.map((t) => `<option>${esc(t)}</option>`).join("");
  const box = document.createElement("div");
  box.innerHTML = POSITIONS.map((p) => `<button type="button" data-pos="${p}" aria-pressed="false">${p === "ALL" ? "All" : p}</button>`).join("");
  $("#f-pos").appendChild(box);

  $("#f-from").onchange = (e) => { state.from = +e.target.value; if (state.to < state.from) state.to = state.from; update(); };
  $("#f-to").onchange = (e) => { state.to = +e.target.value; if (state.from > state.to) state.from = state.to; update(); };
  $("#f-team").onchange = (e) => { state.team = e.target.value; update(); };
  $("#f-min").oninput = (e) => { state.min = Math.max(0, +e.target.value || 0); update(); };
  let t;
  $("#f-q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); update(); }, 120); };
  box.onclick = (e) => { const b = e.target.closest("button"); if (b) { state.pos = b.dataset.pos; update(); } };
  document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; state.sort = []; update(); }));
  document.querySelectorAll("[data-cols]").forEach((b) => (b.onclick = () => { state.cols = b.dataset.cols; state.sort = state.sort.filter((s) => colDefs().some((c) => c.key === s.key)); update(); }));
  $("#b-reset").onclick = () => { Object.assign(state, { ...DEFAULTS, sort: [] }); update(); };
  $("#b-csv").onclick = downloadCSV;
}

function syncControls() {
  $("#f-from").value = state.from;
  $("#f-to").value = state.to;
  $("#f-team").value = state.team;
  $("#f-min").value = state.min;
  if ($("#f-q").value !== state.q) $("#f-q").value = state.q;
  document.querySelectorAll("[data-pos]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.pos === state.pos));
  document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === state.view));
  document.querySelectorAll("[data-cols]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.cols === state.cols));
}

function update() { syncControls(); writeURL(); render(); }

// ---------- URL state ----------
function readURL() {
  Object.assign(state, { ...DEFAULTS, sort: [] });
  const p = new URLSearchParams(location.search);
  const ws = DATA.meta.weeks.filter((w) => w.status !== "upcoming").map((w) => w.week);
  const wk = (v, d) => (ws.includes(+v) ? +v : d);
  if (p.has("from")) state.from = wk(p.get("from"), DEFAULTS.from);
  if (p.has("to")) state.to = wk(p.get("to"), DEFAULTS.to);
  if (state.from > state.to) [state.from, state.to] = [state.to, state.from];
  if (POSITIONS.includes(p.get("pos"))) state.pos = p.get("pos");
  if (p.get("team")) state.team = p.get("team");
  if (p.get("view") === "pg") state.view = "pg";
  if (p.get("cols") === "cnt") state.cols = "cnt";
  if (p.get("min")) state.min = Math.max(0, +p.get("min") || 0);
  if (p.get("q")) state.q = p.get("q");
  if (p.get("sort")) {
    const keys = new Set(colDefs().map((c) => c.key));
    state.sort = p.get("sort").split(",").map((s) => { const [key, d] = s.split("."); return { key, dir: d === "a" ? "asc" : "desc" }; })
      .filter((s) => keys.has(s.key)).slice(0, 3);
  }
}
function writeURL() {
  const p = new URLSearchParams();
  if (state.from !== DEFAULTS.from) p.set("from", state.from);
  if (state.to !== DEFAULTS.to) p.set("to", state.to);
  if (state.pos !== "ALL") p.set("pos", state.pos);
  if (state.team) p.set("team", state.team);
  if (state.view !== "total") p.set("view", "pg");
  if (state.cols !== "pts") p.set("cols", "cnt");
  if (state.min) p.set("min", state.min);
  if (state.q) p.set("q", state.q);
  if (state.sort.length) p.set("sort", state.sort.map((s) => `${s.key}.${s.dir[0]}`).join(","));
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

// ---------- aggregation ----------
function aggregate() {
  const { from, to } = state;
  const inRange = (r) => r.week >= from && r.week <= to;
  const out = new Map();
  for (const r of DATA.players) {
    if (!inRange(r)) continue;
    let a = out.get(r.player_id);
    if (!a) {
      a = { id: r.player_id, name: r.player_display_name, pos: r.position, team: r.team, lastWeek: 0, g: 0, total: 0, isDef: false };
      for (const k of PLAYER_ONLY) a[k] = 0;
      out.set(r.player_id, a);
    }
    a.g += 1;
    a.total += r.sabotage_pts;
    for (const k of PLAYER_ONLY) a[k] += r[k] ?? 0;
    if (r.week >= a.lastWeek) { a.lastWeek = r.week; a.team = r.team; a.name = r.player_display_name; }
  }
  for (const r of DATA.defense) {
    if (!inRange(r)) continue;
    const id = "DEF-" + r.team;
    let a = out.get(id);
    if (!a) { a = { id, name: `${r.team} Defense`, pos: "DEF", team: r.team, g: 0, total: 0, pts_def: 0, points_allowed: 0, isDef: true }; out.set(id, a); }
    a.g += 1;
    a.total += r.sabotage_pts;
    a.pts_def += r.sabotage_pts;
    a.points_allowed += r.points_allowed;
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
function colDefs() { return [...BASE, ...(state.cols === "pts" ? PTS : CNT)]; }

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
      let x = value(a, c), y = value(b, c);
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
    if (cur[0].dir === first) state.sort = [{ key, dir: flip }];
    else state.sort = [];
  } else {
    state.sort = [{ key, dir: first }];
  }
  update();
}

// ---------- render ----------
let lastRows = [];
function render() {
  const defs = colDefs();
  const rows = sortRows(filtered(aggregate()));
  lastRows = rows;
  const active = state.sort.length ? state.sort : defaultSort();

  const groups = [];
  for (const c of defs) {
    const g = c.group || "";
    if (groups.length && groups[groups.length - 1].g === g) groups[groups.length - 1].n++;
    else groups.push({ g, n: 1, cls: c.cls || "" });
  }
  const groupRow = `<tr class="groups">${groups.map((g, i) =>
    `<th colspan="${g.n}" class="${i === 0 ? "" : "grp-start"}${g.g ? "" : ""}">${esc(g.g)}</th>`).join("")}</tr>`;
  const headRow = `<tr class="cols">${defs.map((c) => {
    const s = active.findIndex((x) => x.key === c.key);
    const sortAttr = c.sortable === false ? "" : ` aria-sort="${s === -1 ? "none" : active[s].dir === "asc" ? "ascending" : "descending"}"`;
    const arrow = s === -1 ? "" : `<span class="arrow" aria-hidden="true">${active[s].dir === "asc" ? "▲" : "▼"}</span>${active.length > 1 && state.sort.length > 1 ? `<span class="ord">${s + 1}</span>` : ""}`;
    const inner = c.sortable === false ? esc(c.label)
      : `<button type="button" data-sort="${c.key}"${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}${arrow}</button>`;
    return `<th scope="col" class="${c.cls || ""}${c.num ? " num" : ""}"${sortAttr}>${inner}</th>`;
  }).join("")}</tr>`;
  $("#board thead").innerHTML = groupRow + headRow;
  const gh = $("#board thead tr.groups").getBoundingClientRect().height;
  $("#board").style.setProperty("--grp-h", gh + "px");

  if (!rows.length) {
    $("#board tbody").innerHTML = `<tr><td colspan="${defs.length}" class="loading">No one matches these filters. Rare, in this league.</td></tr>`;
  } else {
    $("#board tbody").innerHTML = rows.map((r, i) => `<tr>${defs.map((c) => {
      if (c.key === "rank") return `<td class="rank sticky">${i + 1}</td>`;
      const v = value(r, c);
      const cls = [c.cls || "", c.num ? "num" : "", v === null ? "blank" : v === 0 ? "zero" : ""].join(" ").trim();
      if (c.key === "name") return `<td class="${cls}">${esc(r.name)}</td>`;
      return `<td class="${cls}">${fmt(v, c)}</td>`;
    }).join("")}</tr>`).join("");
  }
  const what = state.pos === "ALL" ? "players and defenses" : state.pos === "DEF" ? "defenses" : `${state.pos}s`;
  $("#count").textContent = `${rows.length} ${what}, weeks ${state.from === state.to ? state.from : `${state.from} to ${state.to}`}${state.view === "pg" ? ", per game" : ""}.`;
  document.querySelectorAll("#board [data-sort]").forEach((b) => (b.onclick = (e) => onSort(b.dataset.sort, e.shiftKey)));
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
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: `sabotage-${DATA.meta.season}-wk${state.from}-${state.to}${state.pos !== "ALL" ? "-" + state.pos : ""}.csv`,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

init();
