import vm from 'node:vm';
import { region } from '../lib/harness.mjs';
export const name = 'catalog: invariants of the model list';

export default async function (t) {
  const ctx = vm.createContext({ document: {}, catalogIndex: () => 0 }); // the data region ends by calling a helper defined in a later region
  vm.runInContext(region('js: data — catalog, engines, state').replace(/'use strict';/, '') + '\nthis.models = models; this.servers = servers; this.portDefaults = portDefaults;', ctx);
  const { models, servers, portDefaults } = ctx;
  const live = models.filter((m) => !m.retired);
  const KINDS = ['language', 'image', 'video', 'audio', 'embedding', 'reranker'];

  t.equal(new Set(models.map((m) => m.ref)).size, models.length, 'every reference is unique');
  t.equal(models.filter((m) => !m.name || !m.ref || !m.kind || !(m.group || m.family) || !m.arch).map((m) => m.ref), [], 'every model has a name, reference, kind, group and architecture');
  t.equal(live.filter((m) => KINDS.indexOf(m.kind) === -1).map((m) => m.ref), [], 'every kind is one of the six');
  t.equal(live.filter((m) => m.kind === 'audio' && ['speech-to-text', 'text-to-speech', 'music'].indexOf(m.role) === -1).map((m) => m.ref), [], 'every audio model has a role');
  for (const kind of KINDS) t.ok(live.some((m) => m.kind === kind), `there are current models of kind ${kind}`);
  for (const role of ['speech-to-text', 'text-to-speech', 'music']) t.ok(live.some((m) => m.role === role), `the audio role ${role} has models (so it is never an empty tab)`);
  t.equal(live.filter((m) => m.kind === 'language' && m.moe === true && m.arch !== 'moe').map((m) => m.ref), [], 'a mixture-of-experts model has architecture moe');
  t.ok(live.filter((m) => m.kind === 'language').length >= 20, 'the language catalog is populated');
  t.equal(live.filter((m) => /Qwen2\.5|Llama-3\.|gemma-3|Mixtral|phi-4|bge-m3|whisper-large-v3$|stable-diffusion-xl/i.test(m.ref)).map((m) => m.ref), [], 'no previous-generation model is visible (the standing exceptions are FLUX.1 dev and Wan 2.2)');
  t.ok(live.some((m) => m.ref === 'black-forest-labs/FLUX.1-dev') && live.some((m) => /Wan2\.2/.test(m.ref)), 'the two standing exceptions are present');
  t.ok(models.some((m) => m.retired), 'previous-generation models are retired, not deleted, so saved data keeps its meaning');

  const def = models.find((m) => m.ref === 'Qwen/Qwen3.8-27B');
  t.ok(def && !def.retired && def.kind === 'language', 'the default model exists and is current');
  t.equal(servers.map((s) => s.id), ['vllm', 'sglang', 'trtllm', 'tgi', 'llama', 'ollama', 'mlx'], 'the engines, in order, with no custom-template engine');
  t.equal(servers.filter((s) => !portDefaults[s.id]).map((s) => s.id), [], 'every engine has a default port');
}
