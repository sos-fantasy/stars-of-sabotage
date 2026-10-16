// Shared helpers and the site-wide player and team search.

export const $ = (s, root = document) => root.querySelector(s);
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const toObjs = ({ cols, rows }) => rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
// Data version stamped on <body> at build time, so a new release never reads a stale file.
export const dataVersion = () => document.body.dataset.dv || "";
export const getJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });

export const NICK = {
  ARI: "Cardinals", ATL: "Falcons", BAL: "Ravens", BUF: "Bills", CAR: "Panthers", CHI: "Bears", CIN: "Bengals",
  CLE: "Browns", DAL: "Cowboys", DEN: "Broncos", DET: "Lions", GB: "Packers", HOU: "Texans", IND: "Colts",
  JAX: "Jaguars", KC: "Chiefs", LA: "Rams", LAC: "Chargers", LV: "Raiders", MIA: "Dolphins", MIN: "Vikings",
  NE: "Patriots", NO: "Saints", NYG: "Giants", NYJ: "Jets", PHI: "Eagles", PIT: "Steelers", SEA: "Seahawks",
  SF: "49ers", TB: "Buccaneers", TEN: "Titans", WAS: "Commanders",
};
export const CITY = {
  ARI: "Arizona", ATL: "Atlanta", BAL: "Baltimore", BUF: "Buffalo", CAR: "Carolina", CHI: "Chicago", CIN: "Cincinnati",
  CLE: "Cleveland", DAL: "Dallas", DEN: "Denver", DET: "Detroit", GB: "Green Bay", HOU: "Houston", IND: "Indianapolis",
  JAX: "Jacksonville", KC: "Kansas City", LA: "Los Angeles", LAC: "Los Angeles", LV: "Las Vegas", MIA: "Miami",
  MIN: "Minnesota", NE: "New England", NO: "New Orleans", NYG: "New York", NYJ: "New York", PHI: "Philadelphia",
  PIT: "Pittsburgh", SEA: "Seattle", SF: "San Francisco", TB: "Tampa Bay", TEN: "Tennessee", WAS: "Washington",
};

// ---------- search ----------
const SUFFIX = /\b(jr|sr|ii|iii|iv|v)\b/g;
export function norm(s) {
  return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[.'’`]/g, "").replace(/-/g, " ").replace(SUFFIX, " ").replace(/\s+/g, " ").trim();
}
function tokens(name) {
  const n = norm(name);
  const t = n.split(" ").filter(Boolean);
  return [...t, t.join("")];   // "smith njigba" also matches "smithnjigba"
}

let INDEX = null;
async function loadIndex() {
  if (INDEX) return INDEX;
  const raw = await getJSON(`data/search.json?v=${dataVersion()}`);
  const players = toObjs(raw).map((p) => ({ ...p, kind: "player", toks: tokens(p.name) }));
  const teams = Object.keys(NICK).map((code) => ({
    kind: "team", id: code, name: `${NICK[code]} defense`, pos: "DEF", team: code,
    toks: [...tokens(`${CITY[code]} ${NICK[code]}`), code.toLowerCase()],
  }));
  INDEX = { players, teams };
  return INDEX;
}

export function rank(index, query, pos = "ALL") {
  const q = norm(query);
  if (!q) return [];
  const qt = q.split(" ");
  const hit = (e) => qt.every((t) => e.toks.some((k) => k.startsWith(t)));
  const out = [];
  const pool = pos === "DEF" ? index.teams : pos === "ALL" ? [...index.teams, ...index.players] : index.players;
  for (const e of pool) {
    if (pos !== "ALL" && pos !== "DEF" && (e.pos === "FB" ? "RB" : e.pos) !== pos) continue;
    if (!hit(e)) continue;
    const full = norm(e.name);
    let score = 0;
    if (full === q) score += 100;
    else if (full.startsWith(q)) score += 40;
    if (e.kind === "team" && (e.id.toLowerCase() === q)) score += 120;
    if (e.kind === "player") score += (e.last - 1999) * 1.5 + Math.min(e.career_pts, 20000) / 2000;
    else score += 30;
    out.push([score, e]);
  }
  return out.sort((a, b) => b[0] - a[0]).slice(0, 8).map((x) => x[1]);
}

const hrefFor = (e) => (e.kind === "team" ? `defenses.html?team=${e.id}` : `player.html?id=${encodeURIComponent(e.id)}`);
const years = (e) => (e.first === e.last ? `${e.first}` : `${e.first} to ${e.last}`);

// Wires any [data-search] block: an input, a listbox, and optional position chips.
export function initSearch(root) {
  const input = $("input", root);
  const list = $("[role=listbox]", root);
  const chips = root.querySelectorAll("[data-spos]");
  let pos = "ALL", items = [], active = -1;
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
  const paint = () => {
    list.innerHTML = items.length
      ? items.map((e, i) => `<li role="option" id="${list.id}-${i}" aria-selected="${i === active}"><a href="${hrefFor(e)}">
          <span class="nm">${esc(e.name)}</span><span class="meta">${esc(e.pos)} · ${esc(e.team || "")}${e.kind === "player" ? " · " + years(e) : ""}</span></a></li>`).join("")
      : `<li class="none">No match. Try a last name or a team.</li>`;
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    input.setAttribute("aria-activedescendant", active >= 0 ? `${list.id}-${active}` : "");
  };
  const run = async () => {
    const idx = await loadIndex().catch(() => null);
    if (!idx) return;
    items = rank(idx, input.value, pos);
    active = items.length ? 0 : -1;
    if (!input.value.trim()) return close();
    paint();
  };
  let t;
  input.addEventListener("focus", () => loadIndex().catch(() => {}), { once: true });
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(run, 80); });
  input.addEventListener("keydown", (e) => {
    if (list.hidden && e.key !== "Enter") return;
    if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(items.length - 1, active + 1); paint(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); paint(); }
    else if (e.key === "Enter") { e.preventDefault(); if (items[active]) location.href = hrefFor(items[active]); }
    else if (e.key === "Escape") { close(); }
  });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) close(); });
  chips.forEach((c) => c.addEventListener("click", () => {
    pos = c.dataset.spos;
    chips.forEach((x) => x.setAttribute("aria-pressed", x === c));
    input.focus();
    if (input.value.trim()) run();
  }));
}

document.querySelectorAll("[data-search]").forEach(initSearch);
