"""OG image + mobile/desktop QA for the edit-reels page."""
from pathlib import Path
from playwright.sync_api import sync_playwright

B = Path(__file__).resolve().parent
SITE = B.parent / "resources-site"
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1200, "height": 630})
    pg.goto((B / "og_edit.html").as_uri(), wait_until="networkidle")
    pg.screenshot(path=str(SITE / "assets" / "og-edit-reels.jpg"), type="jpeg", quality=90)
    m = br.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    m.goto((SITE / "edit-reels" / "index.html").as_uri(), wait_until="networkidle")
    m.evaluate("document.fonts.ready")
    m.screenshot(path=str(B / "qa_edit_mobile.png"), full_page=True)
    print("overflow-x mobile:", m.evaluate("document.documentElement.scrollWidth > window.innerWidth"),
          "| buttons:", m.evaluate("document.querySelectorAll('.prompt .hd button').length"),
          "| imgs broken:", m.evaluate("[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src)"),
          "| inter:", m.evaluate("document.fonts.check('800 20px Inter')"))
    d = br.new_page(viewport={"width": 1280, "height": 900})
    d.goto((SITE / "edit-reels" / "index.html").as_uri(), wait_until="networkidle")
    d.screenshot(path=str(B / "qa_edit_desktop.png"))
    h = br.new_page(viewport={"width": 390, "height": 844})
    h.goto((SITE / "index.html").as_uri(), wait_until="networkidle")
    h.screenshot(path=str(B / "qa_hub_mobile.png"), full_page=True)
    br.close()
