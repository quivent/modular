import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { ROOT } from '../lib/harness.mjs';
export const name = 'bundle: the flag lists inside index.html are exactly what catalog/flags/*.json says';

export default async function (t) {
  const check = spawnSync('node', [join(ROOT, 'tools', 'bundle.mjs'), '--check'], { encoding: 'utf8' });
  t.ok(check.status === 0, 'the embedded block matches the data files' + (check.status ? ' — fix: python3 -m librarian sync' : ''), (check.stdout || '').trim());

  const page = readFileSync(join(ROOT, 'index.html'), 'utf8');
  const m = page.match(/<script type="application\/json" id="flagData">\n([\s\S]*?)\n<\/script>/);
  t.ok(!!m, 'the page has its flag data block');
  const embedded = Object.assign({}, ...m[1].split('\n').map((l) => JSON.parse(l)));
  const dir = join(ROOT, 'catalog', 'flags');
  const files = readdirSync(dir).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
  t.equal(Object.keys(embedded).sort(), files, 'every engine with a data file is in the page');

  const a = page.indexOf('var HELP_FILLER'), b = page.indexOf('function flagLine(');
  const ctx = vm.createContext({});
  vm.runInContext(page.slice(a, b), ctx);
  let flags = 0, differing = [], dated = [];
  for (const engine of files) {
    const src = JSON.parse(readFileSync(join(dir, engine + '.json'), 'utf8'));
    const e = embedded[engine];
    const srcFlags = src.sections.flatMap((s) => s.flags);
    const embFlags = e.sections.flatMap((s) => s.flags);
    flags += embFlags.length;
    if (srcFlags.map((f) => f.name).join() !== embFlags.map((f) => f.name).join()) differing.push(engine + ': names or order');
    if (e.fetched !== src.fetched || e.source !== src.source) dated.push(engine);
    // the text kept for the page must survive the page's own rules unchanged
    for (const f of embFlags) if (f.help && ctx.flagHelpText(f) !== f.help) differing.push(engine + ' ' + f.name + ': description is not stable');
  }
  t.equal(differing, [], `${flags} flags: same names in the same order, descriptions stable`);
  t.equal(dated, [], 'each engine keeps its source and the date it was read');
  t.ok(page.length < 600000, 'the page stays a sensible size', String(page.length));
}
