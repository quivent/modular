"""python3 -m librarian <command>

  status            what the desk has seen, and what is waiting for you
  plan ENGINE       read the source and show what would be filed and held. Changes nothing.
  event ENGINE [RELEASE]   handle one release now (reads the source, files the safe changes, holds the rest)
  poll              look at every release feed and documentation page once; re-read whatever changed
  inbox             what is waiting for a person        show ID    the details
  apply ID          approve a held change: it is filed, tested, committed        dismiss ID    set it aside
  models            run the Hugging Face scan and note what is worth a look
  facts             re-read every model's facts and vLLM recipe; file what changed, hold what vanished
  sync              rebuild the page's copy of the flag lists from the data files (safe: touches only the generated block)
  gate              before a deploy: in step, or brought into step, or a clear message
  install / uninstall   run it by itself: start at login, restart if it stops (macOS)
  serve [--port N] [--no-poll]   run the listener: POST /event (GitHub or Hugging Face webhooks), and a look at the feeds and pages every hour

It commits locally and never pushes or deploys. It will not touch index.html or catalog/flags while they have
uncommitted changes of yours.
"""
import json, pathlib, sys

from . import feeds, models, serve, service, triggers
from .core import Librarian, classify, diff, profile_flags, validate

BEAT = pathlib.Path(__file__).resolve().parent / "beat.json"


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    beat = json.loads(BEAT.read_text())
    lib = Librarian()
    if cmd == "status":
        s = lib.state()
        for engine in beat["engines"]:
            d = lib.load(engine)
            print(f"{engine:<7} {d['count']:>4} flags  read {d['fetched']}  release {d.get('release', '-'):<14} last looked {s['ran'].get(engine, 'never')}")
        live = service.running()
        print(f"\nlistening: {'yes, on port 8431, ' + str(live['queued']) + ' queued' if live else 'no  (python3 -m librarian install)'}")
        print("wakes on: release feeds · documentation page changes · webhooks (GitHub, Hugging Face)")
        print(f"waiting for you: {len(lib.items())}   (python3 -m librarian inbox)")
        return 0
    if cmd == "plan":
        engine = rest[0]
        current = lib.load(engine)
        staged = lib.extract(engine)
        problems = validate(engine, staged, current)
        print("the new read looks wrong: " + "; ".join(problems) if problems else "the new read looks sound")
        safe, held = classify(diff(current, staged), profile_flags(lib.root))
        print(f"would file {len(safe)}: " + ", ".join(f"{o['op']} {o['name']}" + (f".{o['field']}" if o['op'] == 'set' else "") for o in safe[:12]))
        print(f"would hold {len(held)}: " + ", ".join(f"{o['op']} {o['name']}" for o in held[:12]))
        return 0
    if cmd == "event":
        print(lib.handle(rest[0], rest[1] if len(rest) > 1 else None, force=True)["said"])
        return 0
    if cmd == "poll":
        events = triggers.poll(lib, beat)
        print(f"{len(events)} engine(s) to re-read" + (": " + ", ".join(f"{e['engine']} ({e['why']})" for e in events) if events else ""))
        triggers.process(lib, events)
        return 0
    if cmd == "inbox":
        for i in lib.items():
            print(f"{i['id']:<28} {i['kind']:<10} {i['summary']}")
        return 0
    if cmd == "show":
        item, _ = lib.item(rest[0])
        print(json.dumps({k: v for k, v in item.items() if k != "ops"}, indent=1))
        for o in item["ops"]:
            print(" ", o["op"], o["name"], o.get("field", ""), "|", o.get("why", ""))
        return 0
    if cmd in ("apply", "dismiss"):
        print(lib.resolve(rest[0], cmd == "apply"))
        return 0
    if cmd == "models":
        item = models.run(lib)
        print(item["summary"] if item else "nothing new")
        return 0
    if cmd in ("install", "uninstall"):
        ok, said = service.install(lib.root) if cmd == "install" else service.uninstall()
        print(said)
        return 0 if ok else 1
    if cmd == "facts":
        print(lib.refresh_facts()["said"])
        return 0
    if cmd == "sync":
        ok, said = lib.sync()
        print(said)
        return 0 if ok else 1
    if cmd == "gate":
        ok, said = lib.gate()
        print(said)
        return 0 if ok else 1
    if cmd == "serve":
        port = int(rest[rest.index("--port") + 1]) if "--port" in rest else 8431
        listener = serve.Listener(lib, beat, port=port, watch="--no-poll" not in rest).start()
        print(f"librarian listening on http://127.0.0.1:{listener.port}  (POST /event, POST /poll, GET /status). Ctrl-C to stop.")
        try:
            listener.stop.wait()
        except KeyboardInterrupt:
            listener.close()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
