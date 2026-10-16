import { $, esc, toObjs, dataVersion, getJSON, NICK } from "./common.js";
import { loadMeta, fillFooter } from "./foot.js";

// Scored stats shown per position, in display order. Each: count field, points field, label.
const STAT = {
  inc: { n: "n_incomplete", p: "pts_incomplete", label: "Incomplete passes", pct: "pct_n_incomplete" },
  sack: { n: "n_sacks", p: "pts_sacks", label: "Sacks taken", pct: "pct_n_sacks" },
  int: { n: "n_ints", p: "pts_int", label: "Interceptions", pct: "pct_n_ints" },
  pk6: { n: "n_pick_sixes", p: "pts_pick_six", label: "Pick sixes (bonus)", pct: "pct_n_pick_sixes" },
  fum: { n: "n_fumbles", p: "pts_fumble", label: "Fumbles", pct: "pct_n_fumbles" },
  lost: { n: "n_fumbles_lost", p: "pts_fumble_lost", label: "Fumbles lost (bonus)", pct: "pct_n_fumbles_lost" },
  car: { n: "n_carries", p: "pts_carries", label: "Rushing attempts", pct: "pct_n_carries" },
  rec: { n: "n_receptions", p: "pts_receptions", label: "Receptions", pct: "pct_n_receptions" },
  fgx: { n: "n_fg_missed", p: null, label: "Field goals missed or blocked", pct: "pct_n_fg_missed" },
  patx: { n: "n_pat_missed", p: null, label: "Extra points missed or blocked", pct: "pct_n_pat_missed" },
};
const BY_POS = {
  QB: ["inc", "sack", "int", "pk6", "fum", "lost", "car"],
  RB: ["car", "rec", "fum", "lost"], FB: ["car", "rec", "fum", "lost"],
  WR: ["rec", "car", "fum", "lost"], TE: ["rec", "car", "fum", "lost"],
  K: ["fgx", "patx"],
};
const POS_NAME = { QB: "QBs", RB: "RBs", FB: "RBs", WR: "WRs", TE: "TEs", K: "kickers" };
// Chart groups (validated categorical slots 1 to 4 on the dark surface).
const GROUPS = [
  { key: "pass", label: "Passing misfires", color: "var(--s1)", f: (r) => r.pts_incomplete + r.pts_sacks },
  { key: "turn", label: "Turnovers", color: "var(--s2)", f: (r) => r.pts_int + r.pts_pick_six + r.pts_fumble + r.pts_fumble_lost },
  { key: "vol", label: "Touches", color: "var(--s3)", f: (r) => r.pts_carries + r.pts_receptions },
  { key: "kick", label: "Missed kicks", color: "var(--s4)", f: (r) => r.pts_kicking },
];

const params = new URLSearchParams(location.search);
const id = params.get("id");
let P = null, seasons = [], weeks = [], meta = null;

async function init() {
  loadMeta().then((m) => { meta = m; fillFooter(m); nextGame(); }).catch(() => {});
  if (!id) return notFound();
  try {
    P = await getJSON(`data/players/${encodeURIComponent(id)}.json?v=${dataVersion()}`);
  } catch (e) {
    return notFound();
  }
  seasons = toObjs(P.seasons);
  weeks = toObjs(P.weeks);
  document.title = `${P.name} | Stars of Sabotage`;
  const sel = $("#p-season");
  sel.innerHTML = [...seasons].reverse().map((s) => `<option value="${s.season}">${s.season}</option>`).join("") +
    (seasons.length > 1 ? `<option value="career">Career</option>` : "");
  const want = params.get("season");
  sel.value = want && [...sel.options].some((o) => o.value === want) ? want : String(P.last);
  sel.onchange = () => {
    const u = new URL(location.href);
    u.searchParams.set("season", sel.value);
    history.replaceState(null, "", u);
    render();
  };
  $("#p-name").textContent = P.name;
  $("#p-meta").innerHTML = `${esc(P.position)} · <span title="${esc(NICK[P.team] || "")}">${esc(P.team)}</span> · ${P.first === P.last ? P.first : `${P.first} to ${P.last}`}`;
  render();
}

function notFound() {
  $("#p-name").textContent = "Player not found";
  $("#p-meta").textContent = "Use the search box above to find someone.";
  $("#p-body").hidden = true;
}

const fmt = (v, d = 0) => (v === null || v === undefined ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const sum = (rows, k) => rows.reduce((a, r) => a + (r[k] || 0), 0);

function render() {
  const sv = $("#p-season").value;
  const career = sv === "career";
  const season = career ? null : +sv;
  const srow = career ? null : seasons.find((s) => s.season === season);
  const wk = career ? weeks : weeks.filter((w) => w.season === season);
  const pos = (srow || seasons[seasons.length - 1]).position;
  const g = wk.length;
  const total = sum(wk, "sabotage_pts");

  // tiles
  const tiles = [
    ["Sabotage points", fmt(total)],
    ["Per game", fmt(g ? total / g : 0, 1)],
    ["Games", fmt(g)],
    career ? ["Seasons", fmt(seasons.length)] : ["Rank", srow ? `#${srow.pos_rank} <small>of ${srow.pos_n} ${POS_NAME[pos] || pos}</small>` : ""],
  ];
  $("#p-tiles").innerHTML = tiles.map(([k, v]) => `<div class="tile"><p class="k">${k}</p><p class="v">${v}</p></div>`).join("");

  // tale of the tape rows
  const keys = [...(BY_POS[pos] || [])];
  for (const k of Object.keys(STAT)) if (!keys.includes(k) && sum(wk, STAT[k].n) > 0) keys.push(k);
  const qualified = srow && srow.pct_sabotage_pts !== null && srow.pct_sabotage_pts !== undefined;
  const pctHead = document.querySelector(".tape-head .ph");
  if (pctHead) pctHead.textContent = career ? "" : "Position percentile";
  $("#p-tape-note").textContent = career ? "Career totals." :
    qualified ? `Bars show where each per-game rate ranks among ${season} ${POS_NAME[pos] || pos} with 4 or more games. 100 means the most sabotage at the position.`
      : `Fewer than 4 games in ${season}, so no position ranking.`;
  $("#p-tape").innerHTML = keys.map((k) => {
    const s = STAT[k];
    const n = sum(wk, s.n);
    let pts = s.p ? sum(wk, s.p) : null;
    if (k === "fgx") pts = sum(wk, "pts_kicking") - sum(wk, "n_pat_missed") * 16;
    if (k === "patx") pts = sum(wk, "n_pat_missed") * 16;
    const pct = qualified ? srow[s.pct] : null;
    const bar = pct === null || pct === undefined ? "" :
      `<div class="bar" role="img" aria-label="${pct}th percentile"><span style="width:${Math.max(2, pct)}%"></span></div><span class="pct">${pct}<small>th</small></span>`;
    return `<div class="tape-row"><p class="lbl">${esc(s.label)}</p>
      <p class="val">${fmt(n)}${g ? `<small>${fmt(n / g, 1)}/g</small>` : ""}</p>
      <p class="pts">${pts === null ? "" : `${fmt(pts)} <small>pts</small>`}</p>
      <div class="pctcell">${bar}</div></div>`;
  }).join("");

  // chart
  $("#p-chart-title").textContent = career ? "Sabotage points by season" : `${season} by week`;
  $("#p-chart").innerHTML = career ? seasonChart() : weekChart(wk, season);
  wireTips($("#p-chart"));

  // log table
  $("#p-log-title").textContent = career ? "Season by season" : "Game log";
  $("#p-log").innerHTML = career ? seasonTable() : gameLog(wk, keys);

  // splits
  $("#p-splits").innerHTML = splits(wk);
}

// ---------- charts (inline SVG, hand-drawn to match the site) ----------
const W = 760, H = 260, M = { t: 16, r: 12, b: 34, l: 40 };
function niceMax(v) { if (v <= 10) return 10; const p = 10 ** Math.floor(Math.log10(v)); return Math.ceil(v / p) * p; }

function weekChart(wk, season) {
  const maxWeek = Math.max(18, ...wk.map((w) => w.week));
  const lastWeek = Math.max(...wk.map((w) => w.week), 0);
  const byWeek = new Map(wk.map((w) => [w.week, w]));
  const ymax = niceMax(Math.max(10, ...wk.map((w) => w.sabotage_pts)));
  const iw = W - M.l - M.r, ih = H - M.t - M.b, bw = iw / maxWeek;
  const y = (v) => M.t + ih - (v / ymax) * ih;
  let s = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Sabotage points by week, ${season}">`;
  for (let i = 0; i <= 4; i++) {
    const v = (ymax / 4) * i;
    s += `<line class="grid" x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}"/><text class="axis" x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
  }
  for (let wkn = 1; wkn <= maxWeek; wkn++) {
    const x = M.l + (wkn - 1) * bw + bw * 0.18, w = bw * 0.64;
    s += `<text class="axis" x="${x + w / 2}" y="${H - 14}" text-anchor="middle">${wkn}</text>`;
    const r = byWeek.get(wkn);
    if (!r) { if (wkn <= lastWeek) s += `<text class="axis dim" x="${x + w / 2}" y="${y(0) - 4}" text-anchor="middle">-</text>`; continue; }
    let base = 0;
    const segs = GROUPS.map((gp) => ({ gp, v: gp.f(r) })).filter((x) => x.v > 0);
    segs.forEach((sg, i) => {
      const top = y(base + sg.v), bottom = y(base);
      const h = Math.max(0, bottom - top - (i ? 2 : 0));   // 2px gap between stacked fills
      const rx = i === segs.length - 1 ? 3 : 0;
      s += `<rect x="${x}" y="${top}" width="${w}" height="${h}" rx="${rx}" fill="${sg.gp.color}"/>`;
      base += sg.v;
    });
    const tip = `Week ${wkn} ${r.home === 0 ? "at" : "vs"} ${r.opponent_team}: ${r.sabotage_pts} pts` +
      segs.map((sg) => ` · ${sg.gp.label} ${sg.v}`).join("");
    s += `<rect class="hit" x="${M.l + (wkn - 1) * bw}" y="${M.t}" width="${bw}" height="${ih}" data-tip="${esc(tip)}"/>`;
  }
  // 3-game rolling average over games played
  const pts = [];
  const played = wk.slice().sort((a, b) => a.week - b.week);
  played.forEach((r, i) => {
    const win = played.slice(Math.max(0, i - 2), i + 1);
    const avg = win.reduce((a, x) => a + x.sabotage_pts, 0) / win.length;
    pts.push([M.l + (r.week - 1) * bw + bw / 2, y(avg)]);
  });
  if (pts.length > 1) s += `<polyline class="avg" points="${pts.map((p) => p.join(",")).join(" ")}"/>`;
  s += `</svg>`;
  const used = GROUPS.filter((gp) => wk.some((r) => gp.f(r) > 0));
  const legend = used.map((gp) => `<span><i style="background:${gp.color}"></i>${gp.label}</span>`).join("") +
    `<span><i class="line"></i>3-game average</span>`;
  return `<div class="legend">${legend}</div>${s}`;
}

function seasonChart() {
  const rows = seasons;
  const ymax = niceMax(Math.max(10, ...rows.map((r) => r.sabotage_pts)));
  const iw = W - M.l - M.r, ih = H - M.t - M.b, bw = iw / Math.max(rows.length, 8);
  const y = (v) => M.t + ih - (v / ymax) * ih;
  let s = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Sabotage points by season">`;
  for (let i = 0; i <= 4; i++) {
    const v = (ymax / 4) * i;
    s += `<line class="grid" x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}"/><text class="axis" x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
  }
  rows.forEach((r, i) => {
    const x = M.l + i * bw + bw * 0.2, w = bw * 0.6;
    s += `<rect x="${x}" y="${y(r.sabotage_pts)}" width="${w}" height="${Math.max(0, y(0) - y(r.sabotage_pts))}" rx="3" fill="var(--s1)"/>`;
    s += `<text class="axis" x="${x + w / 2}" y="${H - 14}" text-anchor="middle">${String(r.season).slice(2)}</text>`;
    s += `<rect class="hit" x="${M.l + i * bw}" y="${M.t}" width="${bw}" height="${ih}" data-tip="${esc(`${r.season} ${r.team}: ${fmt(r.sabotage_pts)} pts in ${r.g} games, #${r.pos_rank} of ${r.pos_n}`)}"/>`;
  });
  return s + `</svg>`;
}

function wireTips(box) {
  let tip = box.querySelector(".tip");
  if (!tip) { tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; box.appendChild(tip); }
  box.querySelectorAll(".hit").forEach((h) => {
    const show = () => {
      tip.textContent = h.dataset.tip;
      tip.hidden = false;
      const b = h.getBoundingClientRect(), c = box.getBoundingClientRect();
      // beside the column, never on top of the bar
      const w = tip.offsetWidth || 230, right = b.right - c.left + 6;
      const sx = box.scrollLeft;
      tip.style.left = `${sx + (right + w <= c.width ? right : Math.max(0, b.left - c.left - w - 6))}px`;
      tip.style.top = `${b.top - c.top + 6}px`;
      h.classList.add("on");
    };
    const hide = () => { tip.hidden = true; h.classList.remove("on"); };
    // Mouse shows on hover; a tap toggles, so a touch never flashes and vanishes.
    h.addEventListener("pointerenter", (e) => e.pointerType === "mouse" && show());
    h.addEventListener("pointerleave", (e) => e.pointerType === "mouse" && hide());
    h.addEventListener("click", () => { box.querySelectorAll(".hit.on").forEach((x) => x !== h && x.classList.remove("on")); show(); });
  });
}

// ---------- tables ----------
const venue = (r) => {
  if (r.roof === "dome" || r.roof === "closed") return "Indoors";
  if (r.roof === null || r.roof === undefined) return "";
  return r.wind === null || r.wind === undefined ? "Outdoors" : `Outdoors, ${r.wind} mph`;
};

function gameLog(wk, keys) {
  const cols = keys.map((k) => STAT[k]);
  const head = `<tr><th>Wk</th><th>Opp</th><th>Venue</th>${cols.map((c) => `<th class="num" title="${esc(c.label)}">${esc(short(c.label))}</th>`).join("")}<th class="num total">Pts</th></tr>`;
  const body = wk.slice().sort((a, b) => a.week - b.week).map((r) =>
    `<tr><td>${r.week}</td><td>${r.home === 0 ? "@" : "vs"} ${esc(r.opponent_team)}</td><td class="dim">${esc(venue(r))}</td>
     ${cols.map((c) => `<td class="num${r[c.n] ? "" : " zero"}">${r[c.n]}</td>`).join("")}<td class="num total">${r.sabotage_pts}</td></tr>`).join("");
  return `<div class="table-wrap plain"><table>${head}${body}</table></div>`;
}
function short(label) {
  return { "Incomplete passes": "Inc", "Sacks taken": "Sk", Interceptions: "INT", "Pick sixes (bonus)": "Pk6", Fumbles: "Fum",
    "Fumbles lost (bonus)": "Lost", "Rushing attempts": "Car", Receptions: "Rec", "Field goals missed or blocked": "FGx",
    "Extra points missed or blocked": "PATx" }[label] || label;
}
function seasonTable() {
  const head = `<tr><th>Season</th><th>Team</th><th class="num">G</th><th class="num total">Pts</th><th class="num">Per G</th><th class="num">Pos rank</th></tr>`;
  const body = [...seasons].reverse().map((s) => `<tr><td><a href="?id=${encodeURIComponent(id)}&season=${s.season}">${s.season}</a></td><td>${esc(s.team)}</td>
    <td class="num">${s.g}</td><td class="num total">${fmt(s.sabotage_pts)}</td><td class="num">${fmt(s.sabotage_pts / s.g, 1)}</td>
    <td class="num">#${s.pos_rank} <span class="dim">of ${s.pos_n}</span></td></tr>`).join("");
  return `<div class="table-wrap plain"><table>${head}${body}</table></div>`;
}

function splits(wk) {
  const groups = [
    ["Home", (r) => r.home === 1], ["Away", (r) => r.home === 0],
    ["Indoors", (r) => r.roof === "dome" || r.roof === "closed"],
    ["Outdoors", (r) => r.roof === "outdoors" || r.roof === "open"],
    ["Outdoors, wind under 10 mph", (r) => (r.roof === "outdoors" || r.roof === "open") && r.wind !== null && r.wind < 10],
    ["Outdoors, wind 10 to 19 mph", (r) => (r.roof === "outdoors" || r.roof === "open") && r.wind >= 10 && r.wind < 20],
    ["Outdoors, wind 20+ mph", (r) => (r.roof === "outdoors" || r.roof === "open") && r.wind >= 20],
  ];
  const all = wk.length ? sum(wk, "sabotage_pts") / wk.length : 0;
  const rows = groups.map(([label, f]) => {
    const g = wk.filter(f);
    if (!g.length) return "";
    const pg = sum(g, "sabotage_pts") / g.length;
    const width = all ? Math.min(100, (pg / (all * 2)) * 100) : 0;
    return `<tr class="${g.length < 4 ? "small" : ""}"><td>${label}</td><td class="num">${g.length}</td><td class="num total">${fmt(pg, 1)}</td>
      <td class="sbar"><span style="width:${width}%"></span><i style="left:50%" title="Overall average"></i></td></tr>`;
  }).join("");
  return `<div class="table-wrap plain"><table><tr><th>Split</th><th class="num">G</th><th class="num">Pts/G</th><th>vs overall (${fmt(all, 1)})</th></tr>${rows}</table></div>
    <p class="hint">The tick marks the overall average. Splits under 4 games are dimmed; small samples swing hard.</p>`;
}

// ---------- next game ----------
async function nextGame() {
  if (!P || !meta || P.last !== meta.season) return;
  try {
    const g = toObjs(await getJSON(`data/games-${meta.season}.json?v=${dataVersion()}`));
    const n = g.find((x) => (x.home_team === P.team || x.away_team === P.team) && (x.home_score === null || x.home_score === undefined));
    if (!n) return;
    const home = n.home_team === P.team;
    const opp = home ? n.away_team : n.home_team;
    const d = new Date(`${n.gameday}T12:00:00`);
    const day = d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    const t = n.gametime ? (() => { const [h, m] = n.gametime.split(":").map(Number); return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"} ET`; })() : "";
    const roof = n.roof === "dome" || n.roof === "closed" ? "Indoors" : n.roof ? (n.roof === "open" ? "Open roof" : "Outdoors") : "";
    $("#p-next").innerHTML = `<p class="eyebrow">Next up</p><p class="next">Week ${n.week} ${home ? "vs" : "at"} <strong>${esc(NICK[opp] || opp)}</strong> · ${day}${t ? " · " + t : ""}${roof ? " · " + roof : ""}</p>`;
    $("#p-next").hidden = false;
  } catch (e) { /* no schedule: leave hidden */ }
}

init();
