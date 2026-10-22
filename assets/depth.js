import { $, esc, NICK, CITY } from "./common.js?v=dd86e435db";
import { loadMeta, fillFooter, fmtET } from "./foot.js?v=949d944f7b";
import { lineChart, wireTips, fmt } from "./stats.js?v=b43e399a02";
import { loadInjuries, loadDepth, tagHTML, isOut } from "./avail.js?v=2b6f548bac";

// Every team's depth chart at QB, RB, WR, TE and K, with today's injury designations.
// Players who are out are crossed off and the next man up is marked as starting,
// the same way the Matchups page picks who to project.
const POS = ["QB", "RB", "WR", "TE", "K"];
const params = new URLSearchParams(location.search);
// Teams in order of team name (Bears, Bengals, Bills...), owner's choice October 22.
const byName = (a, b) => (NICK[a] || a).localeCompare(NICK[b] || b);
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
  const teams = Object.keys(D.teams).sort(byName);
  const sel = $("#d-team");
  sel.innerHTML = `<option value="all">All teams, starters</option>` +
    teams.map((t) => `<option value="${t}">${esc(NICK[t] || t)} (${esc(CITY[t] || t)})</option>`).join("");
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
  document.querySelectorAll("#d-body .chart-box").forEach(wireTips);
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

function entry(e, pos) {
  const cls = ["dent", e.start ? "on" : "", unavailable(e) ? "gone" : ""].join(" ").trim();
  return `<li class="${cls}"><span class="drank">${e.rank}</span>
    <span class="dname"><span class="dn">${nameLink(e)}</span>${e.start ? ` <span class="dslot">${esc(e.slot)}</span>` : ""}${move(e)}
      ${e.in_for ? `<span class="infor">in for ${esc(e.in_for)}</span>` : ""}${tagHTML(e.tag, { block: true })}${lastLine(e, pos)}</span></li>`;
}

// His most recent game: snap share, carries (RB), targets (RB, WR, TE), Sabotage points.
function lastLine(e, pos) {
  const g = e.last;
  if (!g) return `<span class="dlast">No games this season</span>`;
  const bits = [];
  if (pos !== "K" && g.snap !== null && g.snap !== undefined) bits.push(`${g.snap}% snaps`);
  if (pos === "RB") bits.push(`${g.car} car`);
  if (["RB", "WR", "TE"].includes(pos) && g.tgt !== null && g.tgt !== undefined) bits.push(`${g.tgt} tgt`);
  bits.push(`${g.pts} pts`);
  const where = g.team && g.team !== e.team ? ` with ${esc(g.team)}` : "";
  return `<span class="dlast" title="Most recent game: week ${g.week}${where}">Wk ${g.week}${where}: ${bits.join(" · ")}</span>`;
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
      <h3>${p === "K" ? "Kicker" : p}</h3><ol class="dlist">${T[p].map((e) => entry({ ...e, team: t }, p)).join("")}</ol></section>`).join("");
  return `<div class="dhead"><h2>${esc(CITY[t] || "")} ${esc(NICK[t] || t)}</h2>${nextGame(t)}<p class="hint">${updated(t)}</p></div>
    <div class="dgrid">${cols}</div>
    ${usageCharts(t)}`;
}

// Usage by week for the team's players at each position, so a rising or falling role
// shows at a glance. Up to four players per chart (the validated color slots), picked
// by season usage and colored in depth chart order.
const USAGE = [
  { pos: "QB", label: "Quarterbacks: share of offensive snaps", unit: "% of snaps", i: 3, ymax: 100 },
  { pos: "RB", label: "Running backs: rushing attempts", unit: " carries", i: 1 },
  { pos: "WR", label: "Wide receivers: targets", unit: " targets", i: 2 },
  { pos: "TE", label: "Tight ends: targets", unit: " targets", i: 2 },
];
const COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
function usageCharts(t) {
  const T = D.teams[t], U = T.usage || {};
  // The team's own game weeks: a bye is left off the axis rather than drawn as zero.
  const xs = T.games || [];
  if (!xs.length) return "";
  const allWeeks = Array.from({ length: Math.max(...xs) }, (_, i) => i + 1);
  const byes = allWeeks.filter((w) => !xs.includes(w));
  const charts = USAGE.map((u) => {
    const ps = (T[u.pos] || []).filter((e) => U[e.id] && U[e.id].some((g) => g[u.i] !== null && g[u.i] !== undefined));
    const total = (e) => U[e.id].reduce((a, g) => a + (g[u.i] || 0), 0);
    const top = [...ps].sort((a, b) => total(b) - total(a)).slice(0, 4).sort((a, b) => a.rank - b.rank);
    if (!top.length) return "";
    const series = top.map((e, k) => ({
      name: e.name, color: COLORS[k],
      // Weeks he did not play are zeros (played flag 0), so the line runs through them.
      pts: U[e.id].filter((g) => g[u.i] !== null && g[u.i] !== undefined)
        .map((g) => ({ x: g[0], v: g[u.i], note: g[5] === 0 ? " (did not play)" : "" })),
    }));
    const left = ps.length - top.length;
    return `<section class="dchart"><h3>${esc(u.label)}</h3>
      <div class="chart-box">${lineChart(xs, (x, long) => (long ? `Week ${x}` : String(x)), series, `${NICK[t] || t} ${u.label} by week`, { unit: u.unit, ymax: u.ymax, ymin: 4 })}</div>
      ${left > 0 ? `<p class="hint">${left} more ${left === 1 ? "player" : "players"} with fewer ${u.pos === "QB" ? "snaps" : u.unit.trim()} not shown.</p>` : ""}</section>`;
  }).join("");
  return `<section class="dusage" aria-labelledby="d-usage-h"><h2 id="d-usage-h">Usage by week</h2>
    <p class="hint">Every ${esc(NICK[t] || t)} game this season${byes.length ? ` (bye: week ${byes.join(", ")})` : ""}. A player who did not play that week, or was not on the team yet, sits at zero. Snap share is the share of the team's offensive plays he was on the field for, from nflverse snap counts. Route participation would be a sharper measure for receivers, but it is not published during the season.</p>
    <div class="dcharts">${charts}</div></section>`;
}

function allTeams() {
  const order = Object.keys(D.teams).sort(byName);
  return `<div class="ggrid dall">${order.map((t) => {
    const T = D.teams[t];
    const starters = POS.flatMap((p) => (T[p] || []).filter((e) => e.start).map((e) => ({ ...e, team: t, pos: p })));
    const out = POS.flatMap((p) => (T[p] || []).filter((e) => e.rank <= ({ QB: 1, RB: 2, WR: 3, TE: 2, K: 1 })[p] && unavailable(e)));
    const n = games.get(t);
    return `<article class="gcard dcard"><h3><a href="?team=${t}" data-team="${t}">${esc(NICK[t] || t)}</a>
        <span class="dim">${n ? `${n.home ? "vs" : "at"} ${esc(n.opp)}` : "bye"}</span></h3>
      <ol class="glist">${starters.map((e) => `<li><span class="slot">${esc(e.slot)}</span><span>${nameLink(e)}${e.in_for ? ` <span class="infor">in for ${esc(e.in_for)}</span>` : ""}${tagHTML(e.tag, { block: true })}${lastLine(e, e.pos)}</span></li>`).join("")}</ol>
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
  rows.sort((a, b) => byName(a.t, b.t) || POS.indexOf(a.p) - POS.indexOf(b.p) || a.e.rank - b.e.rank);
  return `<div class="table-wrap plain"><table class="wrap"><tr><th>Team</th><th>Pos</th><th>Player</th><th>Change</th></tr>
    ${rows.map(({ t, p, e }) => `<tr><td>${esc(NICK[t] || t)}</td><td>${p}</td><td>${nameLink(e)}${tagHTML(e.tag, { block: true })}</td>
      <td>${[e.in_for ? `Starting in for ${esc(e.in_for)}` : "", e.new ? `New to the chart, now No. ${e.rank}` : "",
        e.prev_rank && e.prev_rank !== e.rank ? `No. ${e.prev_rank} to No. ${e.rank}` : ""].filter(Boolean).join(". ")}</td></tr>`).join("")}</table></div>`;
}

init();
