import { spawnSync } from 'node:child_process';
import { startServer, startBrowser, sleep } from '../lib/harness.mjs';
export const name = 'stack: the second page stacks commands into one server and leaves the first page as it was';

export default async function (t) {
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    const $ = (fn, arg) => browser.eval(fn, arg);
    const pick = (sel, text) => $(([s, x]) => [...document.querySelectorAll(s)].find((b) => b.textContent.trim() === x || b.textContent.includes(x)).click(), [sel, text]);
    const go = async (hash) => { await $((h) => { location.hash = h; }, hash); await sleep(120); };
    const script = () => $(() => document.getElementById('stackOutput').textContent);
    const cards = () => $(() => [...document.querySelectorAll('#stackList .stack-item')].map((li) => [li.querySelector('strong').textContent, ...[...li.querySelectorAll('small')].map((s) => s.textContent)].join(' | ')));
    const checks = () => $(() => [...document.querySelectorAll('#stackChecks li')].map((l) => l.className + ': ' + l.textContent));
    // everything a person could see change on the first page
    const firstPage = () => $(() => JSON.stringify([state, [...document.querySelectorAll('#top input')].map((e) => e.id + '=' + e.value), [...document.querySelectorAll('#top [role=switch]')].map((e) => e.id + '=' + e.getAttribute('aria-checked')), document.getElementById('output').textContent, document.getElementById('fitNote').textContent, document.getElementById('checks').textContent, document.getElementById('archDesign').innerHTML]));

    // ── the way in: one small icon, top right ──
    const link = await $(() => { const a = document.getElementById('stackLink'), r = a.getBoundingClientRect(); return { last: a === a.parentElement.lastElementChild, parent: a.parentElement.className, text: a.textContent.trim(), icons: a.querySelectorAll('svg').length, name: a.getAttribute('aria-label'), w: r.width, h: r.height }; });
    t.equal([link.last, link.parent, link.text, link.icons, link.name], [true, 'top-right', '', 1, 'Deploy a full server'], 'the link is the last thing in the top-right corner: one icon, no words, named for screen readers');
    t.ok(link.w <= 40 && link.h <= 40 && link.w >= 16, 'and it is small', `${link.w}x${link.h}`);
    t.equal(await $(() => [document.getElementById('top').hidden, document.getElementById('stackPage').hidden, document.title]), [false, true, 'Modular — Build a model deployment'], 'the first page is what opens');

    // ── three saved configurations to stack: the default, an embedding model, and one on TensorRT ──
    await $(() => document.getElementById('saveConfig').click());
    await pick('#archChoices .choice', 'Retrieval');
    await sleep(120);
    await $(() => document.getElementById('saveConfig').click());
    await pick('#archChoices .choice', 'Language');
    await sleep(120);
    await pick('#gpuCountChoices .choice', '2');
    const command = await $(() => document.getElementById('output').textContent);
    const before = await firstPage();

    await $(() => document.getElementById('stackLink').click());
    await sleep(150);
    t.equal(await $(() => [location.hash, document.getElementById('top').hidden, document.getElementById('stackPage').hidden, document.title, scrollY]), ['#stack', true, false, 'Modular — Deploy a full server', 0], 'the icon opens the second page, at its top');
    t.equal(await $(() => document.querySelector('#stackPage h1').textContent), 'Deploy a full server (one command at a time)', 'which says what it is for');
    t.equal(await $(() => [document.getElementById('stackEmpty').hidden, document.getElementById('stackCopy').disabled, document.getElementById('stackOutput').textContent.split('\n')[0]]), [false, true, '# Nothing to deploy yet.'], 'an empty stack shows no script and says so');
    t.equal(await $(() => [document.querySelector('#stackCurrent .choice').textContent, [...document.querySelectorAll('#stackSaved .choice')].map((b) => b.textContent)]), ['Qwen3.8 27B · vLLM', ['Configuration 1', 'Configuration 2']], 'it offers the configuration on the first page and every saved one');

    // ── stacking ──
    await $(() => document.querySelector('#stackCurrent .choice').click());
    t.equal(await cards(), ['Qwen3.8 27B | vLLM · port 8000 · GPUs 0–1'], 'the current configuration becomes the first service, with its port and its GPUs');
    const docker = await $(() => dockerCommand(spec()).split('\n').slice(1).join('\n'));
    const one = await script();
    t.ok(docker.length > 40 && one.includes(docker), 'its flags are exactly the ones the Docker output on the first page shows');
    t.ok(one.includes('docker run -d --restart unless-stopped --name modular-qwen3-8-27b ') && one.includes(' -e CUDA_VISIBLE_DEVICES=0,1 ') && one.includes(' -p 127.0.0.1:8000:8000 ') && !one.includes('--rm --runtime nvidia'), 'kept running, named, on its own port and GPUs, and published on this machine only', one.split('\n').find((l) => /^docker run -d/.test(l)));
    await $(() => document.querySelectorAll('#stackSaved .choice')[1].click());
    await $(() => document.querySelectorAll('#stackSaved .choice')[0].click());
    t.equal(await cards(), ['Qwen3.8 27B | vLLM · port 8000 · GPUs 0–1', 'Qwen3-VL-Embedding 8B | vLLM · port 8001 · GPU 2', 'Qwen3.8 27B | vLLM · port 8002 · GPU 3'], 'saved configurations stack below it: each gets the next free port and the next GPUs');
    t.equal(await firstPage(), before, 'reading saved configurations changed nothing on the first page');
    const three = await script();
    t.equal(three.split('\n').filter((l) => /^docker run -d/.test(l)).map((l) => [/--name (\S+)/.exec(l)[1], /CUDA_VISIBLE_DEVICES=(\S+)/.exec(l)[1], /-p (\S+)/.exec(l)[1]]), [['modular-qwen3-8-27b', '0,1', '127.0.0.1:8000:8000'], ['modular-qwen3-vl-embedding-8b', '2', '127.0.0.1:8001:8000'], ['modular-qwen3-8-27b-2', '3', '127.0.0.1:8002:8000']], 'no two containers share a name, a port or a GPU');
    t.ok((await checks()).includes('ok: Qwen3-VL-Embedding 8B listens on port 8001: 8000 is taken by Qwen3.8 27B (01).') && (await checks()).includes('ok: Qwen3.8 27B (03) listens on port 8002: 8000 is taken by Qwen3.8 27B (01).') && (await checks()).includes('ok: The stack uses 4 GPUs, numbered 0 to 3. Each service is pinned to its own.'), 'Checks says which port moved (telling two services of one model apart by their place) and how many GPUs the machine needs', JSON.stringify(await checks()));
    t.ok(three.includes('-ge 4 ] || { echo "This stack needs 4 GPUs."') && three.includes('docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi'), 'the script checks the machine for those GPUs before starting anything');
    t.equal(three.split('\n').filter((l) => /^wait_for modular-/.test(l)), ['wait_for modular-qwen3-8-27b http://127.0.0.1:8000/health', 'wait_for modular-qwen3-vl-embedding-8b http://127.0.0.1:8001/health', 'wait_for modular-qwen3-8-27b-2 http://127.0.0.1:8002/health'], 'and waits for each service on its own port');

    // ── order is the stack: moving a service moves its GPUs ──
    await $(() => document.querySelector('#stackList [data-stack-act=down]').click());
    t.equal((await cards()).slice(0, 2), ['Qwen3-VL-Embedding 8B | vLLM · port 8000 · GPU 0', 'Qwen3.8 27B | vLLM · port 8001 · GPUs 1–2'], 'moving a service down gives the one above it the first port and GPU');
    await $(() => document.querySelectorAll('#stackList [data-stack-act=up]')[1].click());
    await $(() => document.querySelectorAll('#stackList [data-stack-act=remove]')[2].click());
    t.equal((await cards()).length, 2, 'a service can be taken off the stack');

    // ── the switches are blocks of the script ──
    await $(() => document.getElementById('stackCheck').click());
    await $(() => document.getElementById('stackWait').click());
    const bare = await script();
    t.ok(!bare.includes('nvidia-smi') && !bare.includes('wait_for'), 'switching off the machine check and the wait takes their blocks out');
    await $(() => document.getElementById('stackCheck').click());
    await $(() => document.getElementById('stackWait').click());

    // ── the gateway ──
    t.ok((await checks()).some((c) => /^ok: Every service listens on this machine only/.test(c)) && !(await script()).includes('caddy'), 'with no gateway the services stay on this machine, and Checks says so');
    await $(() => document.getElementById('stackGateway').click());
    t.ok(!(await script()).includes('caddy') && (await checks()).some((c) => /^warn: The gateway needs the domain name/.test(c)), 'a gateway with no domain is left out of the script, with the reason');
    await $(() => { const d = document.getElementById('stackDomain'); d.value = 'not a domain'; d.oninput(); });
    t.ok(!(await script()).includes('caddy'), 'and so is one whose domain is not a host name');
    await $(() => { const d = document.getElementById('stackDomain'); d.value = 'https://Models.Example.com/'; d.oninput(); });
    const full = await script();
    t.equal(full.split('\n').slice(0, 4)[3], ': "${MODULAR_API_KEY:?Set MODULAR_API_KEY to the key clients must send}"', 'with a domain, the script refuses to start without the API key, before anything runs');
    t.ok(full.includes('models.example.com {\n\troute {\n\t\t@denied not header Authorization "Bearer {$MODULAR_API_KEY}"\n\t\trespond @denied 401\n\t\thandle_path /qwen3-8-27b/* {\n\t\t\treverse_proxy 127.0.0.1:8000\n\t\t}\n\t\thandle_path /qwen3-vl-embedding-8b/* {\n\t\t\treverse_proxy 127.0.0.1:8001\n\t\t}\n\t\trespond 404\n\t}\n}'), 'the gateway refuses requests without the key first, then gives every service its own path', full.slice(full.indexOf('cat >')));
    t.ok((await cards())[0].endsWith('| https://models.example.com/qwen3-8-27b/'), 'each service shows the address it will have', (await cards())[0]);
    const syntax = spawnSync('bash', ['-n'], { input: full, encoding: 'utf8' });
    t.equal([syntax.status, syntax.stderr], [0, ''], 'the whole script is valid bash');

    // ── the way back ──
    await pick('#stackModes .choice', 'Tear down');
    t.equal((await script()).split('\n').pop(), 'docker rm -f modular-gateway modular-qwen3-8-27b modular-qwen3-vl-embedding-8b', 'Tear down removes exactly what Deploy started');
    await pick('#stackModes .choice', 'Deploy');

    // ── a configuration with no container command is refused by name, not guessed at ──
    await go('#top');
    await pick('#serverList .server', 'TensorRT');
    await go('#stack');
    t.equal(await $(() => [document.querySelector('#stackCurrent .choice').textContent, document.querySelector('#stackCurrent .choice').disabled, document.getElementById('stackCurrentNote').textContent]), ['Qwen3.8 27B · TensorRT', true, 'No container command is documented for TensorRT.'], 'an engine with no documented container command cannot be stacked, and the page says why');
    // one that is already in a stack (saved before, or by another copy of Modular) is shown and left out
    await $(() => { const c = spec(); stack.services.push({ label: 'Qwen3.8 27B', fit: '', spec: c }); storeStack(); renderStack(); });
    t.equal((await cards())[2], 'Qwen3.8 27B | Left out of the script. No container command is documented for TensorRT.', 'one already in the stack is shown with the reason');
    t.ok(!(await script()).includes('trtllm') && (await script()).includes('# Deploys 2 services') && (await checks())[0] === 'warn: Qwen3.8 27B (03) is left out of the script. No container command is documented for TensorRT.', 'and it is not in the script', (await checks())[0]);
    await go('#top');
    await pick('#serverList .server', 'vLLM');
    await pick('#archChoices .choice', 'Audio');
    await pick('#archDesign .choice', 'Music');
    await sleep(150);
    await $(() => document.querySelector('#modelList .model-option').click());
    await sleep(150);
    await go('#stack');
    t.equal(await $(() => [document.querySelector('#stackCurrent .choice').disabled, document.getElementById('stackCurrentNote').textContent]), [true, 'No launch command yet for this kind of model.'], 'a model with no launch command cannot be added, and the page says why');

    // ── the stack is remembered, and both ways back to the first page work ──
    await browser.open(server.base + '/?reload#stack'); // a different address, so the document really loads again
    t.equal([(await cards()).length, await $(() => JSON.parse(localStorage.getItem('modular.stack')).v), await $(() => document.getElementById('stackDomain').value)], [3, 1, 'https://Models.Example.com/'], 'the stack survives a reload, in a versioned shape');
    t.equal(await $(() => [document.getElementById('stackPage').hidden, scrollY]), [false, 0], 'a link to the second page opens it, at its top');
    await $(() => document.getElementById('stackLink').click());
    await sleep(120);
    t.equal(await $(() => [location.hash, document.getElementById('top').hidden, document.title]), ['#top', false, 'Modular — Build a model deployment'], 'on the second page the same icon leads back');
    await go('#stack');
    await $(() => document.querySelector('.brand').click());
    await sleep(120);
    t.equal(await $(() => document.getElementById('top').hidden), false, 'and so does the Modular name');
    t.equal(await $(() => document.getElementById('output').textContent.length > 20), true, 'the first page still shows its command');

    // ── a stack saved by a newer Modular is shown as empty and never overwritten ──
    const newer = JSON.stringify({ v: 99, layers: ['something this version does not know'] });
    await browser.open(server.base + '/?newer#stack', { init: `localStorage.setItem('modular.stack', ${JSON.stringify(newer)});` });
    await $(() => document.querySelector('#stackCurrent .choice').click());
    t.equal(await $(() => localStorage.getItem('modular.stack')), newer, 'a stack written by a newer version is left exactly as it was');
    t.equal((await browser.errors()).length, 0, 'no page errors', JSON.stringify(await browser.errors()));
    t.ok(command.length > 20, 'the first page had a command throughout');
  } finally {
    await browser.close();
    await server.close();
  }
}
