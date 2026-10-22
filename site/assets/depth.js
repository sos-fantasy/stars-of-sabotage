import { $, esc, NICK, CITY } from "./common.js";
import { loadMeta, fillFooter, fmtET } from "./foot.js";
import { loadInjuries, loadDepth, tagHTML, isOut } from "./avail.js";

// Every team's depth chart at QB, RB, WR, TE and K, with today's injury designations.
// Players who are out are crossed off and the next man up is marked as starting,
// the same way the Matchups page picks who to project.
const POS = ["QB", "RB", "WR", "TE", "K"];
const params = new URLSearchParams(location.search);
let D = null, games = new Map();

async function init() {
  loadMeta().then(fillFooter).catch(() => {});
  const [, d, proj] = await Promise.all([loadInjuries(), loadDepth(),
    fetch(`data/projections.json?t=${Math.floor(Date.now() / 300000)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null)]);
  D = d;
  if (!D) {
    $("#d-body").innerHTML = `<p class="loading">Depth charts are not available right now. They return on the next update.</p>`;
    return;
  }
  if (proj && proj.week === D.week) {
    for (const g of proj.games || []) {
      games.set(g.home, { opp: g.away, home: true, g });
      games.set(g.away, { opp: g.home, home: false, g });
    }
  }
  $("#d-week").textContent = `${D.season} week ${D.week}`;
  const teams = Object.keys(D.teams).sort((a, b) => (CITY[a] + NICK[a]).localeCompare(CITY[b] + NICK[b]));
  const sel = $("#d-team");
  sel.innerHTML = `<option value="all">All teams, starters</option>` +
    teams.map((t) => `<option value="${t}">${esc(CITY[t] || t)} ${esc(NICK[t] || "")}</option>`).join("");
  const want = (params.get("team") || "").toUpperCase();
  sel.value = D.teams[want] ? want : "all";
  sel.onchange = () => { history.replaceState(null, "", sel.value === "all" ? location.pathname : `?team=${sel.value}`); show(); };
  $("#d-body").onclick = (e) => {
    const a = e.target.closest("[data-team]");
    if (!a) return;
    e.preventDefault();
    sel.value = a.dataset.team;
    sel.onchange();
    window.scrollTo({ top: 0 });
  };
  show();
}

function show() {
  const t = $("#d-team").value;
  $("#d-body").innerHTML = t === "all" ? allTeams() : oneTeam(t);
  $("#d-changes").innerHTML = changes(t === "all" ? null : t);
}

const nameLink = (e) => (e.id ? `<a class="plink" href="player.html?id=${encodeURIComponent(e.id)}">${esc(e.name)}</a>` : esc(e.name));
const unavailable = (e) => isOut(e.tag);

function move(e) {
  if (e.new) return `<span class="dmove new" title="Not on this list a week ago">new</span>`;
  if (!e.prev_rank || e.prev_rank === e.rank) return "";
  const up = e.prev_rank > e.rank;
  return `<span class="dmove ${up ? "up" : "down"}" title="Was No. ${e.prev_rank} a week ago">${up ? "▲" : "▼"} from ${e.prev_rank}</span>`;
}

function entry(e) {
  const cls = ["dent", e.start ? "on" : "", unavailable(e) ? "gone" : ""].join(" ").trim();
  return `<li class="${cls}"><span class="drank">${e.rank}</span>
    <span class="dname"><span class="dn">${nameLink(e)}</span>${e.start ? ` <span class="dslot">${esc(e.slot)}</span>` : ""}${move(e)}
      ${e.in_for ? `<span class="infor">in for ${esc(e.in_for)}</span>` : ""}${tagHTML(e.tag, { block: true })}</span></li>`;
}

function nextGame(team) {
  const n = games.get(team);
  if (!n) return `<p class="dim">No game in week ${D.week}.</p>`;
  return `<p class="dim">Week ${D.week} ${n.home ? "vs" : "at"} ${esc(NICK[n.opp] || n.opp)}. <a href="matchups.html">Matchups</a></p>`;
}

function updated(t) {
  const u = Object.values(D.teams[t].updated || {});
  const latest = u.sort().pop();
  return latest ? `Chart as of ${fmtET(latest)}.` : "";
}

function oneTeam(t) {
  const T = D.teams[t];
  const cols = POS.filter((p) => T[p] && T[p].length).map((p) => `<section class="dcol" aria-label="${p}">
      <h3>${p === "K" ? "Kicker" : p}</h3><ol class="dlist">${T[p].map(entry).join("")}</ol></section>`).join("");
  return `<div class="dhead"><h2>${esc(CITY[t] || "")} ${esc(NICK[t] || t)}</h2>${nextGame(t)}<p class="hint">${updated(t)}</p></div>
    <div class="dgrid">${cols}</div>`;
}

function allTeams() {
  const order = Object.keys(D.teams).sort((a, b) => (CITY[a] + NICK[a]).localeCompare(CITY[b] + NICK[b]));
  return `<div class="ggrid dall">${order.map((t) => {
    const T = D.teams[t];
    const starters = POS.flatMap((p) => (T[p] || []).filter((e) => e.start));
    const out = POS.flatMap((p) => (T[p] || []).filter((e) => e.rank <= ({ QB: 1, RB: 2, WR: 3, TE: 2, K: 1 })[p] && unavailable(e)));
    const n = games.get(t);
    return `<article class="gcard dcard"><h3><a href="?team=${t}" data-team="${t}">${esc(NICK[t] || t)}</a>
        <span class="dim">${n ? `${n.home ? "vs" : "at"} ${esc(n.opp)}` : "bye"}</span></h3>
      <ol class="glist">${starters.map((e) => `<li><span class="slot">${esc(e.slot)}</span><span>${nameLink(e)}${e.in_for ? ` <span class="infor">in for ${esc(e.in_for)}</span>` : ""}${tagHTML(e.tag, { block: true })}</span></li>`).join("")}</ol>
      ${out.length ? `<p class="dout">Not playing: ${out.map((e) => `${esc(e.name)} (${esc(e.tag.status)})`).join(", ")}</p>` : ""}
    </article>`;
  }).join("")}</div>`;
}

// Moves near the top of each chart in the last seven days, and who is filling in.
function changes(team) {
  const rows = [];
  for (const [t, T] of Object.entries(D.teams)) {
    if (team && t !== team) continue;
    for (const p of POS) {
      for (const e of T[p] || []) {
        const top = ({ QB: 1, RB: 2, WR: 3, TE: 2, K: 1 })[p];
        const moved = e.prev_rank && e.prev_rank !== e.rank && (e.rank <= top || e.prev_rank <= top);
        const fresh = e.new && e.rank <= top;
        if (moved || fresh || e.in_for) rows.push({ t, p, e });
      }
    }
  }
  if (!rows.length) return `<p class="hint">No changes among the starters in the last week.</p>`;
  rows.sort((a, b) => a.t.localeCompare(b.t) || POS.indexOf(a.p) - POS.indexOf(b.p) || a.e.rank - b.e.rank);
  return `<div class="table-wrap plain"><table class="wrap"><tr><th>Team</th><th>Pos</th><th>Player</th><th>Change</th></tr>
    ${rows.map(({ t, p, e }) => `<tr><td>${esc(t)}</td><td>${p}</td><td>${nameLink(e)}${tagHTML(e.tag, { block: true })}</td>
      <td>${[e.in_for ? `Starting in for ${esc(e.in_for)}` : "", e.new ? `New to the chart, now No. ${e.rank}` : "",
        e.prev_rank && e.prev_rank !== e.rank ? `No. ${e.prev_rank} to No. ${e.rank}` : ""].filter(Boolean).join(". ")}</td></tr>`).join("")}</table></div>`;
}

init();
