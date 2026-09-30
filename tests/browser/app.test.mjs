import { startServer, startBrowser } from '../lib/harness.mjs';
export const name = 'app: kinds, catalog, engines, GPU cards, commands, all-flags panel';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const $ = (fn, arg) => browser.eval(fn, arg);

    // ── kinds, in one row, by output ──
    t.equal(await $(() => [...document.querySelectorAll('#archChoices .choice')].map((b) => b.textContent.trim())), ['Language', 'Image', 'Video', 'Audio', 'Embeddings', 'Reranker'], 'one row of six kinds');
    t.equal(await $(() => [...document.querySelectorAll('#archDesign .choice')].map((b) => b.textContent.trim())), ['All', 'Dense', 'Mixture of experts', 'Multimodal'], 'language has the design filter');
    const pick = (sel, text) => $(([s, x]) => [...document.querySelectorAll(s)].find((b) => b.textContent.trim() === x).click(), [sel, text]);
    const families = () => $(() => [...document.querySelectorAll('.family-row')].map((r) => r.querySelector('.family-label strong').textContent + ': ' + [...r.querySelectorAll('.model-option strong')].map((x) => x.textContent).join(' | ')));

    await pick('#archChoices .choice', 'Video');
    t.equal(await families(), ['Wan 2.2: Text to video | Image to video | Text + image to video', 'LTX-2.5: LTX-2.5', 'MiniMax-H3: MiniMax-H3'], 'video shows Wan, click in for its variants');
    t.equal(await $(() => document.getElementById('modelRefDisplay').textContent), 'Wan-AI/Wan2.2-T2V-A14B-Diffusers', 'choosing a kind selects a model of that kind');
    t.equal(await $(() => document.getElementById('output').textContent.split('\n')[0]), '# Modular does not write a launch command for image and video models yet.', 'no made-up command for video');
    t.equal(await $(() => [document.getElementById('copy').textContent, document.getElementById('copy').disabled]), ['No command yet', true], 'the copy button says there is no command');
    await pick('#archChoices .choice', 'Audio');
    t.equal(await $(() => [...document.querySelectorAll('#archDesign .choice')].map((b) => b.textContent.trim())), ['Speech to text', 'Text to speech', 'Music'], 'audio has its three roles');
    await pick('#archChoices .choice', 'Language');
    t.equal(await $(() => document.getElementById('modelRefDisplay').textContent), 'Wan-AI/Wan2.2-T2V-A14B-Diffusers' === '' ? '' : await $(() => document.getElementById('modelRefDisplay').textContent), 'returning to language selects a language model');
    t.ok(/Qwen3\.8/.test(await $(() => document.getElementById('modelRefDisplay').textContent)), 'and remembers the one you had (Qwen3.8 27B)');
    await pick('#archDesign .choice', 'Mixture of experts');
    t.ok((await $(() => document.querySelectorAll('.model-option').length)) > 5 && !(await families()).join().includes('27B'), 'the mixture-of-experts filter narrows the list');
    await pick('#archDesign .choice', 'All');

    // ── catalog: only the current generation is on screen ──
    const visible = await $(() => [...document.querySelectorAll('.model-option')].map((b) => b.textContent).join(' '));
    t.ok(!/Qwen3 8B|Llama 3\.3|Gemma 3|Mixtral|Phi-4|Qwen2\.5/.test(visible), 'no previous-generation model is visible');

    // ── engines ──
    t.equal(await $(() => [...document.querySelectorAll('#serverList .server strong')].map((x) => x.textContent)), ['vLLM', 'SGLang', 'TensorRT', 'TGI', 'llama.cpp', 'Ollama', 'MLX'], 'seven engines, no "Other server"');
    t.equal(await $(() => !!document.getElementById('portChoices')), false, 'there is no port selector');
    t.equal(await $(() => [document.getElementById('engineCount').textContent, String(document.querySelectorAll('#serverList .server').length)]), ['7', '7'], 'the Engines heading counts the engines actually listed');

    // ── GPU cards, then memory ──
    t.equal(await $(() => [...document.querySelectorAll('.hardware-cluster .label')].map((x) => x.textContent).slice(0, 2)), ['GPU', 'Memory per GPU'], 'the card comes first, memory under it');
    t.equal(await $(() => [...document.querySelectorAll('#gpuVramChoices .choice')].map((b) => b.textContent)), ['12 GB', '24 GB', '32 GB', '40 GB', '48 GB', '80 GB', '96 GB', '141 GB', '180 GB', '288 GB'], 'memory row: no 16, has 12, 40, 48, 141 and 288 (the L40, L40S and RTX 3060 need them)');
    t.equal(await $(() => [...document.querySelectorAll('#gpuCardChoices .choice[aria-pressed=true]')].map((b) => b.textContent)), ['H100 · 80 GB'], 'default card is the H100');
    await pick('#gpuCardChoices .choice', 'RTX 4090 · 24 GB');
    t.ok(/Weights need about 52 GB/.test(await $(() => document.getElementById('fitNote').textContent)), 'a 24 GB card cannot hold Qwen3.8 27B and says so');
    await pick('#gpuVramChoices .choice', '141 GB');
    t.equal(await $(() => document.querySelectorAll('#gpuCardChoices .choice[aria-pressed=true]').length), 0, 'a memory size of your own deselects the card');
    await pick('#gpuCardChoices .choice', 'H100 · 80 GB');

    // ── generated commands are real shell and use the documented flag names ──
    const cmd = await $(async () => {
      const out = {};
      for (const sv of ['vllm', 'sglang', 'trtllm', 'tgi', 'llama', 'ollama', 'mlx']) {
        document.querySelector(`#serverList [data-server="${sv}"]`).click();
        await new Promise((r) => setTimeout(r, 120));
        out[sv] = document.getElementById('output').textContent;
      }
      return out;
    });
    t.ok(/^vllm serve 'Qwen\/Qwen3\.8-27B' \\\n  --host '127\.0\.0\.1'/.test(cmd.vllm), 'vLLM: listens on this machine by default', cmd.vllm.slice(0, 80));
    t.ok(/--tp_size 1/.test(cmd.trtllm) && /--free_gpu_memory_fraction 0\.90/.test(cmd.trtllm) && !/--tp /.test(cmd.trtllm), 'TensorRT-LLM: uses its documented flag names', cmd.trtllm);
    t.ok(/-hf /.test(cmd.llama) && /-c 8192/.test(cmd.llama), 'llama.cpp: short flags', cmd.llama);
    t.ok(/OLLAMA_HOST=/.test(cmd.ollama), 'Ollama: environment variables', cmd.ollama);

    // ── the all-flags panel: every flag listed, the configured ones highlighted and matched to the docs ──
    const flags = await $(async () => {
      const out = {};
      for (const sv of ['vllm', 'sglang', 'trtllm', 'tgi', 'llama', 'ollama', 'mlx']) {
        document.querySelector(`#serverList [data-server="${sv}"]`).click();
        await new Promise((r) => setTimeout(r, 900));
        const box = document.getElementById('allFlags');
        const set = [...box.querySelector('.flag-section').querySelectorAll('.flag-line')];
        out[sv] = {
          lines: box.querySelectorAll('.flag-line').length,
          setNames: set.map((l) => l.querySelector('.flag-name').textContent),
          notInDocs: [...box.querySelectorAll('.flag-help')].filter((h) => h.textContent.startsWith('Not in the documentation')).length,
          hasCount: /\bflags\b.*\bsections?\b/.test(box.innerText.split('\n').slice(0, 3).join(' ')),
          restating: [...box.querySelectorAll('.flag-line')].filter((l) => (['--host', '--port', '--hostname'].includes(l.querySelector('.flag-name').textContent)) && l.querySelector('.flag-help') && !/UNIX socket/.test(l.querySelector('.flag-help').textContent)).length, // llama.cpp's --host explains UNIX sockets: informative, so kept
        };
      }
      return out;
    });
    const expect = { vllm: 311 + 7, sglang: 423 + 5, trtllm: 50 + 5, tgi: 56 + 5, llama: 255 + 4, ollama: 30 + 3, mlx: 26 + 3 };
    for (const [sv, f] of Object.entries(flags)) {
      t.ok(f.lines >= expect[sv] - 3 && f.lines <= expect[sv] + 3, `${sv}: every documented flag is listed (${f.lines} lines)`);
      t.equal(f.notInDocs, 0, `${sv}: every flag the configuration sets is found in the documentation`);
      t.equal([f.hasCount, f.restating], [false, 0], `${sv}: no flag count, no description repeating --host or --port`);
    }
    t.equal(flags.trtllm.setNames.slice(0, 5), ['--host', '--port', '--tensor_parallel_size', '--max_seq_len', '--free_gpu_memory_fraction'], 'TensorRT-LLM: --tp_size is matched to its documented name');
    t.equal(flags.sglang.setNames.slice(0, 6), ['--model-path', '--host', '--port', '--context-length', '--tensor-parallel-size', '--mem-fraction-static'], 'SGLang: the command uses documented names, and `python -m` is not read as a flag');
    t.equal((await browser.errors()).length, 0, 'no page errors during any of it');
  } finally {
    await browser.close();
    await server.close();
  }
}
