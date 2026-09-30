import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ROOT, freePort, sleep } from '../lib/harness.mjs';
export const name = 'server: an older database is upgraded in place and keeps its data';

export default async function (t) {
  const dir = mkdtempSync(join(tmpdir(), 'modular-mig-'));
  const db = join(dir, 'old.db');
  const sql = (q) => spawnSync('sqlite3', [db, q], { encoding: 'utf8' });
  try {
    if (spawnSync('sqlite3', ['-version']).status !== 0) return t.skip('sqlite3 command not found');
    // a database exactly as version 2 of the schema made it
    spawnSync('sqlite3', [db], { input: readFileSync(join(ROOT, 'tests', 'fixtures', 'schema-v2.sql'), 'utf8') });
    sql("INSERT INTO task_groups(slug,title,position) VALUES('g','G',1); INSERT INTO tasks(group_id,title) VALUES(1,'keep me');" +
        "INSERT INTO saved_configurations(name,model_ref,engine,settings) VALUES('old','a/b','vllm','{\"server\":\"vllm\"}'),('newer','c/d','sglang','{\"server\":\"sglang\",\"v\":1}');" +
        "INSERT INTO favorite_models(model_ref,position) VALUES('a/b',0);");
    t.equal(sql('PRAGMA user_version;').stdout.trim(), '2', 'the fixture is a version 2 database');
    const port = await freePort();
    const child = spawn('python3', ['server.py', '--port', String(port)], { cwd: ROOT, env: { ...process.env, MODULAR_DB: db }, stdio: 'ignore' });
    try {
      let up = false;
      for (let i = 0; i < 60 && !up; i++) { try { up = (await fetch(`http://127.0.0.1:${port}/api/tasks`)).ok; } catch { await sleep(150); } }
      t.ok(up, 'the server starts on it');
      t.equal(sql('PRAGMA user_version;').stdout.trim(), '3', 'and upgrades it to the current version');
      t.equal(sql('SELECT title FROM tasks;').stdout.trim(), 'keep me', 'tasks survive');
      t.equal(sql('SELECT name || ":" || snapshot_version FROM saved_configurations ORDER BY id;').stdout.trim().split('\n'), ['old:0', 'newer:1'], 'saved setups survive, with their snapshot version filled in');
      const s = await (await fetch(`http://127.0.0.1:${port}/api/state`)).json();
      t.equal([s.version, s.configs.length, s.favorites], [1, 2, ['a/b']], 'and they are served as state');
    } finally {
      child.kill('SIGTERM');
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
