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
    // embedding and reranker models are not chat models: the engines are told
    await click('#archChoices .choice', 'Embeddings'); await sleep(200);
    await click('#serverList .server', 'vLLM'); await sleep(200);
    t.ok(/--runner pooling/.test((await read()).cmd), 'vLLM runs an embedding model as a pooling model');
    await click('#serverList .server', 'SGLang'); await sleep(200);
    t.ok(/--is-embedding/.test((await read()).cmd), 'SGLang is told it is an embedding model');
    await click('#archChoices .choice', 'Reranker'); await sleep(200);
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
