# Contributing to Modular

Modular is one self-contained page (`index.html`), a small local server, and data files. There is no
build step and no dependencies to install.

## What you need

- **Python 3.9 or newer**, standard library only (tested on 3.9 and 3.14)
- **Node 22 or newer** for the tests, which use its built-in WebSocket (tested on 26)
- **Chrome or Chromium** (for the browser tests; set `CHROME=/path/to/chrome` if it is not found)
- **sqlite3** (only for the database migration test)

## Run it

```sh
python3 server.py            # http://127.0.0.1:8420, plus the tracker and saved-state database
```

Any static server also works for the configurator alone: `python3 -m http.server 8420`.

## Run the tests

```sh
node tests/run.mjs           # everything
node tests/run.mjs unit      # only files whose path contains "unit"
```

The browser tests start their own server and their own headless Chrome on free ports, with a
temporary database, and stop only what they started. They never touch `db/modular.db` or the server
you may have running. Without Chrome they report SKIP, not a pass.

Before you commit, these three should be green:

```sh
python3 tools/map.py --check                      # the regions of index.html are well formed
python3 -m py_compile server.py tools/*.py db/*.py
node tests/run.mjs
```

## Find your way around `index.html`

The file is one page, organised into named regions marked `▸ name`. Print the map, or one region:

```sh
python3 tools/map.py                 # every region with its line range
python3 tools/map.py "memory estimate"   # print one region
```

## Common changes

**Add or update a model.** Add an entry to the `models` array in the region `js: data`. Append it at
the end so saved favorites (which remember a position) stay valid. Give it a `kind`, a `group`, and a
`label`; for audio a `role`. Use only the current generation of a family: retire older versions with
`retired: true` instead of deleting them. To let the memory check cover it, add its checkpoint size
(`gib`, the size of the files on Hugging Face) to `MEMORY_SHAPES`. `python3 tools/scan.py` reads
Hugging Face and suggests what is new; it never edits the catalog.

**Refresh the flag lists.** Don't edit them by hand: the librarian does it (`python3 -m librarian --help`).
It reads an engine's documentation when the engine publishes a release or when a page it reads changes
(`python3 -m librarian serve`, or `poll` once), files additions and description changes, holds back anything that could change what the app
generates (`inbox`, then `apply` or `dismiss`), runs the tests, and commits locally. It never pushes or
deploys, and it leaves alone any file you have uncommitted changes in. `python3 tools/flags.py` is the
extractor it uses. The page carries its own copy of the lists: before a deploy run `python3 -m librarian gate`.

**Model facts.** What decides whether a model starts (its context limit, what a token costs in cache, its
architecture, whether it ships its own code) is read from its own `config.json` by `python3 tools/facts.py`
into `catalog/facts.json`, together with what the vLLM recipes say it needs (`tools/recipes.py`). Nothing about a
model is typed into the page by hand. Gated repositories need `HF_TOKEN` to be read. The librarian refreshes
these daily (`python3 -m librarian facts` does it now). After any change to the data, `python3 tools/bundle.mjs`
puts it into the page and the tests check the two agree.

**Add an engine.** Add it to `servers` and `portDefaults` (region `js: data`), write its branch in
`command()` and `flagRows()`, add a parser for its documentation to `tools/flags.py`, and cover it in
`tests/browser/app.test.mjs`. Take flag names from the engine's reference, not from memory.

**Change the second page (Stack).** It lives in the same file: the regions `html: stack`, `css: stack` and `js: stack`,
shown when the address ends in `#stack`. A service's command always comes from `dockerCommand()`, so the two pages
cannot disagree; the stack adds only the name, port and GPUs. Take anything new the script runs from that tool's own
documentation and say where in the comment at the top of `js: stack`. `tests/browser/stack.test.mjs` covers it.

**Add a theme.** Copy a block in the region `css: themes` and change the role variables. Add it to
the `THEMES` list in `js: themes`.

## Rules the project follows

They are written out in [design-laws.md](design-laws.md). The short version: keep the page calm, do
only what was asked, use the words practitioners use, take facts from sources and date them, and
never show a command Modular cannot stand behind.

- Commits stay local until someone reviews them. Nothing here deploys itself.
- The tracker (`python3 server.py`, the Tracker button) is the task list. Its database is local to your
  machine and starts from the roadmap, so `@fix_plan.md` in the repository is a snapshot of the
  maintainer's tracker. `python3 tools/fix_plan.py` regenerates it from yours.
