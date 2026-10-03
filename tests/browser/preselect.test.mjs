import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'preselect: hardware follows the model until you choose it; options that cannot work are not offered';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const $ = (fn, arg) => browser.eval(fn, arg);
    const pick = (label) => $((n) => { const e = [...document.querySelectorAll('#modelList .model-option')].find((x) => x.closest('.family-row').querySelector('.family-label strong').textContent + ' ' + x.querySelector('strong').textContent === n); if (e) e.click(); return !!e; }, label);
    const pressed = (id) => $((x) => document.querySelector('#' + x + ' [aria-pressed=true]')?.textContent, id);
    const hw = async () => [await pressed('gpuCountChoices'), await pressed('gpuCardChoices'), await $(() => document.getElementById('fitNote').classList.contains('warn'))];

    // ── hardware follows the model ──
    t.equal(await hw(), ['1', 'H100', false], 'the default model opens on 1 × H100');
    await pick('Llama 4 Scout');
    t.equal(await hw(), ['4', 'H100', false], 'a model too big for one H100 gets the fewest H100s it fits on');
    t.ok(/^Set to 4 × H100 to fit this model\./.test(await $(() => document.getElementById('fitNote').textContent)), 'and the fit note says why the hardware changed');
    t.ok(/--tensor-parallel-size 4/.test(await $(() => document.getElementById('output').textContent)), 'tensor parallelism follows');
    await pick('Kimi K3');
    t.equal(await hw(), ['8', 'B300', false], 'a model that 8 H100s cannot hold gets the smallest card that holds it');
    await pick('Qwen3.8 2.4T-A95B');
    t.equal(await hw(), ['1', 'H100', true], 'a model that fits nowhere stays on 1 × H100, and the warning explains');
    await pick('Qwen3.8 27B');
    t.equal(await hw(), ['1', 'H100', false], 'and a small model brings it back to 1 × H100');

    // ── precision follows the checkpoint ──
    const quants = () => $(() => [...document.querySelectorAll('#quantChoices .choice')].map((x) => x.textContent));
    const engine = (label) => $((x) => [...document.querySelectorAll('#serverList .server')].find((s) => s.querySelector('strong').textContent === x).click(), label);
    t.equal(await quants(), ['Native / auto', 'FP8', 'bitsandbytes', 'Custom…'], 'a bf16 checkpoint is not offered AWQ or GPTQ, which load only checkpoints published in them');
    await engine('TensorRT');
    t.equal(await quants(), ['Native / auto', 'FP8', 'Custom…'], 'nor NVFP4 on TensorRT, which needs a ModelOpt checkpoint');
    await engine('vLLM');
    await $(() => { document.getElementById('customModel').open = true; const i = document.getElementById('modelLink'); i.value = 'https://huggingface.co/someone/their-model'; i.dispatchEvent(new Event('input')); });
    t.equal(await quants(), ['Native / auto', 'FP8', 'AWQ', 'GPTQ', 'bitsandbytes', 'Custom…'], 'a pasted model, whose format is not known, keeps every option');
    await $(() => [...document.querySelectorAll('#quantChoices .choice')].find((x) => x.textContent === 'AWQ').click());
    await pick('Qwen3.8 27B');
    t.equal(await pressed('quantChoices'), 'Native / auto', 'moving to a checkpoint that is not AWQ drops the AWQ choice');
    await browser.open(server.base + '/?hardware'); // a fresh page: hardware nobody has chosen yet

    // ── what you choose is never moved ──
    await $(() => [...document.querySelectorAll('#gpuCardChoices .choice')].find((x) => x.textContent === 'L40S').click());
    await pick('Llama 4 Scout');
    t.equal(await hw(), ['1', 'L40S', true], 'once you choose hardware, a model never moves it');
    t.equal(await $(() => /^Set to/.test(document.getElementById('fitNote').textContent)), false, 'and the note no longer claims it was set for you');

    await browser.open(server.base + '/?restored');
    await pick('Llama 4 Scout');
    await $(() => document.getElementById('saveConfig').click());
    await sleep(100);
    await pick('Qwen3.8 27B');
    await $(() => document.querySelector('[data-load-config]').click());
    await sleep(200);
    await pick('GLM-5.3 Flash');
    t.equal((await hw()).slice(0, 2), ['4', 'H100'], 'hardware from a restored setup counts as chosen');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
