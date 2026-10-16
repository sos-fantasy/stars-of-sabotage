// Shared: load meta.json and fill the footer status line on every page.
export async function loadMeta() {
  // Minute-stamped so neither the browser nor a CDN can hold an old copy.
  const r = await fetch(`data/meta.json?t=${Math.floor(Date.now() / 60000)}`, { cache: "no-cache" });
  if (!r.ok) throw new Error("meta " + r.status);
  return r.json();
}

const ET = "America/New_York";
export function fmtET(iso, withTime = true) {
  const d = new Date(iso);
  const opts = withTime
    ? { timeZone: ET, month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
    : { timeZone: ET, weekday: "short", month: "short", day: "numeric" };
  return d.toLocaleString("en-US", opts) + (withTime ? " ET" : "");
}

export const STATUS_TEXT = {
  final: "final",
  provisional: "provisional",
  in_progress: "in progress",
  upcoming: "upcoming",
};

export function fillFooter(meta) {
  const el = document.getElementById("foot-status");
  if (!el || !meta) return;
  const wk = meta.weeks.find((w) => w.week === meta.latest_week);
  let s = `Data last changed ${fmtET(meta.updated_at)}. Checked ${meta.checked_on}.`;
  if (wk) s += ` Week ${wk.week} is ${STATUS_TEXT[wk.status]}.`;
  s += ` Scoring rules v${meta.scoring_version}.`;
  el.textContent = s;
}

if (!document.getElementById("board")) {
  loadMeta().then(fillFooter).catch(() => {});
}
