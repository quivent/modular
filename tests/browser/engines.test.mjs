import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'engines: llama.cpp, Ollama and MLX get the build they can load; switching engines raises no false warnings';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    await sleep(600);
    const $ = (fn, arg) => browser.eval(fn, arg);
    const click = (sel, text) => $(([s, x]) => { const e = [...document.querySelectorAll(s)].find((b) => b.textContent.trim().startsWith(x)); if (e) e.click(); return !!e; }, [sel, text]);
    const read = () => $(() => ({
      cmd: document.getElementById('output').textContent,
      checks: [...document.querySelectorAll('#checks li')].map((x) => x.textContent),
    }));
    // a model is picked the way a person does: find its family row, take the first size in it
    const pickModel = async (family) => { await $((x) => { const row = [...document.querySelectorAll('#modelList .family-row')].find((r) => r.querySelector('.family-label strong').textContent.startsWith(x)); row && row.querySelector('.model-option').click(); }, family); await sleep(250); };
    // the default model, one engine after another: the checks stay quiet
    const seen = {};
    for (const engine of ['llama.cpp', 'Ollama', 'MLX', 'TGI', 'vLLM']) {
      await click('#serverList .server', engine);
      await sleep(250);
      seen[engine] = await read();
    }
    t.equal(Object.values(seen).flatMap((r) => r.checks).filter((c) => /was not carried/.test(c)), [], 'choosing an engine does not warn about a format nobody chose');
    await click('#serverList .server', 'llama.cpp'); await sleep(200);
    t.ok(/-hf 'unsloth\/Qwen3\.8-27B-GGUF'/.test((await read()).cmd), 'llama.cpp loads the GGUF build, not the original weights');
    await click('#serverList .server', 'Ollama'); await sleep(200);
    t.ok(/ollama pull 'hf\.co\/unsloth\/Qwen3\.8-27B-GGUF'/.test((await read()).cmd), 'Ollama pulls the GGUF build through hf.co');
    await click('#serverList .server', 'MLX'); await sleep(200);
    t.ok(/--model 'mlx-community\/Qwen3\.8-27B-4bit'/.test((await read()).cmd), 'MLX loads the converted build');

    // a model with no GGUF build says so, instead of printing a command that cannot work
    await click('#archChoices .choice', 'Language'); await sleep(100);
    await $(() => { const b = [...document.querySelectorAll('#modelList .model-option')].find((x) => /3 Ultra/.test(x.textContent)); b && b.click(); });
    await click('#serverList .server', 'llama.cpp'); await sleep(250);
    const r = await read();
    t.ok(r.checks.some((c) => /No GGUF build/.test(c)), 'a model with no GGUF build is flagged for llama.cpp', JSON.stringify(r.checks));
    // engines that cannot serve a kind of model are not offered for it
    const offered = async (kind) => { await click('#archChoices .choice', kind); await sleep(200); return $(() => [...document.querySelectorAll('#serverList .server strong')].map((x) => x.textContent)); };
    const retrieval = async (task, name) => {
      await click('#archChoices .choice', 'Retrieval'); await sleep(150);
      const on = await $(() => [...document.querySelectorAll('#archDesign .choice[aria-pressed=true]')].map((b) => b.textContent));
      for (const label of on) await click('#archDesign .choice', label);
      await click('#archDesign .choice', task); await sleep(200);
      await $((x) => { const b = [...document.querySelectorAll('#modelList .model-option')].find((e) => e.textContent.trim().length); b && b.click(); }, name); await sleep(250);
      return $(() => [...document.querySelectorAll('#serverList .server strong')].map((x) => x.textContent));
    };
    t.equal(await retrieval('Embeddings'), ['vLLM', 'SGLang'], 'embedding models: the engines that serve them');
    t.equal(await retrieval('Rerankers'), ['vLLM'], 'rerankers: vLLM');
    t.equal(await offered('Audio'), ['vLLM'], 'speech to text: vLLM');
    t.equal(await offered('Language'), ['vLLM', 'SGLang', 'TensorRT', 'TGI', 'llama.cpp', 'Ollama', 'MLX'], 'and language models get all seven');
    await $(() => { const b = [...document.querySelectorAll('#modelList .model-option')].find((x) => x.textContent.trim().startsWith('27B')); b && b.click(); });
    await click('#serverList .server', 'Ollama'); await sleep(200);
    t.equal((await $(() => document.getElementById('status').hidden ? '' : document.getElementById('status').textContent)), '', 'Ollama with a catalog model raises no error banner');
    // precision: every image model offers it, in the same row the text models use
    await click('#archChoices .choice', 'Image'); await sleep(200);
    const prec = () => $(() => ({ label: document.querySelector('#quantField .label').textContent, shown: getComputedStyle(document.getElementById('quantField')).display !== 'none', options: [...document.querySelectorAll('#quantChoices .choice')].map((b) => b.textContent) }));
    await pickModel('FLUX.2');
    t.equal(await prec(), { label: 'Weight format / quantization', shown: true, options: ['Native / auto', 'FP8', 'NVFP4'] }, 'FLUX.2 dev: a precision row, in the same place and with the same name as for text models');
    await click('#quantChoices .choice', 'FP8'); await sleep(200);
    t.ok(/--component-quantizations\.transformer fp8/.test((await read()).cmd), 'FP8 is SGLang\'s online quantization of the transformer');
    await click('#quantChoices .choice', 'NVFP4'); await sleep(200);
    const fp4 = await read();
    t.ok(/--transformer-weights-path 'black-forest-labs\/FLUX\.2-dev-NVFP4'/.test(fp4.cmd) && !/fp8/.test(fp4.cmd), 'NVFP4: the weights repo SGLang documents for FLUX.2 dev, replacing the FP8 flag');
    t.ok(fp4.checks.some((c) => /NVFP4 needs a Blackwell GPU/.test(c)), 'and an H100 is told it is not Blackwell', JSON.stringify(fp4.checks));
    await click('#gpuCardChoices .choice', 'B200'); await sleep(200);
    t.ok(!(await read()).checks.some((c) => /Blackwell/.test(c)), 'on a B200 that warning goes away');
    await $(() => { const row = [...document.querySelectorAll('#modelList .family-row')].find((r) => r.querySelector('.family-label strong').textContent.startsWith('FLUX.1')); [...row.querySelectorAll('.model-option')].find((b) => b.textContent.trim().startsWith('dev')).click(); }); await sleep(250);
    await click('#quantChoices .choice', 'NVFP4'); await sleep(200);
    t.ok(/--transformer-path 'lmsys\/flux1-dev-modelopt-nvfp4-sglang-transformer'/.test((await read()).cmd), 'FLUX.1 dev: its documented NVFP4 transformer');
    await $(() => { const row = [...document.querySelectorAll('#modelList .family-row')].find((r) => r.querySelector('.family-label strong').textContent.startsWith('FLUX.1')); [...row.querySelectorAll('.model-option')].find((b) => b.textContent.trim().startsWith('schnell')).click(); }); await sleep(250);
    const sch = await read();
    t.ok(/FLUX\.1-schnell/.test(sch.cmd) && sch.checks.some((c) => /does not list/.test(c)), 'FLUX.1 schnell is in the catalog, and says SGLang\'s documentation does not list it', JSON.stringify(sch.checks));
    t.equal((await prec()).options, ['Native / auto', 'FP8'], 'schnell offers only the precisions that need no special repository');
    await click('#archChoices .choice', 'Language'); await sleep(200);
    // a row of precisions appears only where there is a real choice: not for speech, embedding or reranking models
    await click('#archChoices .choice', 'Retrieval'); await sleep(200);
    t.equal(await $(() => getComputedStyle(document.getElementById('quantField')).display), 'none', 'retrieval models: no precision row of options that mean nothing for them');
    await click('#archChoices .choice', 'Language'); await sleep(200);
    // what the model and the engine each declare: support, shipped code, and the quantization a checkpoint was made in
    const pickPill = async (family, pill) => { await $(([f, p]) => { const row = [...document.querySelectorAll('#modelList .family-row')].find((r) => r.querySelector('.family-label strong').textContent.startsWith(f)); [...row.querySelectorAll('.model-option')].find((b) => b.textContent.trim().startsWith(p)).click(); }, [family, pill]); await sleep(250); };
    await click('#archChoices .choice', 'Language'); await sleep(200);
    await click('#serverList .server', 'vLLM'); await pickPill('Qwen3.8', '27B');
    t.ok(!(await read()).checks.some((c) => /own list of supported|no built-in/.test(c)), 'the default model raises no support warning on vLLM');
    await click('#serverList .server', 'MLX'); await pickPill('DeepSeek V4', 'V4 Pro'); await sleep(200);
    t.ok((await read()).checks.some((c) => /MLX's own list of supported models does not include DeepseekV4ForCausalLM/.test(c)), 'MLX is told it has no module for DeepSeek V4 Pro (no converted build exists either)', JSON.stringify((await read()).checks));
    await pickPill('Qwen3.8', 'Flash-Next'); await sleep(200);
    t.ok(!(await read()).checks.some((c) => /own list of supported/.test(c)), 'but not for a model that has a converted MLX build');
    await click('#serverList .server', 'vLLM'); await pickPill('Qwen3.8', '27B');
    await click('#quantChoices .choice', 'AWQ'); await sleep(250);
    t.ok((await read()).checks.some((c) => /AWQ loads a checkpoint that was published in AWQ/.test(c)), 'AWQ on a plain bf16 repository is called out before launch');
    await click('#quantChoices .choice', 'Native'); await sleep(200);
    t.ok(!(await read()).checks.some((c) => /AWQ loads/.test(c)), 'and goes away with Native');
    await click('#archChoices .choice', 'Retrieval'); await sleep(200);
    for (const label of await $(() => [...document.querySelectorAll('#archDesign .choice[aria-pressed=true]')].map((b) => b.textContent))) await click('#archDesign .choice', label); // show every retrieval model
    await pickPill('jina-reranker', 'v3.5'); await click('#serverList .server', 'vLLM'); await sleep(250);
    t.ok(!/--trust-remote-code/.test((await read()).cmd), 'a reranker whose code vLLM already has built in is not trusted needlessly');
    await pickPill('jina-embeddings-v5', 'omni small'); await click('#serverList .server', 'vLLM'); await sleep(250);
    const jina = await read();
    t.ok(/--trust-remote-code/.test(jina.cmd) && jina.checks.some((c) => /ships its own code/.test(c)), 'an embedding model that ships code vLLM lacks gets --trust-remote-code, and the page says why', jina.cmd + JSON.stringify(jina.checks));
    await click('#archChoices .choice', 'Language'); await sleep(200);
    // a speech model has its own, fixed window: a text context length and a prefix cache do not belong in its command
    await click('#archChoices .choice', 'Audio'); await sleep(200);
    const speech = (await read()).cmd;
    t.ok(/^vllm serve 'openai\/whisper/.test(speech) && !/--max-model-len|--enable-prefix-caching/.test(speech), 'speech to text: no text context length, no prefix cache', speech);
    await click('#archChoices .choice', 'Language'); await sleep(200);
    await click('#serverList .server', 'vLLM'); await sleep(200);
    t.ok(/--max-model-len/.test((await read()).cmd), 'a language model still gets its context length');
    // text to speech: the two models vLLM-Omni documents get its command; the rest say plainly that nothing is documented
    await click('#archChoices .choice', 'Audio'); await sleep(150);
    await click('#archDesign .choice', 'Text to speech'); await sleep(250);
    await pickModel('Qwen3-TTS');
    const qwenTts = (await read()).cmd.replace(/\s+/g, ' ');
    t.equal(qwenTts.split(' ').slice(0, 6), ['vllm', 'serve', "'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'", '\\', '--omni', '\\'], 'Qwen3-TTS: the documented vLLM-Omni command');
    t.ok(/--port 8000/.test(qwenTts) && !/--trust-remote-code/.test(qwenTts), 'with a port, and without model code it does not need');
    await pickModel('OmniVoice');
    t.ok(/--omni/.test((await read()).cmd) && /--trust-remote-code/.test((await read()).cmd), 'OmniVoice: the same, with the model code its documentation asks for');
    const omniFlags = await $(() => { const names = [...document.querySelectorAll('#allFlags .flag-name')].map((x) => x.textContent); return { omni: names.filter((n) => n === '--omni').length, port: names.filter((n) => n === '--port').length, vllm: names.includes('--tensor-parallel-size'), total: names.length }; });
    t.ok(omniFlags.omni === 1 && omniFlags.port === 1 && omniFlags.vllm && omniFlags.total > 380, 'its flag list is Omni\'s and vLLM\'s together, each flag once', JSON.stringify(omniFlags));
    await pickModel('Kokoro');
    t.ok(/^# No server command is documented/.test((await read()).cmd), 'Kokoro: no documented server, so no invented command');
    await click('#archDesign .choice', 'Music'); await sleep(250);
    await pickModel('ACE-Step');
    t.ok(/^# No server command is documented/.test((await read()).cmd), 'music models: the same');
    await click('#archChoices .choice', 'Language'); await sleep(200);
    // embedding and reranker models are not chat models: the engines are told
    await retrieval('Embeddings');
    await click('#serverList .server', 'vLLM'); await sleep(200);
    t.ok(/--runner pooling/.test((await read()).cmd), 'vLLM runs an embedding model as a pooling model');
    await click('#serverList .server', 'SGLang'); await sleep(200);
    t.ok(/--is-embedding/.test((await read()).cmd), 'SGLang is told it is an embedding model');
    await retrieval('Rerankers');
    await click('#serverList .server', 'vLLM'); await sleep(200);
    t.ok(/--runner pooling/.test((await read()).cmd), 'and a reranker too');
    await click('#archChoices .choice', 'Language'); await sleep(200);
    t.ok(!/--runner|--is-embedding/.test((await read()).cmd), 'a chat model gets neither');
    // a Mac: MLX offers Macs and their memory, not NVIDIA cards; coming back restores your card
    await click('#archChoices .choice', 'Language'); await sleep(150);
    await click('#gpuCardChoices .choice', 'RTX 4090'); await sleep(150);
    await click('#serverList .server', 'MLX'); await sleep(250);
    const mac = await $(() => ({
      cards: [...document.querySelectorAll('#gpuCardChoices .choice')].map((b) => b.textContent),
      label: document.getElementById('gpuCardLabel').textContent,
      memory: document.getElementById('gpuVramLabel').textContent,
      count: getComputedStyle(document.getElementById('gpuCountField')).display,
      chip: [...document.querySelectorAll('#summary span')].map((x) => x.textContent)[1],
    }));
    t.equal(mac.cards.slice(0, 3), ['Mac · 16 GB', 'Mac · 24 GB', 'Mac · 32 GB'], 'MLX offers Macs by their memory');
    t.ok(mac.cards.every((c) => /^Mac/.test(c)) && mac.label === 'Mac' && mac.memory === 'Unified memory' && mac.count === 'none', 'no NVIDIA cards, no GPU count, memory called what it is', JSON.stringify(mac));
    t.equal(mac.chip, 'Mac · 64 GB', 'the summary says Mac, not GPU');
    await click('#serverList .server', 'vLLM'); await sleep(250);
    t.equal(await $(() => document.querySelector('#gpuCardChoices .choice[aria-pressed=true]').textContent), 'RTX 4090', 'back on vLLM, your card is back');
    await click('#serverList .server', 'llama.cpp'); await sleep(250);
    t.ok(await $(() => { const c = [...document.querySelectorAll('#gpuCardChoices .choice')].map((b) => b.textContent); return c.includes('RTX 4090') && c.includes('Mac · 64 GB'); }), 'llama.cpp and Ollama run on both, so both are offered');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
