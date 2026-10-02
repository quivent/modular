import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { join } from 'node:path';
import { region, ROOT } from '../lib/harness.mjs';
export const name = 'memory estimate: will it start? (weights, KV cache, heads, offload, card memory)';

export default async function (t) {
  // the model facts arrive the way they do in the page: as the generated block
  const facts = readFileSync(join(ROOT, 'index.html'), 'utf8').match(/id="factData">\n([\s\S]*?)\n<\/script>/)[1];
  const ctx = vm.createContext({ document: { getElementById: (id) => (id === 'factData' ? { textContent: facts } : null) } });
  vm.runInContext(region('js: memory estimate') + '\nthis.estimateFit = estimateFit; this.MEMORY_SHAPES = MEMORY_SHAPES;', ctx);
  const { estimateFit, MEMORY_SHAPES: M } = ctx;
  const base = { tp: 1, pp: 1, vramGb: 24, utilPercent: 90, contextTokens: 8192, quant: 'Native / auto', dtype: 'auto', kvFp8: false, offloadGb: 0, kvGb: 0 };
  const est = (ref, o = {}) => estimateFit(M[ref], { ...base, ...o });

  // weights that cannot fit
  let r = est('meta-llama/Llama-3.3-70B-Instruct');
  t.equal(r.level, 'fail', '70B bf16 does not fit one 24 GB card');
  t.ok(/131 GB/.test(r.text) && /at least 7/.test(r.text), 'says how much and how many GPUs', r.text);
  t.ok(/FP8 build needs about 66 GB \(4 of/.test(r.text), 'offers FP8 only when it saves memory', r.text);
  r = est('deepseek-ai/DeepSeek-V4.1-Flash', { vramGb: 80 });
  t.ok(r.level === 'fail' && !/FP8 build/.test(r.text), 'no FP8 hint when the checkpoint is already smaller than FP8', r.text);

  // KV cache
  r = est('Qwen/Qwen3-8B', { contextTokens: 40960 });
  t.ok(r.level === 'fail' && /holds only about 31,300 tokens/.test(r.text) && /FP8/.test(r.text), 'KV too small for the context, suggests FP8 KV', r.text);
  t.equal(est('Qwen/Qwen3-8B', { contextTokens: 40960, kvFp8: true }).level, 'ok', 'FP8 KV doubles the room');
  r = est('Qwen/Qwen3-8B');
  t.ok(r.level === 'ok' && /weights about 15 GB/.test(r.text) && /about 3 full-length/.test(r.text), 'fits with room for 3 full-length requests', r.text);
  t.ok(/full-length/.test(est('ibm-granite/granite-4.2-8b').text), 'Granite 4.2 gets the full KV check');
  t.equal(est('mistralai/Ministral-3-14B-Instruct-2512', { contextTokens: 131072 }).level, 'fail', 'Ministral 3 14B at 128K on 24 GB');

  // weights only, exact file sizes
  r = est('openai/gpt-oss-20b');
  t.ok(r.level === 'ok' && /13 GB/.test(r.text) && /full-length/.test(r.text), 'gpt-oss 20B uses its real 12.8 GiB of files, and its sliding-window cache is counted', r.text);
  t.ok(est('Qwen/Qwen3.8-27B', { vramGb: 80 }).level === 'ok' && est('Qwen/Qwen3.8-27B').level === 'fail', 'Qwen3.8 27B: fits 80 GB, not 24 GB');
  t.equal(est('deepseek-ai/DeepSeek-V4.1-Flash', { vramGb: 80, tp: 8 }).level, 'ok', 'DeepSeek V4.1 Flash fits 8 x 80 GB');

  // heads must divide across GPUs
  r = est('Qwen/Qwen2.5-VL-7B-Instruct', { tp: 8, vramGb: 80 });
  t.ok(r.level === 'fail' && /28 attention heads/.test(r.text) && /1, 2, 4 GPUs/.test(r.text), '28 heads cannot split 8 ways', r.text);

  // offload, fixed KV, precision
  t.ok(/after CPU offload/.test(est('Qwen/Qwen3-32B', { offloadGb: 20 }).text), 'says the figure is after offload');
  t.ok(/Fixed KV cache/.test(est('Qwen/Qwen3-8B', { kvGb: 10 }).text), 'fixed KV that overflows the GPU is caught');
  t.equal(estimateFit(M['Qwen/Qwen3-8B'], { ...base, quant: 'my-quant' }), null, 'unknown quantization is not estimated');

  // every shape is well formed
  const wellFormed = (kv) => !kv || (['full', 'slide', 'mla'].every((k) => !kv[k] || (Array.isArray(kv[k]) && kv[k].every((n) => n > 0))));
  const bad = Object.entries(M).filter(([ref, f]) => (f.gib !== undefined && !(f.gib > 0)) || !wellFormed(f.kv));
  t.equal(bad.map((x) => x[0]), [], 'no model fact is malformed');

  // the model's own limits
  r = est('Qwen/Qwen3-8B', { contextTokens: 131072, vramGb: 80 });
  t.ok(r.level === 'fail' && /at most 40,960 tokens/.test(r.text), 'a context longer than the model supports is refused', r.text);
  r = est('Qwen/Qwen3.8-27B', { tp: 3, vramGb: 80 });
  t.ok(r.level === 'fail' && /4 key-value heads cannot be split across 3/.test(r.text), 'tensor parallelism must divide the KV heads, not only the heads', r.text);
  t.equal(est('Qwen/Qwen3.8-27B', { tp: 8, vramGb: 80 }).level, 'ok', 'more GPUs than KV heads repeats them, which is allowed');

  // each attention design is counted by its own rule
  r = est('Qwen/Qwen3.8-27B', { vramGb: 80, contextTokens: 262144 });
  t.ok(r.level === 'ok' && /full-length/.test(r.text), 'hybrid linear attention: only the full-attention layers cost per token', r.text);
  r = est('google/gemma-4-31B-it', { vramGb: 80, contextTokens: 262144 });
  t.ok(r.level === 'fail' && /KV cache holds only about/.test(r.text), 'Gemma 4 at its full 262K context does not leave room for the cache on 80 GB', r.text);
  t.equal(est('google/gemma-4-31B-it', { vramGb: 80, contextTokens: 32768 }).level, 'ok', 'and at 32K it does (sliding layers stop growing at their window)');
  t.ok(/full-length/.test(est('zai-org/GLM-5.3', { vramGb: 288, tp: 8, contextTokens: 131072 }).text), 'compressed-latent attention (GLM-5.3) is counted');
  t.ok(/not estimated/.test(est('deepseek-ai/DeepSeek-V4.1-Flash', { vramGb: 80, tp: 8 }).text), 'a design that cannot be counted honestly says so instead of guessing');
  r = est('Qwen/Qwen3-VL-Embedding-8B', { vramGb: 12, contextTokens: 8192, weightsOnly: true });
  t.ok(r.level === 'fail' && /Weights need about/.test(r.text), 'embedding models are checked for weights only');
}
