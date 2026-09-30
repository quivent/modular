// Seeded random configurations, built inside the page from spec(), so a failure can be reproduced.
// Used by the golden-command test and by anything that needs many different valid configurations.
export const PAGE_SOURCE = `
function makeRandomConfigs(engine, count, seed0) {
  let seed = seed0;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const base = spec();
  const out = [];
  for (let i = 0; i < count; i++) {
    const c = JSON.parse(JSON.stringify(base));
    c.runtime.server = engine;
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
    c.runtime.scheduling = Object.assign({}, c.runtime.scheduling, {
      policy: pick(['fcfs', 'priority']), max_num_batched_tokens: pick([null, null, 2048, 8192]), max_num_seqs: pick([null, 64, 256]),
      chunked_prefill: pick([true, false]), enforce_eager: pick([true, false]),
      dtype: pick(['auto', 'auto', 'bfloat16', 'float16']), kv_cache_dtype: pick(['auto', 'auto', 'fp8']) });
    c.model.build = pick([null, null, 'FP8']);
    c.model.ornith_profile = pick([true, false]);
    c.model.served_name = pick(['Ornith-1.5-9B', "o'k"]);
    c.model.reference = pick(['Qwen/Qwen3.8-27B', 'org/name', "weird'name", '']);
    out.push(c);
  }
  return out;
}
`;
