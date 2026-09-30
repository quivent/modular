"""Rebuild README images. Requires Playwright and its Chromium browser.

Run a local server from the repository root, then:
    python assets/readme/render.py --url http://127.0.0.1:8000
"""
from argparse import ArgumentParser
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8000')
args = parser.parse_args()
base = args.url.rstrip('/')
out = Path(__file__).resolve().parent

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    for name, width, height in [('cover', 1200, 800), ('cover-mobile', 680, 1120)]:
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1.5)
        page.goto(base + '/assets/readme/cover.html', wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(out / (name + '.png')))
        page.close()

    page = browser.new_page(viewport={'width': 1200, 'height': 1100}, device_scale_factor=1.5)
    page.goto(base, wait_until='networkidle')
    page.locator('#runtime-title').evaluate('(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-35)')
    # End at a section boundary; preserve the original UI and its native type.
    page.locator('section[aria-labelledby="runtime-title"]').screenshot(path=str(out / 'engine.png'))
    page.locator('.preview').screenshot(path=str(out / 'output.png'))
    page.close()

    page = browser.new_page(viewport={'width': 390, 'height': 900}, device_scale_factor=2)
    page.goto(base, wait_until='networkidle')
    page.locator('.preview').screenshot(path=str(out / 'output-mobile.png'))
    page.close()

    page = browser.new_page(viewport={'width': 1200, 'height': 1090}, device_scale_factor=1.5)
    page.goto(base + '/assets/readme/workspace.html', wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    page.locator('.spread').screenshot(path=str(out / 'workspace.png'))
    browser.close()
