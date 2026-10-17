// Shared stat definitions and chart helpers for the player and compare pages.

// Scored stats shown per position, in display order. Each: count field, points field, label.
export const STAT = {
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
export const BY_POS = {
  QB: ["inc", "sack", "int", "pk6", "fum", "lost", "car"],
  RB: ["car", "rec", "fum", "lost"], FB: ["car", "rec", "fum", "lost"],
  WR: ["rec", "car", "fum", "lost"], TE: ["rec", "car", "fum", "lost"],
  K: ["fgx", "patx"],
};
export const POS_NAME = { QB: "QBs", RB: "RBs", FB: "RBs", WR: "WRs", TE: "TEs", K: "kickers" };
// Chart groups (validated categorical slots 1 to 4 on the dark surface).
export const GROUPS = [
  { key: "pass", label: "Passing misfires", color: "var(--s1)", f: (r) => r.pts_incomplete + r.pts_sacks },
  { key: "turn", label: "Turnovers", color: "var(--s2)", f: (r) => r.pts_int + r.pts_pick_six + r.pts_fumble + r.pts_fumble_lost },
  { key: "vol", label: "Touches", color: "var(--s3)", f: (r) => r.pts_carries + r.pts_receptions },
  { key: "kick", label: "Missed kicks", color: "var(--s4)", f: (r) => r.pts_kicking },
];

export const fmt = (v, d = 0) => (v === null || v === undefined ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
export const sum = (rows, k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
// Axis top with four even, round gridline steps (steps of 1, 2, 2.5 or 5 times a power of ten).
export function niceMax(v) {
  if (v <= 10) return 10;
  const raw = v / 4, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw);
  return step * 4;
}

// Sabotage points from one stat. Kicking points arrive as one total, so split it:
// each missed or blocked PAT is 16 and field goal misses are the rest.
export function statPoints(rows, k) {
  if (k === "patx") return sum(rows, "n_pat_missed") * 16;
  if (k === "fgx") return sum(rows, "pts_kicking") - sum(rows, "n_pat_missed") * 16;
  return STAT[k].p ? sum(rows, STAT[k].p) : null;
}

export function short(label) {
  return { "Incomplete passes": "Inc", "Sacks taken": "Sk", Interceptions: "INT", "Pick sixes (bonus)": "Pk6", Fumbles: "Fum",
    "Fumbles lost (bonus)": "Lost", "Rushing attempts": "Car", Receptions: "Rec", "Field goals missed or blocked": "FGx",
    "Extra points missed or blocked": "PATx" }[label] || label;
}
export function wireTips(box) {
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

