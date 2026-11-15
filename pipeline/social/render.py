"""Render social cards (HTML) to JPEG with headless Chromium.

Instagram only accepts JPEG, so every card ships as .jpg.

Usage: python pipeline/social/render.py pipeline/social/cards/scoring.html site/assets/social/how-sabotage-scores.jpg
Needs: pip install playwright pillow, then python -m playwright install chromium
"""
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

# True when anything inside the card would be cut off: content taller than the
# card, or a line wider than its column.
OVERFLOW_JS = """() => {
  const c = document.querySelector('.card');
  if (c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1) return true;
  const g = document.querySelector('.grow');
  if (g && g.getBoundingClientRect().height < 0) return true;
  for (const el of c.querySelectorAll('.mid, .nm, .ln')) {
    if (el.scrollWidth > el.clientWidth + 1) return true;
  }
  return false;
}"""


def _shot(page, width, height):
    page.evaluate("document.fonts.ready")
    return page.locator(".card").screenshot()


def _save(png: bytes, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(png)).convert("RGB").save(out, "JPEG", quality=90, optimize=True)


def render(src: Path, out: Path, width: int = 1080, height: int = 1350) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(src.resolve().as_uri())
        png = _shot(page, width, height)
        browser.close()
    _save(png, out)


def render_fit(build_html, out: Path, trims=(0, 1, 2), width: int = 1080, height: int = 1350) -> int:
    """build_html(trim) -> HTML string. Tries each trim level until nothing overflows.
    Returns the trim level used. Raises RuntimeError if no level fits."""
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        for t in trims:
            f = Path(tmp) / f"card-{t}.html"
            f.write_text(build_html(t), encoding="utf-8")
            page.goto(f.as_uri())
            page.evaluate("document.fonts.ready")
            if not page.evaluate(OVERFLOW_JS):
                _save(page.locator(".card").screenshot(), out)
                browser.close()
                return t
        browser.close()
    raise RuntimeError(f"{out.name}: card overflows at every trim level")


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
    print("wrote", sys.argv[2])
