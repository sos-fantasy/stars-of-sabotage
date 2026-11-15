"""Render a social card (HTML) to a JPEG with headless Chromium.

Instagram only accepts JPEG, so every card ships as .jpg.

Usage: python pipeline/social/render.py pipeline/social/cards/scoring.html site/assets/social/how-sabotage-scores.jpg
Needs: pip install playwright pillow, then python -m playwright install chromium
"""
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


def render(src: Path, out: Path, width: int = 1080, height: int = 1350) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(src.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        png = page.locator(".card").screenshot()
        browser.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(png)).convert("RGB").save(out, "JPEG", quality=90, optimize=True)


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
    print("wrote", sys.argv[2])
