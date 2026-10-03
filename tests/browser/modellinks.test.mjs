import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'model links: a pasted link or tag is read as what it is, and an Ollama tag is refused by engines that cannot load it';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const $ = (fn, arg) => browser.eval(fn, arg);
    const paste = async (link) => {
      await $((x) => { document.getElementById('customModel').open = true; const i = document.getElementById('modelLink'); i.value = x; i.dispatchEvent(new Event('input')); }, link);
      await sleep(150);
      return $(() => [document.getElementById('source').value, document.getElementById('modelRef').value]);
    };
    const engine = async (label) => {
      await $((x) => [...document.querySelectorAll('#serverList .server')].find((s) => s.querySelector('strong').textContent === x).click(), label);
      await sleep(150);
      return $(() => (document.getElementById('status').hidden ? '' : document.getElementById('status').textContent));
    };

    t.equal(await paste('https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct'), ['huggingface', 'meta-llama/Llama-3.1-8B-Instruct'], 'a Hugging Face link becomes its model ID');
    t.equal(await engine('vLLM'), '', 'and vLLM takes it without a warning');
    t.equal(await paste('/models/my-model'), ['path', '/models/my-model'], 'a path is a path');
    t.equal(await paste('https://example.com/model.gguf'), ['url', 'https://example.com/model.gguf'], 'any other link is a URL');
    t.ok(/Fetch or mount the URL first/.test(await engine('vLLM')), 'and is flagged as needing a download first');

    t.equal(await paste('qwen3:8b'), ['ollama', 'qwen3:8b'], 'a bare Ollama tag is a tag, not a URL with "qwen3:" as its scheme');
    t.equal(await paste('https://ollama.com/library/qwen3:8b'), ['ollama', 'qwen3:8b'], 'an ollama.com link becomes its tag');
    const refused = {};
    for (const label of ['vLLM', 'SGLang', 'TensorRT', 'TGI']) refused[label] = /runs only in Ollama/.test(await engine(label));
    t.equal(refused, { vLLM: true, SGLang: true, TensorRT: true, TGI: true }, 'engines that cannot load an Ollama tag say so instead of printing a command that fails');
    t.equal(await engine('Ollama'), '', 'Ollama takes the tag without a warning');
    t.ok(/ollama pull 'qwen3:8b'/.test(await $(() => document.getElementById('output').textContent)), 'and pulls it');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
