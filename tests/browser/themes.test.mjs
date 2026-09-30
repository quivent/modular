import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'themes: six themes, remembered, applied before the page paints';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const $ = (fn, arg) => browser.eval(fn, arg);
    t.equal(await $(() => document.getElementById('themeOpen').nextElementSibling.id), 'trackerOpen', 'the Themes button sits just left of Tracker');
    await $(() => document.getElementById('themeOpen').click());
    t.equal(await $(() => [...document.querySelectorAll('.theme-card strong')].map((x) => x.textContent)), ['Meadow', 'Midnight', 'Paper', 'Terminal', 'macOS', 'Windows'], 'six themes, including macOS and Windows');
    const paper = {};
    for (const [label, id] of [['Meadow', null], ['Midnight', 'midnight'], ['Paper', 'paper'], ['Terminal', 'terminal'], ['macOS', 'macos'], ['Windows', 'windows']]) {
      await $((l) => [...document.querySelectorAll('.theme-card')].find((c) => c.querySelector('strong').textContent === l).click(), label);
      paper[label] = await $(() => ({ attr: document.documentElement.getAttribute('data-theme'), bg: getComputedStyle(document.body).backgroundColor, stored: localStorage.getItem('modular.theme') }));
      t.equal([paper[label].attr, paper[label].stored], [id, id || 'meadow'], `${label}: applied and remembered`);
    }
    t.equal(new Set(Object.values(paper).map((x) => x.bg)).size, 6, 'all six themes have their own page background')
    t.equal(paper.Meadow.bg, 'rgb(248, 249, 246)', 'Meadow is the original palette');
    t.ok(/^rgb\((?:[0-9]|1[0-9]|2[0-9]|3[0-9]), /.test(paper.Midnight.bg) && /^rgb\((?:[0-9]|1[0-9]), /.test(paper.Terminal.bg), 'Midnight and Terminal are dark');
    t.equal(await $(() => getComputedStyle(document.body).fontFamily.includes('Segoe')), true, 'Windows uses Segoe UI');
    // remembered across a reload and applied before first paint
    await browser.open(server.base + '/', { init: `document.addEventListener('DOMContentLoaded', () => { window.__themeAtLoad = document.documentElement.getAttribute('data-theme'); });` });
    t.equal(await $(() => window.__themeAtLoad), 'windows', 'a saved theme is already on the page at DOMContentLoaded (no flash of the default)');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
