"""HTML for top-N cards (1080 x 1350). Rendered to JPEG by render.py.

`trim` drops optional pieces when the card does not fit:
0 = everything, 1 = no one-liner, 2 = no one-liner and no header mascot.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = (ROOT / "site" / "assets").resolve()


def _u(p: str) -> str:
    return (ASSETS / p).as_uri()


def top_card(card: dict, trim: int = 0) -> str:
    best = max(r["pts"] for r in card["rows"]) or 1
    from top7 import stat_line  # local import keeps this file free of data logic

    rows = []
    for i, r in enumerate(card["rows"]):
        w = r["pts"] / best * 100
        color = "#f2b705" if i == 0 else "#ece6d8"
        rows.append(
            f'<div class="r"><span class="rk">{escape(r["rank"])}</span><div class="mid">'
            f'<div class="nm"><b>{escape(r["name"])}</b><span>{escape(r["pos"])} · {escape(r["team"])}</span></div>'
            f'<div class="ln">{" · ".join(f"<span>{escape(b)}</span>" for b in stat_line(r).split(" · "))}</div>'
            f'<div class="bar"><i style="width:{w:.1f}%;background:{color}"></i></div></div>'
            f'<span class="pt">{r["pts"]}</span></div>'
        )
    head = []
    for name, score in card["headline"]:
        head.append(escape(name) + (f" <span>{score}</span>" if score is not None else ""))
    if card["type"] == "wreckage":
        h1 = f'{escape(card["headline"][0][0])} <span>{escape(card["headline"][1][0])}</span>'
    else:
        h1 = "<br>".join(head)
    mascot = "" if trim >= 2 else f'<img class="mascot" src="{_u("whoopsie.webp")}" alt="">'
    blurb = "" if trim >= 1 else f'<p class="blurb">{escape(card["blurb"])}</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(card['id'])}</title>
<style>
@font-face{{font-family:Anton;src:url("{_u('fonts/anton-latin-400-normal.woff2')}") format("woff2")}}
@font-face{{font-family:"JetBrains Mono";font-weight:400;src:url("{_u('fonts/jetbrains-mono-latin-400-normal.woff2')}") format("woff2")}}
@font-face{{font-family:"JetBrains Mono";font-weight:700;src:url("{_u('fonts/jetbrains-mono-latin-700-normal.woff2')}") format("woff2")}}
*{{box-sizing:border-box}} body{{margin:0}}
.card{{width:1080px;height:1350px;background:#15140f;color:#ece6d8;font-family:"JetBrains Mono",monospace;display:flex;flex-direction:column;overflow:hidden}}
.bar0{{height:18px;background:#b8421f;flex:none}}
.head{{padding:40px 72px 0;display:flex;justify-content:space-between;align-items:flex-end;gap:24px}}
.eb{{font-size:24px;letter-spacing:6px;color:#f2b705;font-weight:700}} .sub{{font-size:22px;letter-spacing:3px;color:#a39b8a;margin-top:12px}}
h1{{margin:20px 0 0;font-family:Anton,Impact,sans-serif;font-weight:400;font-size:88px;line-height:.94;text-transform:uppercase}} h1 span{{color:#f2b705}}
.mascot{{width:150px;height:167px;flex:none}}
.th,.r{{display:grid;grid-template-columns:70px minmax(0,1fr) 110px;gap:16px}}
.th{{margin:28px 72px 0;padding-bottom:10px;border-bottom:3px solid #f2b705;font-size:17px;letter-spacing:3px;color:#f2b705;font-weight:700}}
.list{{margin:0 72px}} .r{{align-items:center;padding:10px 0;border-bottom:2px solid #3a372d}}
.rk{{font-family:Anton,Impact,sans-serif;font-size:40px;color:#f2b705}} .mid{{display:flex;flex-direction:column;gap:6px;min-width:0}}
.nm{{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}} .nm b{{font-size:28px}} .nm span{{font-size:18px;color:#a39b8a}}
.ln{{font-size:17px;color:#a39b8a;letter-spacing:1px;line-height:1.35}} .ln span{{white-space:nowrap}} .bar{{height:10px;background:#2a2820}} .bar i{{display:block;height:10px}}
.pt{{font-family:Anton,Impact,sans-serif;font-size:52px;text-align:right}}
.blurb{{margin:22px 72px 24px;font-size:23px;line-height:1.4}} .grow{{flex:1}}
.foot{{flex:none;background:#0d0c09;border-top:6px solid #b8421f;padding:18px 72px;display:flex;justify-content:space-between;align-items:center;font-size:18px}}
.brand{{display:flex;align-items:center;gap:16px}} .brand img{{width:58px;height:65px}}
.word{{font-family:Anton,Impact,sans-serif;font-size:34px;line-height:1;text-transform:uppercase}} .word span{{color:#f2b705}}
.url{{font-size:16px;letter-spacing:3px;color:#a39b8a;margin-top:4px}} .legal{{text-align:right;color:#a39b8a;line-height:1.5}}
</style></head><body><div class="card"><div class="bar0"></div>
<div class="head"><div><div class="eb">{escape(card['eyebrow'])}</div><div class="sub">{escape(card['sub'])}</div>
<h1>{h1}</h1></div>{mascot}</div>
<div class="th"><span>RANK</span><span>PLAYER · WHAT HE DID</span><span style="text-align:right">POINTS</span></div>
<div class="list">{''.join(rows)}</div>
{blurb}<div class="grow"></div>
<div class="foot"><div class="brand"><img src="{_u('whoopsie.webp')}" alt=""><div><div class="word">Stars of <span>Sabotage</span></div><div class="url">STARSOFSABOTAGE.COM</div></div></div><div class="legal">Data: nflverse, CC BY 4.0<br>Not affiliated with the NFL</div></div>
</div></body></html>"""
