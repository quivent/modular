import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { region } from '../lib/harness.mjs';
export const name = 'memory estimate: will it start? (weights, KV cache, heads, offload, card memory)';

export default async function (t) {
  const ctx = vm.createContext({});
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
  t.ok(r.level === 'fail' && /holds only about 31,600 tokens/.test(r.text) && /FP8/.test(r.text), 'KV too small for the context, suggests FP8 KV', r.text);
  t.equal(est('Qwen/Qwen3-8B', { contextTokens: 40960, kvFp8: true }).level, 'ok', 'FP8 KV doubles the room');
  r = est('Qwen/Qwen3-8B');
  t.ok(r.level === 'ok' && /weights about 15 GB/.test(r.text) && /about 3 full-length/.test(r.text), 'fits with room for 3 full-length requests', r.text);
  t.ok(/full-length/.test(est('ibm-granite/granite-4.2-8b').text), 'Granite 4.2 gets the full KV check');
  t.equal(est('mistralai/Ministral-3-14B-Instruct-2512', { contextTokens: 131072 }).level, 'fail', 'Ministral 3 14B at 128K on 24 GB');

  // weights only, exact file sizes
  r = est('openai/gpt-oss-20b');
  t.ok(r.level === 'ok' && /13 GB/.test(r.text) && /not estimated/.test(r.text), 'gpt-oss 20B uses its real 12.8 GiB of files', r.text);
  t.ok(est('Qwen/Qwen3.8-27B', { vramGb: 80 }).level === 'ok' && est('Qwen/Qwen3.8-27B').level === 'fail', 'Qwen3.8 27B: fits 80 GB, not 24 GB');
  t.equal(est('deepseek-ai/DeepSeek-V4.1-Flash', { vramGb: 80, tp: 8 }).level, 'ok', 'DeepSeek V4.1 Flash fits 8 x 80 GB');

  // heads must divide across GPUs
  r = est('Qwen/Qwen2.5-VL-7B-Instruct', { tp: 8, vramGb: 80 });
  t.ok(r.level === 'fail' && /28 attention heads/.test(r.text) && /1, 2, 4 GPUs/.test(r.text), '28 heads cannot split 8 ways', r.text);

  // offload, fixed KV, precision
  t.ok(/after CPU offload/.test(est('Qwen/Qwen3-32B', { offloadGb: 20 }).text), 'says the figure is after offload');
  t.ok(/Fixed KV cache/.test(est('Qwen/Qwen3-8B', { kvGb: 10 }).text), 'fixed KV that overflows the GPU is caught');
  t.equal(estimateFit(M['Qwen/Qwen3-8B'], { ...base, quant: 'my-quant' }), null, 'unknown quantization is not estimated');

  // every current-generation shape carries what the estimate needs
  const bad = Object.entries(M).filter(([ref, s]) => !s.billions || (s.gib !== undefined && !(s.gib > 0)) || (!s.noKv && s.gib !== undefined && !(s.layers && s.kvHeads && s.headDim)));
  t.equal(bad.map((x) => x[0]), [], 'no shape is missing weights or KV numbers it claims to have');
}
