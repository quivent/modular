import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';
import { ROOT } from '../lib/harness.mjs';
export const name = 'flag descriptions: long ones are cut, reprints of the flag are hidden, informative ones stay';

export default async function (t) {
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  const a = html.indexOf('var HELP_FILLER');
  const b = html.indexOf('function flagLine(');
  const ctx = vm.createContext({});
  vm.runInContext(html.slice(a, b), ctx);
  const dir = join(ROOT, 'catalog', 'flags');
  const byName = {};
  let longest = 0;
  const marked = [];
  for (const f of readdirSync(dir)) {
    const d = JSON.parse(readFileSync(join(dir, f), 'utf8'));
    for (const fl of d.sections.flatMap((s) => s.flags)) {
      const shown = ctx.flagHelpText(fl);
      longest = Math.max(longest, shown.length);
      byName[d.engine + ' ' + fl.name] = shown;
      if (/\*\*/.test(shown)) marked.push(d.engine + " " + fl.name);
    }
  }
  t.equal(marked, [], "no markup shows in any description");
  t.ok(longest <= 200, `no description shows longer than 200 characters (longest ${longest})`);
  for (const k of ['vllm --host', 'vllm --port', 'sglang --host', 'sglang --port', 'tgi --hostname', 'trtllm --port', 'sglang --forward-pass-metrics-worker-id'])
    t.equal(byName[k], '', `${k}: shows nothing`);
  for (const k of ['sglang --page-size', 'llama --parallel', 'vllm --served-model-name', 'vllm --offload-backend', 'vllm --shutdown-timeout'])
    t.ok(byName[k], `${k}: keeps a description`);
  t.ok(byName['vllm --served-model-name'].length < 200, 'a long description is cut to one sentence');
}
