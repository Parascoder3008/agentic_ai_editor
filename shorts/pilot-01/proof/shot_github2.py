"""Desktop-layout repo header (stars visible), 2x for zoom-ins."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 960}, device_scale_factor=2, color_scheme="dark")
    pg.goto("https://github.com/AgriciDaniel/claude-ads", wait_until="networkidle")
    pg.screenshot(path="gh_desk.png")
    star = pg.locator("#repo-stars-counter-star").first
    print("stars box", star.bounding_box(), star.inner_text())
    b.close()
