import { startServer, startBrowser } from '../lib/harness.mjs';
export const name = 'harness probe: server and browser start, page loads, both stop cleanly';
export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    t.equal(await browser.eval(() => document.title), 'Modular — Build a model deployment', 'page title');
    t.equal(await browser.eval(() => document.getElementById('modelRefDisplay').textContent), 'Qwen/Qwen3.8-27B', 'opens on the current default model');
    t.equal((await browser.errors()).length, 0, 'no page errors');
    t.equal(await browser.eval(() => document.getElementById('trackerOpen').hidden), false, 'tracker shows when the server answers');
  } finally {
    await browser.close();
    await server.close();
  }
}
