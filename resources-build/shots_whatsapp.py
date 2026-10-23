"""OG image + QA screenshots (mobile 390 wide, desktop) of the WhatsApp agent guide."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent / "resources-site"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto((ROOT.parent / "resources-build" / "og_whatsapp.html").as_uri(), wait_until="networkidle")
    pg.screenshot(path=str(ROOT / "assets" / "og-whatsapp-agent.jpg"), type="jpeg", quality=90)
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    m.goto((ROOT / "whatsapp-agent" / "index.html").as_uri(), wait_until="networkidle")
    m.screenshot(path=str(ROOT.parent / "resources-build" / "qa_whatsapp_mobile.png"), full_page=True)
    print("overflow-x (mobile):", m.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
    b.close()
