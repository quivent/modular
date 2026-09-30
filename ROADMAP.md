# Roadmap to a finished Modular

Modular today is a complete, working prototype. This checklist is the path from
"generates a good starting command" to "a configuration you can trust."
Ordered by dependency, roughly: foundation, trust, reach, polish.

## Foundation

- [ ] **1. Separate the working copy.** `index.html` and `next.html` are identical. Decide the flow (edit `next.html`, promote to `index.html`) or delete one, and document it.
- [ ] **2. Split the single file.** Move the ~89 KB page into a semantic configuration model, engine renderers, checks, and UI modules. Keep it buildless (ES modules) so `python3 -m http.server` still works.
- [ ] **3. Reconcile the docs with the app.** `DESIGN.md` still cites 12 models in earlier sections; the app has 15. Keep one current-state summary at the top and move history below it.

## Trust

- [ ] **4. Versioned engine profiles.** Describe each engine's flags, defaults, accepted values, and conflicts as data (JSON) per version, then generate the renderer and checks from it.
- [ ] **5. Engine version selector.** Let the user pick the version they run and show how defaults or spellings differ before export.
- [ ] **6. Source links and last-checked dates.** Link each version-specific flag to its documentation, and label unknown compatibility as unknown.
- [ ] **7. Automated tests.** Golden-file tests for every engine and output format, plus tests for each check (oversubscription, omitted settings, duplicate arguments).
- [ ] **8. Better fit estimates.** Extend the weight-only note to KV cache and activation headroom for the chosen context and batch, clearly labeled as an estimate.

## Reach

- [ ] **9. More command forms.** Add environment-variable output and Kubernetes or Compose snippets, generated from the same configuration state.
- [ ] **10. Complete the remaining engines.** Bring TGI, llama.cpp, and MLX LM to the same depth as vLLM and SGLang.
- [ ] **11. Share and import.** Export a configuration as a link or file and import it, so a setup can move between people and machines.
- [ ] **12. Catalog upkeep.** Refresh the curated models, and add a lightweight way to update the catalog without editing the page.

## Polish

- [ ] **13. Accessibility pass.** Keyboard-only walkthrough, screen-reader audit of the checks and flag map, contrast and reduced-motion checks.
- [ ] **14. Self-hosted fonts and offline mode.** Remove the Google Fonts request so the page works fully offline.
- [ ] **15. Release.** Screenshots refreshed by `assets/readme/render.py`, a tagged version, hosted deployment, and the "prototype" label removed from the README.
