#!/usr/bin/env node
// Prints the model catalog as JSON: [{ref, name, kind, retired}]. Read-only; the page stays the one place the list lives.
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root = process.env.MODULAR_ROOT || join(dirname(fileURLToPath(import.meta.url)), '..');
const lines = readFileSync(join(root, 'index.html'), 'utf8').split('\n');
const marker = /(?:\/\*|<!--)\s*▸\s*(.+?)\s*(?:\*\/|-->)\s*$/;
const at = lines.findIndex((l) => (marker.exec(l) || [])[1] === 'js: data — catalog, engines, state');
let end = lines.length;
for (let i = at + 1; i < lines.length; i++) if (marker.test(lines[i])) { end = i; break; }
const ctx = vm.createContext({ document: {}, catalogIndex: () => 0 }); // the region ends by calling a helper defined later
vm.runInContext(lines.slice(at + 1, end).join('\n').replace(/'use strict';/, '') + '\nthis.models = models;', ctx);
console.log(JSON.stringify(ctx.models.map((m) => ({ ref: m.ref, name: m.name, kind: m.kind, retired: !!m.retired }))));
