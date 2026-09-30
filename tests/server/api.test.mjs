import { connect } from 'node:net';
import { createHash, randomBytes } from 'node:crypto';
import { startServer, sleep } from '../lib/harness.mjs';
export const name = 'server: tasks API, saved state, safety rules, live events over a WebSocket';

const J = { 'Content-Type': 'application/json' };

// A minimal WebSocket client over a raw socket, so the test can send its own Origin header.
function wsOpen(port, { origin, upgrade = true } = {}) {
  return new Promise((resolve, reject) => {
    const s = connect(port, '127.0.0.1');
    const key = randomBytes(16).toString('base64');
    let buf = Buffer.alloc(0), head = null;
    const frames = [], waiters = [];
    const pump = () => {
      while (head && buf.length >= 2) {
        let len = buf[1] & 0x7f, off = 2;
        if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
        if (buf.length < off + len) return;
        const f = { op: buf[0] & 0xf, payload: buf.subarray(off, off + len) };
        buf = buf.subarray(off + len);
        const w = waiters.shift();
        w ? w(f) : frames.push(f);
      }
    };
    s.on('data', (d) => {
      buf = Buffer.concat([buf, d]);
      if (!head) {
        const i = buf.indexOf('\r\n\r\n');
        if (i < 0) return;
        head = buf.subarray(0, i).toString();
        buf = buf.subarray(i + 4);
        resolve({ head, key, next: () => new Promise((r) => (frames.length ? r(frames.shift()) : waiters.push(r))), send: (op, payload = Buffer.alloc(0)) => {
          const mask = randomBytes(4);
          s.write(Buffer.concat([Buffer.from([0x80 | op, 0x80 | payload.length]), mask, Buffer.from(payload.map((b, i) => b ^ mask[i % 4]))]));
        }, close: () => s.destroy() });
      }
      pump();
    });
    s.on('error', reject);
    s.write(`GET /api/events HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\n` + (upgrade ? `Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: ${key}\r\nSec-WebSocket-Version: 13\r\n` : '') + (origin ? `Origin: ${origin}\r\n` : '') + '\r\n');
  });
}

export default async function (t) {
  const server = await startServer();
  const { base, port } = server;
  try {
    const call = async (method, path, body, headers = {}) => {
      const r = await fetch(base + path, { method, headers: { ...J, ...headers }, body: body === undefined ? undefined : JSON.stringify(body) });
      let data = null;
      try { data = await r.json(); } catch {}
      return { status: r.status, data };
    };

    // ── tasks ──
    let r = await call('GET', '/api/tasks');
    t.ok(r.status === 200 && r.data.tasks.length >= 22 && r.data.groups.length >= 4, 'the tracker seeds from the roadmap on first run');
    r = await call('POST', '/api/tasks', { group: 'trust', title: 'probe task' });
    const id = r.data.id;
    t.equal([r.status, r.data.status], [201, 'todo'], 'create a task');
    r = await call('PATCH', `/api/tasks/${id}`, { status: 'done' });
    t.ok(r.status === 200 && r.data.status === 'done' && r.data.done_at, 'mark it done, and it records when');
    t.equal((await call('PATCH', `/api/tasks/${id}`, { status: 'bogus' })).status, 400, 'an invalid status is refused');
    t.equal((await call('POST', '/api/tasks', { group: 'nope', title: 'x' })).status, 400, 'an unknown group is refused');
    t.equal((await call('PATCH', '/api/tasks/999999', { status: 'done' })).status, 404, 'a missing task is 404');
    t.equal((await call('DELETE', `/api/tasks/${id}`)).status, 200, 'delete it');

    // ── saved state ──
    r = await call('GET', '/api/state');
    t.equal([r.data.version, r.data.empty], [1, true], 'state starts empty at version 1');
    const state = { version: 1, favorites: ['Qwen/Qwen3.8-27B'], defaultModel: 'Qwen/Qwen3.8-27B', configs: [{ name: 'a', modelRef: 'x', snapshot: { server: 'vllm', v: 1 } }], preferences: { hfNamespace: 'me' } };
    t.equal((await call('PUT', '/api/state', state)).status, 200, 'state can be saved');
    r = await call('GET', '/api/state');
    t.ok(r.data.favorites[0] === 'Qwen/Qwen3.8-27B' && r.data.configs[0].snapshot.v === 1 && r.data.preferences.hfNamespace === 'me' && r.data.defaultModel === 'Qwen/Qwen3.8-27B', 'and comes back whole');
    t.equal((await call('PUT', '/api/state', { ...state, version: 2 })).status, 400, 'state from a newer version is refused, not overwritten');
    t.equal((await call('PUT', '/api/state', { favorites: 'x' })).status, 400, 'malformed state is refused');

    // ── safety ──
    for (const p of ['/db/schema.sql', '/db/modular.db', '/.git/config', '/../etc/passwd'])
      t.equal((await fetch(base + p, { redirect: 'manual' })).status, 404, `${p} is never served`);
    // fetch() will not send a custom Host header, so this goes over a raw socket
    const status = await new Promise((res) => {
      const c = connect(port, '127.0.0.1');
      let got = '';
      c.on('data', (d) => { got += d; if (got.includes('\r\n')) { res(got.split('\r\n')[0]); c.destroy(); } });
      c.write('GET /api/tasks HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n');
    });
    t.ok(/ 403 /.test(status), 'a request addressed to another host is refused (DNS-rebinding guard)', status);
    r = await call('POST', '/api/tasks', { group: 'trust', title: 'x' }, { 'Content-Type': 'text/plain' });
    t.equal(r.status, 400, 'writes need a JSON body');
    t.equal((await fetch(base + '/favicon.ico')).status, 204, 'the favicon request is answered quietly');

    // ── live events ──
    const ws = await wsOpen(port);
    const accept = createHash('sha1').update(ws.key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    t.ok(/^HTTP\/1\.1 101/.test(ws.head) && ws.head.includes(accept), 'the WebSocket handshake is valid HTTP/1.1 and proves the key');
    t.equal(JSON.parse((await ws.next()).payload.toString()).event, 'hello', 'the server greets each subscriber');
    const created = (await call('POST', '/api/tasks', { group: 'reach', title: 'event probe' })).data;
    let ev = JSON.parse((await ws.next()).payload.toString());
    t.ok(ev.event === 'task.created' && ev.task.title === 'event probe', 'creating a task is pushed');
    await call('PATCH', `/api/tasks/${created.id}`, { status: 'doing' });
    ev = JSON.parse((await ws.next()).payload.toString());
    t.ok(ev.event === 'task.updated' && ev.task.status === 'doing', 'changing a task is pushed');
    await call('DELETE', `/api/tasks/${created.id}`);
    ev = JSON.parse((await ws.next()).payload.toString());
    t.equal([ev.event, ev.id], ['task.deleted', created.id], 'deleting a task is pushed');
    ws.send(0x9, Buffer.from('hi'));
    const pong = await ws.next();
    t.ok(pong.op === 0xa && pong.payload.toString() === 'hi', 'a ping is answered with the same payload');
    const other = await wsOpen(port);
    await other.next();
    other.close();
    await sleep(150);
    await call('PATCH', `/api/tasks/${(await call('POST', '/api/tasks', { group: 'reach', title: 'after a peer left' })).data.id}`, { status: 'done' });
    let alive = true;
    ev = JSON.parse((await ws.next()).payload.toString());
    ev = JSON.parse((await ws.next()).payload.toString());
    t.equal(ev.event, 'task.updated', 'the other subscribers keep receiving after one disconnects');
    ws.send(0x8, Buffer.from([0x03, 0xe8]));
    t.equal((await ws.next()).op, 0x8, 'a close is echoed');
    ws.close();
    t.ok(/^HTTP\/1\.\d 403/.test((await wsOpen(port, { origin: 'http://evil.example' })).head), 'a WebSocket from another site is refused');
    t.ok(/^HTTP\/1\.\d 400/.test((await wsOpen(port, { upgrade: false })).head), 'a plain request to the events address is refused');
  } finally {
    await server.close();
  }
}
