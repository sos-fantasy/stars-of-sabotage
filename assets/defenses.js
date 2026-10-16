import { $, esc, toObjs, dataVersion, getJSON, NICK, CITY } from "./common.js?v=e89b39acdc";
import { loadMeta, fillFooter } from "./foot.js?v=949d944f7b";

const BUCKETS = ["0", "1-6", "7-13", "14-20", "21-27", "28-34", "35+"];
const params = new URLSearchParams(location.search);
let meta = null, seasons = [], sortKey = "pts", sortDir = "desc", scrolled = false;
const cache = new Map();

async function init() {
  try {
    meta = await loadMeta();
    seasons = await getJSON(`data/seasons.json?v=${dataVersion()}`);
  } catch (e) {
    $("#d-table").innerHTML = `<p class="loading">Could not load the data. Try again in a minute.</p>`;
    return;
  }
  fillFooter(meta);
  const sel = $("#d-season");
  sel.innerHTML = seasons.map((s) => `<option value="${s.season}">${s.season}${s.season === meta.season ? " (current)" : ""}</option>`).join("");
  const want = +params.get("season");
  sel.value = seasons.some((s) => s.season === want) ? String(want) : String(meta.season);
  sel.onchange = () => { const u = new URL(location.href); u.searchParams.set("season", sel.value); history.replaceState(null, "", u); render(); };
  render();
}

async function load(season) {
  if (!cache.has(season)) {
    const v = season === meta.season ? meta.data_hash : meta.scoring_version;
    const [d, g] = await Promise.all([getJSON(`data/defense-${season}.json?v=${v}`), getJSON(`data/games-${season}.json?v=${v}`)]);
    cache.set(season, { rows: toObjs(d), games: toObjs(g) });
  }
  return cache.get(season);
}

const fmt = (v, d = 0) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

async function render() {
  const season = +$("#d-season").value;
  const { rows, games } = await load(season);
  const maxWeek = Math.max(...games.map((g) => g.week));
  const teams = new Map();
  for (const r of rows) {
    let t = teams.get(r.team);
    if (!t) { t = { team: r.team, g: 0, pts: 0, pa: 0, weeks: new Map(), buckets: Object.fromEntries(BUCKETS.map((b) => [b, 0])) }; teams.set(r.team, t); }
    t.g++; t.pts += r.sabotage_pts; t.pa += r.points_allowed; t.buckets[r.pa_bucket]++;
    t.weeks.set(r.week, r);
  }
  const list = [...teams.values()].map((t) => ({ ...t, ppg: t.pts / t.g, papg: t.pa / t.g }));
  const dir = sortDir === "asc" ? 1 : -1;
  list.sort((a, b) => (sortKey === "team" ? a.team.localeCompare(b.team) * dir : (a[sortKey] - b[sortKey]) * dir || b.pts - a.pts || a.team.localeCompare(b.team)));

  // top five card
  const top = [...list].sort((a, b) => b.pts - a.pts || b.pa - a.pa).slice(0, 5);
  $("#d-top").innerHTML = top.map((t, i) => `<li><span class="rk">${i + 1}</span><span class="nm">${esc(CITY[t.team] || "")} ${esc(NICK[t.team] || t.team)}<small>${t.team} · ${fmt(t.papg, 1)} allowed per game</small></span><span class="v">${fmt(t.pts)}</span></li>`).join("");
  $("#d-top-title").textContent = `${season} most generous defenses`;

  // table
  const H = (k, label, num = true) => {
    const on = sortKey === k;
    return `<th scope="col" class="${num ? "num" : ""}" aria-sort="${on ? (sortDir === "asc" ? "ascending" : "descending") : "none"}"><button type="button" data-k="${k}">${label}${on ? `<span class="arrow">${sortDir === "asc" ? "▲" : "▼"}</span>` : ""}</button></th>`;
  };
  const focus = params.get("team");
  $("#d-table").innerHTML = `<div class="table-wrap plain"><table id="dtab"><thead><tr><th class="num">#</th>${H("team", "Defense", false)}${H("g", "G")}${H("pts", "Sabotage pts")}${H("ppg", "Per G")}${H("pa", "Pts allowed")}${H("papg", "Allowed / G")}
    ${BUCKETS.map((b) => `<th class="num bk" title="Games allowing ${b} points">${b}</th>`).join("")}</tr></thead><tbody>
    ${list.map((t, i) => `<tr id="t-${t.team}" class="${t.team === focus ? "focus" : ""}"><td class="num dim">${i + 1}</td><td><strong>${esc(NICK[t.team] || t.team)}</strong> <span class="dim">${t.team}</span></td>
      <td class="num">${t.g}</td><td class="num total">${fmt(t.pts)}</td><td class="num">${fmt(t.ppg, 1)}</td><td class="num">${fmt(t.pa)}</td><td class="num">${fmt(t.papg, 1)}</td>
      ${BUCKETS.map((b) => `<td class="num bk${t.buckets[b] ? "" : " zero"}">${t.buckets[b]}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div>`;
  $("#d-table").querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => {
    const k = b.dataset.k;
    if (sortKey === k) sortDir = sortDir === "desc" ? "asc" : "desc"; else { sortKey = k; sortDir = k === "team" ? "asc" : "desc"; }
    render();
  }));

  // week-by-week grid: shade = Sabotage points earned that week (0 to 42), one hue
  const byeOrUnplayed = (t, w) => {
    const g = games.find((x) => x.week === w && (x.home_team === t || x.away_team === t));
    return !g ? "Bye" : "";
  };
  $("#d-grid").innerHTML = `<div class="table-wrap plain"><table class="grid"><thead><tr><th>Defense</th>${Array.from({ length: maxWeek }, (_, i) => `<th class="num">${i + 1}</th>`).join("")}</tr></thead><tbody>
    ${list.map((t) => `<tr class="${t.team === focus ? "focus" : ""}"><td><strong>${t.team}</strong></td>${Array.from({ length: maxWeek }, (_, i) => {
      const r = t.weeks.get(i + 1);
      if (!r) { const b = byeOrUnplayed(t.team, i + 1); return `<td class="num dim">${b ? "bye" : ""}</td>`; }
      const a = (r.sabotage_pts / 42).toFixed(2);
      return `<td class="num cell" style="--a:${a}" title="Week ${r.week} vs ${r.opponent}: ${r.points_allowed} allowed, ${r.sabotage_pts} Sabotage pts">${r.points_allowed}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table></div>`;
  if (focus && !scrolled && document.getElementById(`t-${focus}`)) { scrolled = true; document.getElementById(`t-${focus}`).scrollIntoView({ block: "center" }); }
}

init();
