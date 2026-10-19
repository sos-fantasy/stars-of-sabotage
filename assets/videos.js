import { $, esc, toObjs, dataVersion, getJSON, NICK } from "./common.js?v=dd86e435db";
import { loadMeta, fillFooter } from "./foot.js?v=949d944f7b";

// Weekly worst-plays videos. The page shows a thumbnail first and only loads YouTube's
// player (from the privacy-enhanced youtube-nocookie.com domain) when someone presses play.
const params = new URLSearchParams(location.search);
let meta = null, list = [], onSite = true;

const thumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
const watch = (id) => `https://www.youtube.com/watch?v=${id}`;
const key = (v) => `${v.season}-${v.week}`;
// nflverse numbers the playoffs as weeks 19 to 22.
const PLAYOFF = { 19: "Wild Card", 20: "Divisional round", 21: "Conference championships", 22: "Super Bowl" };
const wkLabel = (w) => PLAYOFF[w] || `week ${w}`;

async function init() {
  try {
    meta = await loadMeta();
    const d = await getJSON(`data/videos.json?v=${meta.data_hash}-${Math.floor(Date.now() / 300000)}`);
    list = d.videos || [];
    onSite = d.play_on_site !== false;
  } catch (e) {
    list = [];
  }
  if (meta) fillFooter(meta);
  if (!list.length) {
    $("#v-main").innerHTML = `<p class="loading">No videos yet. They show up here after each week's games.</p>`;
    $("#v-pick").hidden = true;
    return;
  }
  // One entry per week (the first video listed for it), newest first.
  const weeks = [];
  const seen = new Set();
  for (const v of list) if (!seen.has(key(v))) { seen.add(key(v)); weeks.push(v); }
  const sel = $("#v-week");
  const seasons = [...new Set(weeks.map((v) => v.season))];
  sel.innerHTML = seasons.map((s) => `<optgroup label="${s}">${weeks.filter((v) => v.season === s)
    .map((v) => `<option value="${key(v)}">${v.season} ${wkLabel(v.week)}</option>`).join("")}</optgroup>`).join("");
  const want = `${params.get("season")}-${params.get("week")}`;
  sel.value = weeks.some((v) => key(v) === want) ? want : key(weeks[0]);
  sel.onchange = () => show(sel.value, true);
  $("#v-more").addEventListener("click", (e) => {
    const a = e.target.closest("[data-k]");
    if (!a) return;
    e.preventDefault();
    sel.value = a.dataset.k;
    show(a.dataset.k, true);
    $("#v-main").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  show(sel.value, false);
  function show(k, push) {
    const [season, week] = k.split("-").map(Number);
    if (push) history.pushState(null, "", `?season=${season}&week=${week}`);
    const vids = list.filter((v) => v.season === season && v.week === week);
    $("#v-main").innerHTML = vids.map(card).join("");
    $("#v-main").querySelectorAll("[data-play]").forEach((b) => (b.onclick = () => play(b)));
    // The rest of the same season only.
    const same = weeks.filter((v) => v.season === season && key(v) !== k);
    $("#v-more-h").textContent = `More from ${season}`;
    $("#v-more").innerHTML = same.map((v) =>
      `<a class="vtile" href="?season=${v.season}&week=${v.week}" data-k="${key(v)}">
        <img src="${thumb(v.id)}" alt="" loading="lazy" width="480" height="360"><span>${v.season} ${wkLabel(v.week)}</span></a>`).join("");
    $("#v-more-h").hidden = same.length === 0;
    culprits(season, week);
  }
  window.addEventListener("popstate", () => location.reload());
}

function card(v) {
  const title = esc(v.title || `${v.season} ${wkLabel(v.week)}`);
  const by = v.channel ? `<p class="vby">From ${esc(v.channel)} on YouTube</p>` : "";
  if (v.embed === "no" || !onSite) {
    return `<article class="vcard"><a class="vframe off" href="${watch(v.id)}" target="_blank" rel="noopener">
        <img src="${thumb(v.id)}" alt="" width="480" height="360"><span class="vplay" aria-hidden="true"></span>
        <span class="vnote">${onSite ? "The uploader does not allow this video on other sites." : "The NFL only lets these videos play on YouTube."} Opens in a new tab.</span></a>
      <h2 class="vtitle">${title}</h2>${by}</article>`;
  }
  return `<article class="vcard"><div class="vframe">
      <button type="button" class="vbtn" data-play="${v.id}" aria-label="Play: ${title}">
        <img src="${thumb(v.id)}" alt="" width="480" height="360"><span class="vplay" aria-hidden="true"></span></button></div>
    <h2 class="vtitle">${title}</h2>${by}<p class="vby"><a href="${watch(v.id)}" target="_blank" rel="noopener">Watch on YouTube</a></p></article>`;
}

function play(btn) {
  const id = btn.dataset.play;
  const f = document.createElement("iframe");
  f.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
  f.title = btn.getAttribute("aria-label").replace(/^Play: /, "");
  f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
  f.allowFullscreen = true;
  f.referrerPolicy = "strict-origin-when-cross-origin";
  btn.replaceWith(f);
}

// The week's biggest saboteurs, so the video sits next to the numbers.
async function culprits(season, week) {
  const box = $("#v-culprits");
  box.innerHTML = "";
  try {
    const v = season === meta.season ? meta.data_hash : meta.scoring_version;
    const rows = toObjs(await getJSON(`data/scores-${season}.json?v=${v}`)).filter((r) => r.week === week)
      .sort((a, b) => b.sabotage_pts - a.sabotage_pts || a.player_display_name.localeCompare(b.player_display_name)).slice(0, 5);
    if (!rows.length) return;
    box.innerHTML = `<h2>Week ${week} top five</h2><ol class="top5">${rows.map((r, i) =>
      `<li><span class="rk">${i + 1}</span><span class="nm"><a class="plink" href="player.html?id=${encodeURIComponent(r.player_id)}&season=${season}">${esc(r.player_display_name)}</a>
        <small>${esc(r.position)} · ${esc(NICK[r.team] || r.team)} vs ${esc(r.opponent_team)}</small></span><span class="v">${r.sabotage_pts}</span></li>`).join("")}</ol>
      <p class="hint"><a href="./?season=${season}&from=${week}&to=${week}">Full week ${week} leaderboard</a></p>`;
  } catch (e) { /* no scores for that season: leave empty */ }
}

init();
