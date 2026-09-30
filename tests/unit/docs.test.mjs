import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { ROOT } from '../lib/harness.mjs';
export const name = 'docs: links resolve and the commands the guide names still exist';

export default async function (t) {
  const docs = ['README.md', 'CONTRIBUTING.md', 'ROADMAP.md', 'design-laws.md', 'PROMPT.md', 'assets/readme/README.md'];
  for (const doc of docs) {
    const src = readFileSync(join(ROOT, doc), 'utf8');
    const links = [...src.matchAll(/\]\(([^)#\s]+)(?:#[^)]*)?\)|(?:src|srcset)="([^"#]+)"/g)].map((m) => m[1] || m[2]).filter((l) => l && !/^(https?:|mailto:|#)/.test(l));
    const missing = links.filter((l) => !existsSync(join(ROOT, dirname(doc), l)));
    t.equal(missing, [], `${doc}: every relative link and image points at a file that exists (${links.length} checked)`);
  }

  // the guide names scripts, files and commands: each must exist
  const guide = readFileSync(join(ROOT, 'CONTRIBUTING.md'), 'utf8');
  const paths = [...new Set([...guide.matchAll(/\b((?:tools|tests|db|catalog)\/[\w./-]+\.(?:py|mjs|json|sql)|server\.py|design-laws\.md)\b/g)].map((m) => m[1]))];
  t.ok(paths.length >= 6, 'the guide names several repository paths', String(paths.length));
  t.equal(paths.filter((p) => !existsSync(join(ROOT, p))), [], `every path the guide names exists (${paths.length} checked)`);
  const regions = [...guide.matchAll(/python3 tools\/map\.py "([^"]+)"/g)].map((m) => m[1]);
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  t.equal(regions.filter((r) => !html.includes('▸ ' + r) && !html.includes('▸ js: ' + r)), [], 'every region the guide asks you to print exists');
  for (const region of ['js: data', 'css: themes', 'js: themes']) t.ok(html.includes('▸ ' + region), `the region the guide sends you to exists: ${region}`);

  // the README should not describe things that are gone
  const readme = readFileSync(join(ROOT, 'README.md'), 'utf8');
  t.equal(['Other server', 'More you can set', 'Qwen2.5', 'Llama 3.3 70B', '6 + custom'].filter((x) => readme.includes(x) && !/Wan 2\.2 and FLUX/.test(x)), [], 'the README no longer mentions removed features or the previous generation');
  const roadmap = readFileSync(join(ROOT, 'ROADMAP.md'), 'utf8');
  t.ok(/- \[x\] \*\*9\. Automated tests/.test(roadmap) || !/- \[ \] \*\*9\./.test(roadmap), 'the roadmap does not list automated tests as undone');
}
