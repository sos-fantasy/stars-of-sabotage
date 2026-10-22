// Injury tags and depth chart spots, shared by every page that lists players.
// Data: data/injuries.json and data/depth.json, written by pipeline/availability.py.
// Standalone (no imports) so the leaderboard can load it without pulling in other modules.

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const stamp = () => Math.floor(Date.now() / 300000);   // five-minute cache window
let INJ = null, DEPTH = null, injP = null, depthP = null;

const get = (u) => fetch(`${u}?t=${stamp()}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);

export function loadInjuries() {
  if (!injP) injP = get("data/injuries.json").then((d) => (INJ = d && d.players ? d : { players: {} }));
  return injP;
}
export function loadDepth() {
  if (!depthP) depthP = get("data/depth.json").then((d) => (DEPTH = d && d.teams ? d : null));
  return depthP;
}
export const injuries = () => INJ;
export const depth = () => DEPTH;

// Short labels for narrow spots (the leaderboard on a phone); the full word stays in the
// tooltip and for screen readers.
const SHORT = { Questionable: "Q", Doubtful: "D", "Did not practice": "DNP", "Limited practice": "Ltd",
  "IR, designated to return": "IR-R", Suspended: "Susp", "Exempt list": "Exempt" };

// One tag object -> HTML. `week` is the week the site is previewing; a designation
// from an earlier week is labeled with its week so it is never read as current.
export function tagHTML(t, { block = false } = {}) {
  if (!t) return "";
  const cur = INJ && INJ.week;
  const old = t.week !== null && t.week !== undefined && cur && t.week !== cur ? ` (week ${t.week})` : "";
  const why = t.injury ? `<span class="inj-why">${esc(t.injury.toLowerCase())}</span>` : "";
  const title = `${t.status}${t.injury ? `: ${t.injury}` : ""}${old}`;
  const short = SHORT[t.status] || t.status;
  const label = short === t.status ? esc(t.status)
    : `<span class="inj-full">${esc(t.status)}</span><span class="inj-short" aria-hidden="true">${esc(short)}</span>`;
  return `<span class="inj inj-${old ? "old" : esc(t.level || "q")}${block ? " inj-block" : ""}" title="${esc(title)}">${label}${why ? ` · ${why}` : ""}${esc(old)}</span>`;
}

// True when the tag rules him out of the week being previewed (not last week's).
export function isOut(t) {
  return !!t && (t.level === "out" || t.level === "d") && (t.week === null || t.week === undefined || !INJ || t.week === INJ.week);
}

export function injTag(id, opts) {
  return INJ && id ? tagHTML(INJ.players[id], opts) : "";
}

// "WR2 for CHI" style label from the depth chart, plus who he is filling in for.
export function slotOf(id) {
  return DEPTH && DEPTH.slots ? DEPTH.slots[id] || null : null;
}
export function slotText(id) {
  const s = slotOf(id);
  if (!s) return "";
  const where = s.slot ? `${s.slot} on the ${s.team} depth chart` : `${s.pos}${s.rank} on the ${s.team} depth chart`;
  return s.in_for ? `${where}, starting for ${s.in_for}` : where;
}
