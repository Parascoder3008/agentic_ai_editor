"""Real screenshots of the Claude Ads repo (dark mode, 2x) for the proof panel."""
from playwright.sync_api import sync_playwright

URL = "https://github.com/AgriciDaniel/claude-ads"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 540, "height": 480}, device_scale_factor=2, color_scheme="dark")
    pg.goto(URL, wait_until="networkidle")
    pg.screenshot(path="gh_top.png")
    pg.screenshot(path="gh_full.png", full_page=True)
    print(pg.evaluate("document.body.scrollHeight"))
    b.close()
