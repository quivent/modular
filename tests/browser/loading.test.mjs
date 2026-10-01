import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'loading: nothing is fetched from another site, fonts come with the page, the flag lists ship inside the page';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    await sleep(1200);
    const r = await browser.eval(async () => {
      await document.fonts.ready;
      const here = location.host;
      const fonts = ['400 12px "DM Sans"', '700 12px "DM Sans"', '700 12px "Manrope"', '400 12px "DM Mono"', '500 12px "DM Mono"'].map((f) => document.fonts.check(f));
      const res = performance.getEntriesByType('resource');
      return {
        outside: res.filter((e) => new URL(e.name).host !== here).map((e) => e.name),
        fonts,
        woff: res.filter((e) => /\.woff2$/.test(e.name)).length,
        flagRequests: res.filter((e) => /catalog\/flags|\/api\//.test(e.name)).map((e) => e.name),
        panel: document.querySelectorAll('#allFlags .flag-line').length > 100,
      };
    });
    t.equal(r.outside, [], 'every request goes to this site (no Google Fonts, no third party)');
    t.equal(r.fonts, [true, true, true, true, true], 'DM Sans, Manrope and DM Mono are available');
    t.ok(r.woff >= 3, 'the font files were fetched from this site', String(r.woff));
    t.ok(r.flagRequests.every((u) => /\/api\/(tasks|state|events)/.test(u)), 'no flag file is requested: the lists are in the page');
    t.ok(r.panel, 'the flag panel is filled');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
