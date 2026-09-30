# Fix plan

Generated from the tracker by `python3 tools/fix_plan.py`. Do not edit here: change the task in the tracker.
Legend: `[ ]` todo, `[~]` doing, `[x]` done, `[!]` blocked. A task is ready when it is `[ ]` and everything it depends on is `[x]`.

## Requests

- [x] **#23 Page heading: “Serve a model (it’s harder than you think)”**
  Replaces “Build a server command.”
- [x] **#24 Kind of model, by output**
  Language, Image, Video, Audio, Embeddings, Reranker in one top row. “Language” not “Language models”. Design sub-choice: Dense · Mixture of experts · Multimodal. Audio roles. Video → Wan → variants. No “Other / custom”.
- [x] **#25 List EVERY flag in the panel (asked 3 times)**
  Real lines, not comments. 1,101 flags from the six engines’ own docs (vLLM 311, SGLang 423, llama.cpp 255, TGI 56, Ollama 30, MLX 26). Flags your configuration sets are highlighted.
- [x] **#26 No flag count, no filter, no restating descriptions**
  Removed the headline count, section counts, relevance tags and the note. Descriptions that only repeat the flag name are hidden. No advanced-settings filter.
- [x] **#27 Remove the port selector**
  Each engine keeps its own default port.
- [x] **#28 Themes button with five themes incl. macOS and Windows**
  Left of Tracker, same style.
- [x] **#29 Catalog: latest versions only (exceptions Wan 2.2, FLUX.1 dev)**
  “Never include a lower version unless there is a reason.” Rebuilt from Hugging Face data: Qwen3.8, Gemma 4, DeepSeek V4.x, GLM-5.3, Kimi K3, gpt-oss, Nemotron 3.x, Granite 4.2, Mistral, Llama 4, FLUX.2, Wan 2.2, LTX-2.5, and current audio, embedding and reranker models. Applied to the file; still to test and commit.
- [x] **#30 Remove “Other server”, add TensorRT-LLM**
  Engine list: drop the custom-template engine, add TensorRT-LLM (trtllm-serve), with its own full flag list.
- [x] **#31 GPU: pick the card first; memory below it**
  Cards, not memory sizes. Memory choices below the card selector: no 16 GB, no 48 GB, add 40 GB, 141 GB (H200) and the B300 (288 GB). Four research passes.
- [x] **#32 Commit and redeploy to Vercel**
  Commit is done for the checkpoint; catalog work is uncommitted. Redeploy production after the catalog is tested.
- [!] **#33 Working copy: use next.html?**
  You said “not using next”. Earlier I retired next.html and moved to branches. Do you want next.html back as the staging copy that gets promoted to index.html?
- [x] **#34 Update the README and roadmap for all of this**
  Kinds, all-flags panel, catalog, hardware, engines, defaults.

## Foundation

- [x] **#1 Separate the working copy**
  Rollback is git: releases are tagged (`v0.7` is the first), risky work happens on a branch, and `next.html` is retired.
- [x] **#2 Organize the single file**
  Formatted, 30 named regions, tools/map.py prints the map. Splitting deferred.
- [x] **#3 Reconcile the docs with the app**
  `DESIGN.md` still cites 12 models in earlier sections; the app has 15. Keep one current-state summary at the top and move history below it.
- [x] **#4 Version the saved data**
  Setups, storage envelopes and /api/state carry versions; older data upgrades on read, newer data is preserved.
- [x] **#5 Contributing guide**
  CONTRIBUTING.md: run, test, extend (model, flag lists, engine, theme). Every command was run in a fresh clone on Python 3.9 and 3.14; a docs test keeps the links and named paths true.
  Depends on: #9
  Blocks: #22

## Trust

- [~] **#6 Versioned engine profiles**
  First slice done: vLLM, SGLang and TensorRT-LLM are profiles (data) and command() is generated from them, byte-identical to the old hand-written code (250 golden commands each, 3,000 random configurations compared). A test checks every profile flag exists in that engine's documentation. Still to do: TGI, llama.cpp, Ollama, MLX LM as profiles; the flag map and the checks generated from the same data; the version dimension.
  Depends on: #9
  Blocks: #7, #8, #13, #22
- [ ] **#7 Engine version selector**
  Let people pick the version they run, and show how defaults or spellings differ before export.
  Depends on: #6  (waiting on 1)
  Blocks: #22
- [ ] **#8 Source links and last-checked dates**
  Link each version-specific flag to its documentation, and label unknown compatibility as unknown.
  Depends on: #6  (waiting on 1)
  Blocks: #22
- [x] **#9 Automated tests**
  Node test runner with a harness that starts a throwaway server and headless Chrome on free ports. 190 checks: estimate, catalog, flag data, browser flows, server API and WebSocket, saved data, themes. Five injected regressions were each caught.
  Blocks: #5, #6, #19, #21, #22
- [x] **#10 Better fit estimates**
  Extend the weight-only note to KV cache and activation headroom for the chosen context and batch, clearly labeled as an estimate.
  Blocks: #22
- [ ] **#11 Input validation**
  Validate pasted references, hosts, ports, paths, and extra arguments, and quote them safely in every output format.
  Blocks: #22

## Reach

- [ ] **#12 More command forms**
  Add environment-variable output and Kubernetes or Compose snippets, generated from the same configuration state.
  Blocks: #22
- [ ] **#13 Complete the remaining engines**
  Bring TGI, llama.cpp, and MLX LM to the same depth as vLLM and SGLang.
  Depends on: #6  (waiting on 1)
  Blocks: #22
- [ ] **#14 Share and import**
  Export a configuration as a link or file and import it, so a setup can move between people and machines.
  Blocks: #22
- [ ] **#15 Catalog upkeep**
  Refresh the curated models, and add a lightweight way to update the catalog without editing the page.
  Blocks: #22
- [ ] **#16 Private repositories**
  Offer a clear, token-free path for private Hugging Face repositories beyond pasting an exact reference.
  Blocks: #22

## Polish

- [ ] **#17 Accessibility pass**
  Keyboard-only walkthrough, screen-reader audit of the checks and flag map, contrast and reduced-motion checks.
  Blocks: #22
- [ ] **#18 Phone and tablet audit**
  Review every breakpoint on real devices, including the live output panel and saved configurations.
  Blocks: #22
- [ ] **#19 Browser support matrix**
  Test current Chrome, Safari, and Firefox, including clipboard fallbacks and local storage being unavailable.
  Depends on: #9
  Blocks: #22
- [ ] **#20 Self-hosted fonts and offline mode**
  Remove the Google Fonts request so the page works fully offline.
  Blocks: #22
- [ ] **#21 Continuous checks**
  Run the tests and a link and asset check on every change.
  Depends on: #9
  Blocks: #22
- [ ] **#22 Release**
  Refresh screenshots with `assets/readme/render.py`, tag a version, deploy, and remove the "prototype" label from this README.
  Depends on: #5 to #21 (all)  (waiting on 14)

## Ready now (highest priority first)

1. #11 Input validation
1. #12 More command forms
1. #14 Share and import
1. #15 Catalog upkeep
1. #16 Private repositories
1. #17 Accessibility pass
1. #18 Phone and tablet audit
1. #19 Browser support matrix
1. #20 Self-hosted fonts and offline mode
1. #21 Continuous checks
