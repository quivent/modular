import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from '../lib/harness.mjs';
export const name = 'flag data: what tools/flags.py extracted from each engine\'s documentation';

export default async function (t) {
  const dir = join(ROOT, 'catalog', 'flags');
  const floor = { vllm: 300, sglang: 400, llama: 240, tgi: 50, trtllm: 45, ollama: 25, mlx: 20, 'sglang-diffusion': 45, 'vllm-omni': 80 };
  const files = readdirSync(dir).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', '')).sort();
  t.equal(files, Object.keys(floor).sort(), 'there is a flag file for each engine');
  for (const engine of Object.keys(floor)) {
    const d = JSON.parse(readFileSync(join(dir, engine + '.json'), 'utf8'));
    const all = d.sections.flatMap((s) => s.flags);
    t.ok(all.length >= floor[engine], `${engine}: at least ${floor[engine]} flags (has ${all.length})`);
    t.equal(all.length, d.count, `${engine}: the recorded count matches the flags present`);
    t.equal(all.filter((f) => !f.name || !/^[-A-Z]/.test(f.name)).length, 0, `${engine}: every flag has a name that looks like a flag`);
    const seen = new Map();
    for (const f of all) seen.set(f.name, (seen.get(f.name) || 0) + 1);
    t.equal([...seen].filter(([, n]) => n > 1).map(([k]) => k), [], `${engine}: no flag is listed twice`);
    t.ok(/^https:\/\//.test(d.source) && /^\d{4}-\d\d-\d\d$/.test(d.fetched), `${engine}: records where it came from and when`);
    t.equal(d.sections.filter((s) => !s.title || !s.flags.length).length, 0, `${engine}: no empty or untitled section`);
  }
  const vllm = JSON.parse(readFileSync(join(dir, 'vllm.json'), 'utf8')).sections.flatMap((s) => s.flags);
  const g = vllm.find((f) => f.name === '--gpu-memory-utilization');
  t.ok(g && g.default === '0.92', 'a known fact holds: vLLM documents --gpu-memory-utilization default 0.92', JSON.stringify(g && g.default));
}
