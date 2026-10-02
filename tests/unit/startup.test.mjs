import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';
import { region, ROOT } from '../lib/harness.mjs';
export const name = 'will it start: engine support, custom code, and quantization are judged from what the model and the engine declare';

export default async function (t) {
  const page = readFileSync(join(ROOT, 'index.html'), 'utf8');
  const lines = (id) => Object.assign({}, ...page.match(new RegExp(`id="${id}">\\n([\\s\\S]*?)\\n</script>`))[1].split('\n').map((l) => JSON.parse(l)));
  const flags = lines('flagData'), facts = lines('factData');
  const ctx = vm.createContext({});
  vm.runInContext(region('js: will it start') + '\nthis.f = { engineLists, supportProblem, needsTrust, quantProblem };', ctx);
  const { engineLists, supportProblem, needsTrust, quantProblem } = ctx.f;
  const sup = (e) => flags[e].support;

  // every engine we hold a list for has a real one
  for (const e of ['vllm', 'llama', 'trtllm', 'mlx', 'sglang', 'tgi']) t.ok(sup(e) && sup(e).names.length > 30, `${e}: its list of supported architectures is in the page (${sup(e) && sup(e).names.length})`);

  // judging a model against a list
  t.equal(engineLists(sup('vllm'), facts['Qwen/Qwen3.8-27B']), true, 'vLLM lists Qwen3.8 27B\'s architecture');
  t.equal(engineLists(sup('vllm'), { arch: ['NotARealForCausalLM'], type: 'nope' }), false, 'and not one that does not exist');
  t.equal(engineLists(sup('vllm'), undefined), null, 'no facts means no opinion');
  t.equal(engineLists(undefined, facts['Qwen/Qwen3.8-27B']), null, 'and no list means no opinion');
  t.equal(engineLists(sup('mlx'), { type: 'gemma4_unified' }), true, 'MLX\'s own remapping counts (gemma4_unified runs as gemma4)');
  t.equal(engineLists(sup('mlx'), facts['Qwen/Qwen3.8-Flash-Next']), false, 'MLX does not list a model type it has no module for');

  // the warning, and when it is not given
  const flash = facts['Qwen/Qwen3.8-Flash-Next'];
  let p = supportProblem({ engine: 'mlx', name: 'MLX', support: sup('mlx'), facts: flash, hasBuild: false });
  t.ok(/MLX's own list of supported models does not include Qwen4ExpForConditionalGeneration/.test(p), 'a model the engine does not list is named in the warning', p);
  t.equal(supportProblem({ engine: 'mlx', name: 'MLX', support: sup('mlx'), facts: flash, hasBuild: true }), '', 'but not when a converted build already exists (someone ran it)');
  t.equal(supportProblem({ engine: 'vllm', name: 'vLLM', support: sup('vllm'), facts: facts['Qwen/Qwen3.8-27B'], hasBuild: false }), '', 'nothing to say about a model the engine lists');
  p = supportProblem({ engine: 'vllm', name: 'vLLM', support: sup('vllm'), facts: { arch: ['NotARealForCausalLM'] }, hasBuild: false });
  t.ok(/fall back to the Transformers library/.test(p), 'vLLM\'s case is told as it is: it falls back instead of refusing', p);

  // custom code
  t.equal(needsTrust(sup('vllm'), facts['jinaai/jina-reranker-v3.5']), !engineLists(sup('vllm'), facts['jinaai/jina-reranker-v3.5']), 'a model with its own code needs trust only where the engine lacks the architecture');
  t.equal(needsTrust(sup('vllm'), facts['moonshotai/Kimi-K3']), false, 'Kimi-K3 ships code but vLLM has it built in: no trust needed');
  t.equal(needsTrust(sup('vllm'), facts['Qwen/Qwen3.8-27B']), false, 'a model that ships no code never does');
  t.equal(needsTrust(undefined, { custom: true, arch: ['X'] }), true, 'with no list to say otherwise, shipped code is trusted-or-fails: trust is added');

  // quantization
  const bf16 = facts['Qwen/Qwen3.8-27B'];
  t.ok(/AWQ loads a checkpoint that was published in AWQ.*not quantized/.test(quantProblem('AWQ', bf16)), 'AWQ on a plain bf16 repository is refused', quantProblem('AWQ', bf16));
  t.ok(/is FP8/.test(quantProblem('GPTQ', facts['zai-org/GLM-5.3'])), 'and a repository published in FP8 is not a GPTQ one', quantProblem('GPTQ', facts['zai-org/GLM-5.3']));
  t.equal(quantProblem('AWQ', { quant: 'awq' }), '', 'a checkpoint published in AWQ loads as AWQ');
  t.equal(quantProblem('NVFP4', { quant: 'modelopt' }), '', 'and ModelOpt checkpoints serve as NVFP4');
  t.equal([quantProblem('FP8', bf16), quantProblem('Native / auto', bf16), quantProblem('bitsandbytes', bf16)], ['', '', ''], 'FP8, native and bitsandbytes quantize on the fly: always fine');
}
