# Roadmap to a finished Modular

Modular today is a complete, working prototype. This checklist is the path from "generates a good starting command" to "a configuration you can trust." It is mirrored at the end of the [README](README.md).

### Foundation

- [x] **1. Separate the working copy.** Rollback is git: releases are tagged (`v0.7` is the first), risky work happens on a branch, and `next.html` is retired.
- [ ] **2. Split the single file.** Move the ~89 KB page into a configuration model, engine renderers, checks, and UI modules. Stay buildless with ES modules so `python3 -m http.server` keeps working.
- [x] **3. Reconcile the docs with the app.** Resolved by deleting `DESIGN.md`, which had drifted from the app. It remains in git history.
- [ ] **4. Version the saved data.** Add a schema version to saved configurations and preferences in local storage, with migrations, so an update never strands someone's saved setups.
- [ ] **5. License and contributing guide.** The repository has no license file yet. Add one, plus short instructions for running, testing, and adding a model or engine.

### Trust

- [ ] **6. Versioned engine profiles.** Describe each engine's flags, defaults, accepted values, and conflicts as data per version, then generate the renderer and checks from it.
- [ ] **7. Engine version selector.** Let people pick the version they run, and show how defaults or spellings differ before export.
- [ ] **8. Source links and last-checked dates.** Link each version-specific flag to its documentation, and label unknown compatibility as unknown.
- [ ] **9. Automated tests.** Golden-file tests for every engine and output format, plus a test for each check (oversubscription, omitted settings, duplicate arguments).
- [ ] **10. Better fit estimates.** Extend the weight-only note to KV cache and activation headroom for the chosen context and batch, clearly labeled as an estimate.
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
