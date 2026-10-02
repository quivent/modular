import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'saved data: old setups upgrade, newer ones are kept, the server shares state across browsers';

export default async function (t) {
  const server = await startServer();
  if (!(await startBrowser().then(async (b) => { if (b) await b.close(); return b; }))) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  const clearServerState = () => fetch(server.base + '/api/state', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const session = async (init, fn, { keepServerState = false } = {}) => {
    if (!keepServerState) await clearServerState(); // the server's copy wins over browser storage, so isolate each session
    const b = await startBrowser();
    try { await b.open(server.base + '/', { init }); await fn(b); } finally { await b.close(); }
  };
  const click = (sel, text) => ([s, x]) => [...document.querySelectorAll(s)].find((e) => e.textContent.trim() === x).click();
  try {
    // build a real setup with the app itself (SGLang, a non-default model), then age it into the first storage format
    let made;
    await session(null, async (b) => {
      await b.eval(() => { document.querySelector('#serverList [data-server="sglang"]').click(); document.getElementById('saveConfig').click(); });
      await sleep(400);
      made = await b.eval(() => JSON.parse(localStorage.getItem('modular.configs')).items[0].snapshot);
    });
    t.ok(made.v === 1 && made.catalogRef === 'Qwen/Qwen3.8-27B', 'a new setup records its version and names its model');
    const legacy = { ...made, favorites: [9], recent: [3], defaultModel: 0 };
    delete legacy.v; delete legacy.catalogRef;
    await session(
      `localStorage.setItem('modular.preferences', JSON.stringify({favorites:[1],defaultModel:4}));
       localStorage.setItem('modular.configs', JSON.stringify([{name:'Old',snapshot:${JSON.stringify(legacy)}}]));`,
      async (b) => {
        const r = await b.eval(async () => {
          const c = JSON.parse(localStorage.getItem('modular.configs'));
          const s = c.items[0].snapshot;
          document.querySelector('#serverList [data-server="vllm"]').click();
          document.querySelector('[data-load-config]').click();
          await new Promise((r) => setTimeout(r, 200));
          return { envelope: c.v, snapV: s.v, ref: s.catalogRef, dropped: !('favorites' in s) && !('recent' in s) && !('defaultModel' in s),
                   engine: document.querySelector('#serverList .active').dataset.server, out: document.getElementById('output').textContent.slice(0, 28) };
        });
        t.equal([r.envelope, r.snapV, r.ref, r.dropped], [1, 1, 'Qwen/Qwen3.8-27B', true], 'an old setup is upgraded: versioned, model named, favorites no longer inside it');
        t.equal([r.engine, r.out.startsWith('python -m sglang')], ['sglang', true], 'loading it switches the engine and the command');
      },
    );

    // newer than this app: kept, not loadable, never overwritten
    await session(
      `localStorage.setItem('modular.configs', JSON.stringify({v:1,items:[{name:'Future',snapshot:{server:'vllm',model:0,v:2,shiny:true,values:{},toggles:{}}}]}));`,
      async (b) => {
        const r = await b.eval(async () => {
          const btn = document.querySelector('[data-load-config]');
          const before = { disabled: btn.disabled, title: btn.title };
          document.getElementById('saveConfig').click();
          await new Promise((r) => setTimeout(r, 200));
          const items = JSON.parse(localStorage.getItem('modular.configs')).items;
          return { before, count: items.length, kept: items[0].snapshot.v === 2 && items[0].snapshot.shiny === true };
        });
        t.equal([r.before.disabled, r.before.title], [true, 'Saved by a newer version of Modular'], 'a setup from a newer version cannot be loaded, and says why');
        t.equal([r.count, r.kept], [2, true], 'saving another setup does not touch it');
      },
    );
    await session(`localStorage.setItem('modular.configs', JSON.stringify({v:2,items:[{name:'Future'}]}));`, async (b) => {
      const ok = await b.eval(async () => { document.getElementById('saveConfig').click(); await new Promise((r) => setTimeout(r, 200)); const c = JSON.parse(localStorage.getItem('modular.configs')); return c.v === 2 && c.items.length === 1 && c.items[0].name === 'Future'; });
      t.ok(ok, 'storage written by a newer version is never overwritten');
    });
    await session(`localStorage.setItem('modular.configs', JSON.stringify({v:1,items:[{name:'Gone',snapshot:{v:1,server:'vllm',model:0,catalogRef:'gone/model',values:{},toggles:{}}}]}));`, async (b) => {
      const r = await b.eval(() => { const x = document.querySelector('[data-load-config]'); return [x.disabled, x.title]; });
      t.equal(r, [true, 'This model is no longer in the catalog'], 'a setup whose model left the catalog is kept and explains itself');
    });

    // the server holds state so a brand-new browser sees it
    await session(null, async (b) => {
      await b.eval(() => { document.getElementById('saveConfig').click(); });
      await sleep(900);
    });
    const state = await (await fetch(server.base + '/api/state')).json();
    t.ok(state.version === 1 && state.configs.length === 1 && state.configs[0].snapshot.v === 1 , 'a saved setup reached the server');
    await session(null, async (b) => {
      await sleep(600);
      const r = await b.eval(() => ({ count: document.getElementById('savedConfigCount').textContent }));
      t.equal(r, { count: '1' }, 'a fresh browser with empty storage shows it');
    }, { keepServerState: true });
    // the theme is part of the saved state: chosen once, it follows you to another browser
    await session(null, async (b) => { await sleep(500); });
    t.equal((await (await fetch(server.base + '/api/state')).json()).preferences.theme, undefined, 'no theme is saved until one is chosen');
    await session(null, async (b) => {
      await sleep(400);
      await b.eval(() => { document.getElementById('themeOpen').click(); [...document.querySelectorAll('.theme-card')].find((c) => c.textContent.startsWith('Windows')).click(); });
      await sleep(900);
    });
    t.equal((await (await fetch(server.base + '/api/state')).json()).preferences.theme, 'windows', 'the chosen theme reaches the server');
    await session(null, async (b) => {
      await sleep(900);
      const r = await b.eval(() => ({ theme: document.documentElement.getAttribute('data-theme'), kept: localStorage.getItem('modular.theme') }));
      t.equal(r, { theme: 'windows', kept: 'windows' }, 'a browser with nothing stored comes up in it');
    }, { keepServerState: true });
    // no flash: the server puts the saved theme on the page itself, so the first paint is already right
    const html = await (await fetch(server.base + '/')).text();
    t.ok(/<html lang="en" data-theme="windows">/.test(html), 'the page arrives already in the saved theme');
    await session(null, async (b) => {
      const early = await b.eval(() => new Promise((res) => { res(document.documentElement.getAttribute('data-theme')); }));
      t.equal(early, 'windows', 'even in a browser that has never been here');
    }, { keepServerState: true });
    await fetch(server.base + '/api/state', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    t.ok(!/data-theme="/.test((await (await fetch(server.base + '/')).text()).slice(0, 200)), 'with nothing saved, the page is sent as it is');
  } finally {
    await server.close();
  }
}
