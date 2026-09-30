import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'phone: no sideways scroll, Copy stays in reach until the command is on screen';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/', { view: '390x800' });
    const $ = (fn, arg) => browser.eval(fn, arg);
    await sleep(800);
    t.equal(await $(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, 'the page does not scroll sideways at 390 px');
    const bar = () => $(() => { const e = document.getElementById('copyBar'); return !e.hidden && getComputedStyle(e).display !== 'none'; });
    t.equal(await bar(), true, 'a Copy button is on screen while the command is far below');
    await $(() => window.scrollTo({ top: document.getElementById('copy').getBoundingClientRect().top + scrollY - 100, behavior: 'instant' }));
    await sleep(1000);
    t.equal(await bar(), false, 'it steps aside when the real Copy button is visible');
    await browser.open(server.base + '/', { view: '1300x900' });
    await sleep(800);
    t.equal(await bar(), false, 'it is not shown on a desktop screen');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
