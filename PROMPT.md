# Modular: loop brief

Modular turns "serve this model" into a configuration you can trust: pick a model, an engine and a GPU
card, and get a launch command, every flag of the engine, and honest checks.

- App: `index.html` (one self-contained file, named regions, map with `python3 tools/map.py`).
- Local server and tracker: `python3 server.py` (SQLite in `db/`).
- Data: `catalog/flags/*.json` (from `python3 tools/flags.py`), `catalog/scan-latest.json`.
- Task list: `@fix_plan.md`, generated from the tracker (`python3 tools/fix_plan.py`). Change status in
  the tracker, then regenerate.
- Laws: `design-laws.md`. Gates: `python3 tools/map.py --check`, `python3 -m py_compile ...`,
  `node tests/run.mjs` once #9 lands.
- Rules: one step per iteration, observe before you submit, never push, never deploy from the loop,
  kill only PIDs this loop started.
