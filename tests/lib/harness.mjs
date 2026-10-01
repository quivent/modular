// Test harness: a throwaway Modular server and a headless Chrome, both on free ports, both cleaned up
// by killing only the processes this file started. Requires Node 22+ (global WebSocket).
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function freePort() {
  return new Promise((ok, fail) => {
    const s = createServer();
    s.once('error', fail);
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address();
      s.close(() => ok(port));
    });
  });
}

export function findChrome() {
  const candidates = [
    process.env.CHROME,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean);
  return candidates.find((c) => existsSync(c)) || null;
}

async function waitFor(check, what, ms = 15000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      const v = await check();
      if (v) return v;
    } catch {}
    await sleep(120);
  }
  throw new Error('timed out waiting for ' + what);
}

function stop(child) {
  return new Promise((done) => {
    if (!child || child.exitCode !== null) return done();
    child.once('exit', () => done());
    child.kill('SIGTERM');
    setTimeout(() => child.exitCode === null && child.kill('SIGKILL'), 2500);
  });
}

// A Modular server on a free port with its own empty database.
export async function startServer() {
  const port = await freePort();
  const dir = mkdtempSync(join(tmpdir(), 'modular-test-'));
  const child = spawn('python3', ['server.py', '--port', String(port)], {
    cwd: ROOT,
    env: { ...process.env, MODULAR_DB: join(dir, 'test.db') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let log = '';
  child.stdout.on('data', (d) => (log += d));
  child.stderr.on('data', (d) => (log += d));
  const base = `http://127.0.0.1:${port}`;
  await waitFor(async () => (await fetch(base + '/api/tasks')).ok, 'the server to answer\n' + log);
  return {
    base,
    port,
    async close() {
      await stop(child);
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

// One headless Chrome. page.eval(fn) runs a function in the page and returns its JSON result.
export async function startBrowser() {
  const chrome = findChrome();
  if (!chrome) return null;
  const port = await freePort();
  const profile = mkdtempSync(join(tmpdir(), 'modular-chrome-'));
  const child = spawn(
    chrome,
    ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'],
    { stdio: 'ignore' },
  );
  const targets = await waitFor(async () => {
    const t = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    return t.find((x) => x.type === 'page') && t;
  }, 'Chrome to start');
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r, j) => ((ws.onopen = r), (ws.onerror = j)));
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) (pending.get(d.id)(d), pending.delete(d.id));
    else if (d.method) events.push(d);
  };
  const send = (method, params = {}) =>
    new Promise((r) => {
      const n = ++id;
      pending.set(n, r);
      ws.send(JSON.stringify({ id: n, method, params }));
    });
  await send('Page.enable');
  await send('Runtime.enable');
  return {
    async open(url, { view = '1200x1000', init } = {}) {
      const [w, h] = view.split('x').map(Number);
      await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false });
      if (init) await send('Page.addScriptToEvaluateOnNewDocument', { source: init });
      await send('Page.navigate', { url });
      await waitFor(async () => (await this.eval(() => document.readyState)) === 'complete', 'the page to load');
      await sleep(400);
    },
    // Runs `fn` (a function, or its source) in the page; returns its value. Throws if the page threw.
    async eval(fn, arg) {
      const src = typeof fn === 'function' ? `(${fn.toString()})(${JSON.stringify(arg ?? null)})` : fn;
      const r = await send('Runtime.evaluate', { expression: `(async()=>{return await ${src}})()`, awaitPromise: true, returnByValue: true });
      if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text);
      return r.result?.result?.value;
    },
    async errors() {
      return events.filter((e) => e.method === 'Runtime.exceptionThrown').map((e) => e.params.exceptionDetails.exception?.description || e.params.exceptionDetails.text);
    },
    async screenshot(file) {
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      (await import('node:fs')).writeFileSync(file, Buffer.from(shot.result.data, 'base64'));
    },
    async close() {
      try {
        ws.close();
      } catch {}
      await stop(child);
      try {
        rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 150 }); // Chrome may still be writing as it exits
      } catch {}
    },
    pid: child.pid,
  };
}

// Extracts a named region of index.html (by its ▸ marker) as source text.
export function region(name) {
  const lines = readFileSync(join(ROOT, 'index.html'), 'utf8').split('\n');
  const marker = /(?:\/\*|<!--)\s*▸\s*(.+?)\s*(?:\*\/|-->)\s*$/;
  const at = lines.findIndex((l) => (marker.exec(l) || [])[1] === name);
  if (at < 0) throw new Error('no region named ' + name);
  let end = lines.length;
  for (let i = at + 1; i < lines.length; i++) if (marker.test(lines[i])) { end = i; break; }
  return lines.slice(at + 1, end).join('\n');
}

export function pythonCompiles(files) {
  return spawnSync('python3', ['-m', 'py_compile', ...files], { cwd: ROOT, encoding: 'utf8' });
}
