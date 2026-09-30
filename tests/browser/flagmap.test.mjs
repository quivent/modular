import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { startServer, startBrowser, ROOT } from '../lib/harness.mjs';
import { PAGE_SOURCE } from '../lib/configs.mjs';
export const name = 'flag map: "where each choice goes" is generated from the same profile rules as the command';

export default async function (t) {
  const golden = JSON.parse(readFileSync(join(ROOT, 'tests', 'fixtures', 'golden-flag-map.json'), 'utf8'));
  const server = await startServer();
  const browser = await startBrowser();
  if (!browser) return t.skip('no Chrome found (set CHROME=/path/to/chrome)');
  try {
    await browser.open(server.base + '/');
    for (const engine of Object.keys(golden.engines)) {
      const r = await browser.eval(`(() => { ${PAGE_SOURCE}
        const want = ${JSON.stringify(golden.engines[engine])};
        state.tab = 'readable';
        const bad = makeRandomConfigs('${engine}', ${golden.count}, ${golden.seed}).map((c, i) => { const got = flagRows(c); return JSON.stringify(got) === JSON.stringify(want[i]) ? null : { i, want: want[i], got }; }).filter(Boolean);
        return { mismatched: bad.length, first: bad[0] };
      })()`);
      t.equal([r.mismatched, r.first], [0, undefined], `${engine}: ${golden.count} flag maps match the recorded originals exactly`);
    }
    const docker = await browser.eval(`(() => { ${PAGE_SOURCE}
      const want = ${JSON.stringify(golden.dockerVllm)};
      state.tab = 'docker';
      const got = makeRandomConfigs('vllm', want.length, ${golden.seed}).map((c) => flagRows(c));
      state.tab = 'readable';
      return got.filter((g, i) => JSON.stringify(g) !== JSON.stringify(want[i])).length;
    })()`);
    t.equal(docker, 0, 'the Docker tab adds its container row first, as before');
    // the map and the command are one source: every flag in a row is a flag the command contains
    const agree = await browser.eval(`(() => { ${PAGE_SOURCE}
      state.tab = 'readable';
      let disagreements = 0;
      for (const e of ['vllm', 'sglang', 'trtllm']) for (const c of makeRandomConfigs(e, 300, 7)) {
        const cmd = command(c);
        for (const row of flagRows(c)) for (const f of (row.flag.match(/--[a-z][\\w-]*/g) || [])) if (!cmd.includes(f) && row.label !== 'Extra arguments') disagreements++;
      }
      return disagreements; })()`);
    t.equal(agree, 0, 'every flag shown in the map appears in the command (they cannot drift apart)');
    t.equal((await browser.errors()).length, 0, 'no page errors');
  } finally {
    await browser.close();
    await server.close();
  }
}
