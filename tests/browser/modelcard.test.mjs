import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'model card: hover shows a small card, opening the selected name shows the full one';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/', { view: '1300x1000' });
    await sleep(700);
    const $ = (fn, arg) => browser.eval(fn, arg);
    // the full card, from the selected model's name
    t.equal(await $(() => getComputedStyle(document.getElementById('modelDialog')).display), 'none', 'the card is closed to begin with');
    await $(() => document.getElementById('modelFocus').click());
    await sleep(250);
    const card = await $(() => ({
      open: document.getElementById('modelDialog').open,
      title: document.getElementById('modelCardTitle').textContent,
      rows: [...document.querySelectorAll('#modelCardBody dt')].map((x) => x.textContent),
      link: (document.querySelector('#modelCardBody a') || {}).href,
      license: [...document.querySelectorAll('#modelCardBody dd')][2] && [...document.querySelectorAll('#modelCardBody dd')][2].textContent,
    }));
    t.ok(card.open && card.title === 'Qwen3.8 27B', 'opening the selected name shows its card', JSON.stringify(card));
    t.ok(['Repository', 'Released', 'License', 'Weights', 'Also as', 'Runs on'].every((r) => card.rows.includes(r)), 'with the repository, release date, license, weight size, other builds and engines', JSON.stringify(card.rows));
    t.equal(card.link, 'https://huggingface.co/Qwen/Qwen3.8-27B', 'and a link to Hugging Face');
    t.equal(card.license, 'Apache 2.0', 'the license in plain words');
    await $(() => document.getElementById('modelCardClose').click());
    await sleep(150);
    t.equal(await $(() => document.getElementById('modelDialog').open), false, 'and it closes');
    // a gated model says so
    await $(() => { const r = [...document.querySelectorAll('#modelList .family-row')].find((x) => x.querySelector('.family-label strong').textContent.startsWith('Llama')); r.querySelector('.model-option').click(); });
    await sleep(250);
    await $(() => document.getElementById('modelFocus').click());
    await sleep(200);
    t.ok((await $(() => [...document.querySelectorAll('#modelCardBody dd')].map((x) => x.textContent))).some((x) => /Gated/.test(x)), 'a gated model says it is gated');
    await $(() => document.getElementById('modelCardClose').click());
    // hovering a pill shows the small card without selecting it
    const before = await $(() => document.getElementById('modelRefDisplay').textContent);
    const pos = await $(() => { const b = [...document.querySelectorAll('#modelList .model-option')].find((x) => x.textContent.trim().startsWith('Flash-Next')); const r = b.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    await browser.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: pos.x, y: pos.y, pointerType: 'mouse' });
    await sleep(700);
    const peek = await $(() => ({ shown: !document.getElementById('modelPeek').hidden, text: document.getElementById('modelPeek').textContent, ref: document.getElementById('modelRefDisplay').textContent }));
    t.ok(peek.shown && /Flash-Next/.test(peek.text) && /Qwen\/Qwen3\.8-Flash-Next/.test(peek.text), 'hovering a pill shows that model\'s card', JSON.stringify(peek));
    t.equal(peek.ref, before, 'and does not select it');
    await browser.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 5, y: 5, pointerType: 'mouse' });
    await sleep(300);
    t.equal(await $(() => document.getElementById('modelPeek').hidden), true, 'moving away hides it');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
