# Roadmap to a finished Modular

Modular today is a complete, working prototype. This checklist is the path from "generates a good starting command" to "a configuration you can trust." It is mirrored at the end of the [README](README.md).

### Foundation

- [x] **1. Separate the working copy.** Rollback is git: releases are tagged (`v0.7` is the first), risky work happens on a branch, and `next.html` is retired.
- [x] **2. Organize the single file.** `index.html` stays one self-contained file, formatted with one statement per line and split into 30 named regions marked `▸ name`. `python3 tools/map.py` prints the map of regions; `python3 tools/map.py checks` prints one region. Splitting into modules is deferred until tests or parallel work need it.
- [x] **3. Reconcile the docs with the app.** Resolved by deleting `DESIGN.md`, which had drifted from the app. It remains in git history.
- [x] **4. Version the saved data.** Saved setups, local-storage envelopes, and the server's `/api/state` now carry version numbers. Older data is upgraded when read (v0 setups gain a catalog reference and stop carrying favorites), and data written by a newer Modular is preserved and never overwritten.
- [ ] **5. Contributing guide.** The MIT license is in place (`LICENSE`). Still to write: short instructions for running, testing, and adding a model or engine.

### Trust

- [ ] **6. Versioned engine profiles.** Describe each engine's flags, defaults, accepted values, and conflicts as data per version, then generate the renderer and checks from it.
- [ ] **7. Engine version selector.** Let people pick the version they run, and show how defaults or spellings differ before export.
- [ ] **8. Source links and last-checked dates.** Link each version-specific flag to its documentation, and label unknown compatibility as unknown.
- [ ] **9. Automated tests.** Golden-file tests for every engine and output format, plus a test for each check (oversubscription, omitted settings, duplicate arguments).
- [x] **10. Better fit estimates.** Every catalog model with a published architecture now gets a real "will it start?" check: weights at the chosen precision, KV cache for a full-length request, attention heads divisible by the GPU count, CPU offload, and fixed KV memory, each with a concrete fix. Custom models and Ornith builds keep the weight-only note.
- [ ] **11. Input validation.** Validate pasted references, hosts, ports, paths, and extra arguments, and quote them safely in every output format.

### Reach

- [ ] **12. More command forms.** Add environment-variable output and Kubernetes or Compose snippets, generated from the same configuration state.
- [ ] **13. Complete the remaining engines.** Bring TGI, llama.cpp, and MLX LM to the same depth as vLLM and SGLang.
- [ ] **14. Share and import.** Export a configuration as a link or file and import it, so a setup can move between people and machines.
- [ ] **15. Catalog upkeep.** Refresh the curated models, and add a lightweight way to update the catalog without editing the page.
- [ ] **16. Private repositories.** Offer a clear, token-free path for private Hugging Face repositories beyond pasting an exact reference.

### Polish

- [ ] **17. Accessibility pass.** Keyboard-only walkthrough, screen-reader audit of the checks and flag map, contrast and reduced-motion checks.
- [ ] **18. Phone and tablet audit.** Review every breakpoint on real devices, including the live output panel and saved configurations.
- [ ] **19. Browser support matrix.** Test current Chrome, Safari, and Firefox, including clipboard fallbacks and local storage being unavailable.
- [ ] **20. Self-hosted fonts and offline mode.** Remove the Google Fonts request so the page works fully offline.
- [ ] **21. Continuous checks.** Run the tests and a link and asset check on every change.
- [ ] **22. Release.** Refresh screenshots with `assets/readme/render.py`, tag a version, deploy, and remove the "prototype" label from this README.
