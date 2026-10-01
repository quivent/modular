import { spawnSync } from 'node:child_process';
import { ROOT } from '../lib/harness.mjs';
export const name = 'librarian: files safe changes, holds risky ones, undoes what breaks, never touches your unsaved work';

export default async function (t) {
  const r = spawnSync('python3', ['-m', 'unittest', 'librarian.test_librarian', '-v'], { cwd: ROOT, encoding: 'utf8', timeout: 240000 });
  const out = (r.stdout || '') + (r.stderr || '');
  const lines = [...out.matchAll(/^test_(\w+) \(.*?\) \.\.\. (ok|FAIL|ERROR)$/gm)];
  t.ok(lines.length >= 14, `the librarian's ${lines.length} checks ran`, out.slice(-400));
  for (const [, what, result] of lines) t.ok(result === 'ok', what.replace(/_/g, ' '), out.slice(-600));
  t.ok(r.status === 0, 'and the run ended cleanly', out.slice(-300));
}
