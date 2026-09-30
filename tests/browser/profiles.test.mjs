import { startServer, startBrowser } from '../lib/harness.mjs';
export const name = 'engine profiles: data-driven commands match the hand-written ones, flag for flag';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const r = await browser.eval(() => {
      // a small seeded generator so a failure can be reproduced
      let seed = 20260930;
      const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
      const pick = (a) => a[Math.floor(rnd() * a.length)];
      const base = spec();
      const outputs = new Set();
      let mismatches = [], checked = 0;
      const compare = (profile, c) => command(c) === profileCommand(profile, c);
      for (let i = 0; i < 4000; i++) {
        const c = JSON.parse(JSON.stringify(base));
        c.runtime.server = 'vllm';
        c.runtime.host = pick(['127.0.0.1', '0.0.0.0', '', "it's.example", 'example.com']);
        c.runtime.port = pick([8000, 8080, 30000, 9]);
        c.runtime.context_tokens = pick([4096, 8192, 32768, 131072]);
        c.runtime.parallel_devices = pick([1, 2, 4, 8]);
        c.runtime.pipeline_stages = pick([1, 1, 2, 4]);
        c.runtime.cpu_offload_gb = pick([0, 0, 8, 20]);
        c.runtime.kv_cache_gb = pick([0, 0, 10, 20]);
        c.runtime.gpu_memory_percent = pick([50, 85, 90, 95]);
        c.runtime.request_logging = pick([true, false]);
        c.runtime.quantization = pick(['Native / auto', 'Native / auto', 'FP8', 'AWQ', 'GPTQ', 'bitsandbytes']);
        c.runtime.trust_model_code = pick([true, false]);
        c.runtime.prefix_cache = pick([true, false]);
        c.runtime.extra_arguments = pick([null, null, '--foo bar', "--name 'x y'"]);
        c.runtime.reasoning_parser = pick([true, false]);
        c.runtime.tool_call_parser = pick([true, false]);
        c.runtime.scheduling = { ...c.runtime.scheduling,
          policy: pick(['fcfs', 'priority']), max_num_batched_tokens: pick([null, null, 2048, 8192]), max_num_seqs: pick([null, 64, 256]),
          chunked_prefill: pick([true, false]), enforce_eager: pick([true, false]),
          dtype: pick(['auto', 'auto', 'bfloat16', 'float16']), kv_cache_dtype: pick(['auto', 'auto', 'fp8']) };
        c.model.build = pick([null, null, 'FP8']);
        c.model.ornith_profile = pick([true, false]);
        c.model.served_name = pick(['Ornith-1.5-9B', "o'k"]);
        c.model.reference = pick(['Qwen/Qwen3.8-27B', 'org/name', "weird'name", '']);
        const a = command(c), b = profileCommand(ENGINE_PROFILES.vllm, c);
        outputs.add(a);
        checked++;
        if (a !== b && mismatches.length < 3) mismatches.push({ a, b });
      }
      // the comparison has teeth: swapping two rules in a copy of the profile must be noticed
      const broken = JSON.parse(JSON.stringify(ENGINE_PROFILES.vllm));
      [broken.rules[1], broken.rules[2]] = [broken.rules[2], broken.rules[1]];
      const c0 = JSON.parse(JSON.stringify(base));
      const noticed = command(c0) !== profileCommand(broken, c0);
      return { checked, distinct: outputs.size, mismatches, noticed };
    });
    t.equal(r.mismatches, [], `the vLLM profile reproduces the hand-written command exactly (${r.checked} random configurations)`);
    t.ok(r.distinct > 500, `the sample exercised many different commands (${r.distinct} distinct)`);
    t.ok(r.noticed, 'the comparison notices a wrong profile (two rules swapped)');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
