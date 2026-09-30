import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { startServer, startBrowser, ROOT } from '../lib/harness.mjs';
import { PAGE_SOURCE } from '../lib/configs.mjs';
export const name = 'engine profiles: the commands they generate are exactly what the hand-written generators produced';

export default async function (t) {
  const golden = JSON.parse(readFileSync(join(ROOT, 'tests', 'fixtures', 'golden-commands.json'), 'utf8'));
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    for (const engine of Object.keys(golden.engines)) {
      const r = await browser.eval(`(() => { ${PAGE_SOURCE}
        const want = ${JSON.stringify(golden.engines[engine])};
        const got = makeRandomConfigs('${engine}', ${golden.count}, ${golden.seed}).map((c) => command(c));
        const bad = got.map((g, i) => (g === want[i] ? null : { i, want: want[i], got: g })).filter(Boolean);
        return { bad: bad.slice(0, 2), total: got.length, mismatched: bad.length };
      })()`);
      t.equal([r.mismatched, r.bad], [0, []], `${engine}: ${r.total} generated commands match the recorded originals exactly`);
    }
    // the comparison has teeth: a profile with two rules swapped must disagree with the record
    const noticed = await browser.eval(`(() => { ${PAGE_SOURCE}
      const want = ${JSON.stringify(golden.engines.vllm)};
      const broken = JSON.parse(JSON.stringify(ENGINE_PROFILES.vllm));
      [broken.rules[1], broken.rules[2]] = [broken.rules[2], broken.rules[1]];
      return makeRandomConfigs('vllm', 20, ${golden.seed}).some((c, i) => profileCommand(broken, c) !== want[i]);
    })()`);
    t.ok(noticed, 'a profile with two rules swapped is noticed');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
