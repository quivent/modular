import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { ROOT } from '../lib/harness.mjs';
export const name = 'tools: the YAML subset reader, the attention classifier and the recipe summary';

export default async function (t) {
  const r = spawnSync('python3', [join(ROOT, 'tools', 'test_tools.py'), '-v'], { cwd: ROOT, encoding: 'utf8', timeout: 120000 });
  const out = (r.stdout || '') + (r.stderr || '');
  const lines = [...out.matchAll(/^test_(\w+) \(.*?\) \.\.\. (ok|FAIL|ERROR)$/gm)];
  t.ok(lines.length >= 12, `${lines.length} checks ran`, out.slice(-400));
  for (const [, what, result] of lines) t.ok(result === 'ok', what.replace(/_/g, ' '), out.slice(-600));
}
