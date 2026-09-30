#!/usr/bin/env node
// Runs every tests/**/*.test.mjs, each in its own process, and prints one line per check.
//   node tests/run.mjs            all tests
//   node tests/run.mjs unit       only files whose path contains "unit"
import { readdirSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve, dirname, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = resolve(dirname(fileURLToPath(import.meta.url)));
const filter = process.argv[2];

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? (f === 'lib' ? [] : walk(p)) : f.endsWith('.test.mjs') ? [p] : [];
  });
}

if (process.argv[3] === '--child') {
  // child mode: run one test file and print JSON
  const mod = await import(pathToFileURL(process.argv[2]).href);
  const results = [];
  const t = {
    equal: (a, b, what) => results.push({ ok: JSON.stringify(a) === JSON.stringify(b), what, detail: JSON.stringify(a) === JSON.stringify(b) ? '' : `expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}` }),
    ok: (v, what, detail = '') => results.push({ ok: !!v, what, detail: v ? '' : detail }),
    skip: (why) => results.push({ skip: why }),
  };
  try {
    await mod.default(t);
  } catch (e) {
    results.push({ ok: false, what: 'test ran to completion', detail: String(e.stack || e).split('\n').slice(0, 4).join(' | ') });
  }
  console.log('@@RESULTS@@' + JSON.stringify({ name: mod.name || process.argv[2], results }));
  process.exit(0);
}

const files = walk(here).filter((f) => !filter || relative(here, f).includes(filter)).sort();
let pass = 0, fail = 0, skipped = 0;
for (const file of files) {
  const r = spawnSync('node', [fileURLToPath(import.meta.url), file, '--child'], { encoding: 'utf8', timeout: 180000 });
  const m = /@@RESULTS@@(.*)/.exec(r.stdout || '');
  const rel = relative(here, file);
  if (!m) {
    fail++;
    console.log(`FAIL  ${rel}\n      crashed: ${(r.stderr || r.stdout || 'no output').split('\n').slice(0, 4).join(' | ')}`);
    continue;
  }
  const { name, results } = JSON.parse(m[1]);
  console.log(`\n${rel}: ${name}`);
  for (const x of results) {
    if (x.skip) { skipped++; console.log(`  SKIP  ${x.skip}`); }
    else if (x.ok) { pass++; console.log(`  pass  ${x.what}`); }
    else { fail++; console.log(`  FAIL  ${x.what}\n        ${x.detail}`); }
  }
}
console.log(`\n${pass} passed, ${fail} failed, ${skipped} skipped`);
process.exit(fail ? 1 : 0);
