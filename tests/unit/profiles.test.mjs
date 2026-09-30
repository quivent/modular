import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';
import { ROOT, region } from '../lib/harness.mjs';
export const name = 'engine profiles: every flag a profile emits exists in that engine\'s documentation';

export default async function (t) {
  const ctx = vm.createContext({ sh: (x) => x });
  vm.runInContext(region('js: engine profiles') + '\nthis.ENGINE_PROFILES = ENGINE_PROFILES;', ctx);
  const profiles = ctx.ENGINE_PROFILES;
  t.ok(Object.keys(profiles).length >= 1, 'there is at least one engine profile');
  for (const [engine, profile] of Object.entries(profiles)) {
    const docs = JSON.parse(readFileSync(join(ROOT, 'catalog', 'flags', engine + '.json'), 'utf8'));
    const known = new Set(docs.sections.flatMap((s) => s.flags.flatMap((f) => [f.name, ...(f.aliases || []), ...(f.negation ? [f.negation] : [])])));
    const missing = profile.rules.map((r) => r.flag).filter((f) => !known.has(f));
    t.equal(missing, [], `${engine}: every flag in the profile is in the documentation (${profile.rules.length} rules, read ${docs.fetched})`);
    t.equal(profile.rules.filter((r) => !r.flag || (r.value && r.literal !== undefined)).length, 0, `${engine}: every rule has a flag, and takes a value or a literal, not both`);
    t.ok(/^\d{4}-\d\d-\d\d$/.test(profile.documented) && profile.head.includes('{model}'), `${engine}: the profile says when it was checked and where the model goes`);
  }
}
