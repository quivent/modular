"""The desk: read a source, compare it with the shelf, file what is safe, hold what is not.

Everything that changes a data file goes through `apply_ops`, and everything is written down in the
ledger. Nothing here pushes, deploys, or deletes without a person approving it.
"""
import contextlib, copy, datetime as dt, json, os, pathlib, re, shutil, subprocess, sys, threading, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIELDS = ("aliases", "negation", "choices", "default", "help", "value")
# A change to these on a flag our commands use could change what the app generates: a person decides.
GUARDED = ("default", "choices", "aliases", "negation")
NAME = re.compile(r"^(-{1,2}[A-Za-z0-9][\w.\-]*|[A-Z][A-Z0-9_]+)$")
TOUCHED = ["index.html", "catalog/flags", "catalog/facts.json"]  # what the librarian may change: nothing else
LOCK = threading.RLock()


def today():
    return dt.date.today().isoformat()


def dump(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def write_atomic(path, text):
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".librarian-tmp")
    tmp.write_text(text)
    os.replace(tmp, path)  # never leave a half-written file


def flags_of(data):
    return [f for s in data.get("sections", []) for f in s.get("flags", [])]


def same(a, b):
    return (a or None) == (b or None)  # [] and None both mean "nothing"


# ── comparing ────────────────────────────────────────────────────────────────────────────────
def validate(engine, staged, current):
    """Reasons not to trust a fresh read at all (the source may have changed shape)."""
    problems = []
    if not isinstance(staged, dict) or not isinstance(staged.get("sections"), list):
        return ["the read has no sections"]
    if staged.get("engine") != engine:
        problems.append(f"the read says it is for {staged.get('engine')!r}")
    if not str(staged.get("source", "")).startswith("https://"):
        problems.append("the read does not name an https source")
    flags = flags_of(staged)
    names = [f.get("name", "") for f in flags]
    if not flags:
        problems.append("no flags were found")
    if len(set(names)) != len(names):
        problems.append("a flag appears twice")
    odd = [n for n in names if not NAME.match(n)]
    if odd:
        problems.append("these do not look like flags: " + ", ".join(odd[:5]))
    have = len(flags_of(current)) if current else 0
    if have and len(flags) < 0.7 * have:
        problems.append(f"only {len(flags)} of the {have} flags we hold were found: the source may have changed shape")
    if have and flags:
        blank = lambda fs: sum(1 for f in fs if not f.get("help")) / len(fs)
        if blank(flags) > 0.3 and blank(flags_of(current)) < 0.1:
            problems.append("most descriptions came back empty")
    return problems


def diff(current, staged):
    """What would have to happen to the shelf to match the source, as small separate operations."""
    now = {f["name"]: (s["title"], f) for s in current.get("sections", []) for f in s["flags"]}
    new = {f["name"]: (s["title"], f) for s in staged.get("sections", []) for f in s["flags"]}
    ops = []
    for name, (section, flag) in new.items():
        if name not in now:
            ops.append({"op": "add", "name": name, "section": section, "flag": flag})
            continue
        old = now[name][1]
        for field in FIELDS:
            if not same(old.get(field), flag.get(field)):
                ops.append({"op": "set", "name": name, "field": field, "from": old.get(field), "to": flag.get(field)})
    for name, (section, flag) in now.items():
        if name not in new:
            ops.append({"op": "remove", "name": name, "section": section, "flag": flag})
    for field in ("sources", "support"):  # which pages the data came from, and which architectures the engine runs
        if staged.get(field) and staged[field] != current.get(field):
            ops.append({"op": "meta", "field": field, "to": staged[field]})
    return ops


def profile_flags(root):
    """Flag names the app's engine profiles use: changes to those are never filed without a person."""
    page = (pathlib.Path(root) / "index.html").read_text()
    i = page.find("▸ js: engine profiles")
    j = page.find("/* ▸", i + 1)
    block = page[i : j if j > 0 else len(page)]
    names = set(re.findall(r"flag:\s*'(-{1,2}[\w.\-]+)'", block))
    # engines whose commands are still written by hand name their flags in the command code itself
    k = page.find("▸ js: command generation")
    hand = page[k : page.find("/* ▸", k + 1)] if k >= 0 else ""
    return names | set(re.findall(r"['\" ](--[a-z][\w\-]*)", hand))


def classify(ops, guarded_names):
    safe, held = [], []
    for op in ops:
        if op["op"] in ("add", "meta"):
            safe.append(op)
        elif op["op"] == "remove":
            held.append({**op, "why": "a flag we hold is gone from the source: renamed, removed, or the page changed"})
        elif op["name"] in guarded_names and op["field"] in GUARDED:
            held.append({**op, "why": f"the app's commands use {op['name']}, and its {op['field']} changed"})
        else:
            safe.append(op)
    return safe, held


def apply_ops(current, ops, release=None, when=None):
    """The only function that edits a collection. Works on a copy; returns the new collection."""
    data = copy.deepcopy(current)
    by_name = lambda: {f["name"]: f for f in flags_of(data)}
    for op in ops:
        if op["op"] == "add":
            if op["name"] in by_name():
                continue
            section = next((s for s in data["sections"] if s["title"] == op["section"]), None)
            if section is None:
                section = {"title": op["section"], "flags": []}
                data["sections"].append(section)
            section["flags"].append(op["flag"])
        elif op["op"] == "set":
            flag = by_name().get(op["name"])
            if flag is not None:
                flag[op["field"]] = op["to"]
        elif op["op"] == "meta":
            data[op["field"]] = op["to"]
        elif op["op"] == "remove":
            for s in data["sections"]:
                s["flags"] = [f for f in s["flags"] if f["name"] != op["name"]]
    data["sections"] = [s for s in data["sections"] if s["flags"]]
    head = {"engine": data["engine"], "source": data["source"], "fetched": when or today()}
    if release or data.get("release"):
        head["release"] = release or data["release"]
    head["count"] = len(flags_of(data))
    rest = {k: v for k, v in data.items() if k not in head and k != "sections"}
    return {**head, **rest, "sections": data["sections"]}


# ── facts about models (context limits, cache costs, recipe requirements) ────────────────────
def diff_facts(current, fresh):
    """Field-level changes that would make the shelf match a fresh read."""
    ops = []
    for ref, f in fresh.items():
        old = current.get(ref, {})
        for k, v in f.items():
            if k != "fetched" and old.get(k) != v:
                ops.append({"op": "fact", "ref": ref, "field": k, "from": old.get(k), "to": v})
        for k in old:
            if k != "fetched" and k not in f:
                ops.append({"op": "fact", "ref": ref, "field": k, "from": old[k], "to": None})
    return ops


def classify_facts(ops):
    """A fact that gains or changes a value is filed. One that vanishes may be a failed read, so a person decides."""
    safe, held = [], []
    for op in ops:
        if op["to"] is None and op["from"] is not None:
            held.append({**op, "why": f"{op['field']} of {op['ref']} is gone from the fresh read"})
        else:
            safe.append(op)
    return safe, held


def apply_fact_ops(current, ops, when=None):
    data = copy.deepcopy(current)
    for op in ops:
        entry = data.setdefault(op["ref"], {})
        if op["to"] is None:
            entry.pop(op["field"], None)
        else:
            entry[op["field"]] = op["to"]
        entry["fetched"] = when or today()
    return dict(sorted(data.items()))


# ── the desk ─────────────────────────────────────────────────────────────────────────────────
class Librarian:
    def __init__(self, root=ROOT, extract=None, verify=None, commit=True, tracker=None, extract_facts=None):
        self.root = pathlib.Path(root)
        self.extract_facts = extract_facts or self._extract_facts
        self.flags = self.root / "catalog" / "flags"
        self.var = self.root / "librarian" / "var"
        self.extract = extract or self._extract
        self.verify = verify or self._verify
        self.commit = commit
        self.tracker = tracker if tracker is not None else self._tracker
        for d in ("inbox", "stage"):
            (self.var / d).mkdir(parents=True, exist_ok=True)

    # – small helpers –
    def run(self, *cmd, check=True, timeout=600):
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode:
            raise RuntimeError(f"{' '.join(cmd)} failed: {(r.stdout + r.stderr).strip()[-600:]}")
        return r

    def load(self, engine):
        return json.loads((self.flags / f"{engine}.json").read_text())

    def state(self):
        p = self.var / "state.json"
        state = json.loads(p.read_text()) if p.exists() else {}
        for key in ("seen", "ran", "models", "fingerprints", "facts"):
            state.setdefault(key, {})
        return state

    def save_state(self, state):
        write_atomic(self.var / "state.json", json.dumps(state, indent=1) + "\n")

    def note(self, **entry):
        entry = {"at": dt.datetime.now().isoformat(timespec="seconds"), **entry}
        with open(self.var / "ledger.jsonl", "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def busy(self):
        """Files the librarian would touch that a person has changed and not yet committed."""
        if not (self.root / ".git").exists():
            return []
        out = self.run("git", "status", "--porcelain", "--", *TOUCHED, check=False).stdout
        return [l[3:] for l in out.splitlines()]

    # – reading the world –
    def _extract(self, engine):
        stage = self.var / "stage" / engine
        stage.mkdir(parents=True, exist_ok=True)
        self.run(sys.executable, "tools/flags.py", "--out", str(stage), engine, timeout=300)
        return json.loads((stage / f"{engine}.json").read_text())

    def _extract_facts(self):
        stage = self.var / "stage" / "facts.json"
        shutil.copy(self.root / "catalog" / "facts.json", stage)  # the read starts from what is known and only adds to it
        self.run(sys.executable, "tools/facts.py", "--out", str(stage), timeout=1500)
        return json.loads(stage.read_text())

    def _verify(self):
        r = self.run("node", "tests/run.mjs", "unit", check=False)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]

    def _tracker(self, title, detail):
        """Leave a note on the local tracker if its server is up. Silence if it is not."""
        try:
            req = urllib.request.Request(
                os.environ.get("MODULAR_URL", "http://127.0.0.1:8420") + "/api/tasks",
                data=json.dumps({"group": "trust", "title": title[:200], "detail": detail[:1900]}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            pass

    # – the work –
    def rebuild(self):
        """Rewrite only the generated block of index.html from the data files."""
        self.run("node", "tools/bundle.mjs", timeout=120)

    def file(self, engine, ops, release, message):
        """Write ops to the shelf, rebuild the page's copy, test, then commit. Undo everything if a test fails."""
        with LOCK:
            path = self.flags / f"{engine}.json"
            page = self.root / "index.html"
            before = {path: path.read_text(), page: page.read_text()}
            try:
                write_atomic(path, dump(apply_ops(json.loads(before[path]), ops, release)))
                self.rebuild()
                ok, tail = self.verify()
                if not ok:
                    raise RuntimeError("tests failed after the change:\n" + tail)
            except Exception as e:
                for p, text in before.items():
                    write_atomic(p, text)  # put back exactly what was there
                return False, str(e)
            sha = None
            if self.commit and (self.root / ".git").exists():
                self.run("git", "add", "--", f"catalog/flags/{engine}.json", "index.html")
                env = {**os.environ, "GIT_AUTHOR_NAME": "Librarian", "GIT_AUTHOR_EMAIL": "librarian@modular.local",
                       "GIT_COMMITTER_NAME": "Librarian", "GIT_COMMITTER_EMAIL": "librarian@modular.local"}
                subprocess.run(["git", "commit", "-q", "-m", message, "--", f"catalog/flags/{engine}.json", "index.html"],
                               cwd=self.root, env=env, capture_output=True, text=True, check=True)
                sha = self.run("git", "rev-parse", "--short", "HEAD").stdout.strip()
            return True, sha

    def hold(self, kind, engine, release, summary, ops=None, problems=None):
        with LOCK:
            n = len(list((self.var / "inbox").glob("*.json"))) + 1
            item = {"id": f"{today()}-{engine}-{n}", "status": "open", "kind": kind, "engine": engine, "release": release,
                    "summary": summary, "ops": ops or [], "problems": problems or [], "opened": today()}
            write_atomic(self.var / "inbox" / f"{item['id']}.json", json.dumps(item, indent=1, ensure_ascii=False) + "\n")
            self.tracker(f"Librarian: {summary}", f"python3 -m librarian show {item['id']}   (apply or dismiss)")
            return item

    def handle(self, engine, release=None, force=False):
        """One engine, one release. Returns what happened, in a sentence a person can read."""
        with LOCK:
            state = self.state()
            if not force and release and state["seen"].get(engine) == release:
                return {"engine": engine, "outcome": "seen", "said": f"{engine} {release}: already looked at"}
            dirty = self.busy()
            if dirty:
                return {"engine": engine, "outcome": "deferred",
                        "said": "waiting: these have uncommitted changes, so I will not touch them: " + ", ".join(dirty)}
            current = self.load(engine)
            try:
                staged = self.extract(engine)
            except Exception as e:
                return {"engine": engine, "outcome": "unreadable", "said": f"could not read the {engine} source: {e}"}
            problems = validate(engine, staged, current)
            if problems:
                item = self.hold("unreadable", engine, release, f"{engine} {release or ''}: the new read looks wrong",
                                 problems=problems)
                state["seen"][engine] = release
                self.save_state(state)
                self.note(kind="held", engine=engine, release=release, item=item["id"], problems=problems)
                return {"engine": engine, "outcome": "held", "said": f"{engine}: not trusting the new read ({problems[0]})", "item": item["id"]}
            safe, held = classify(diff(current, staged), profile_flags(self.root))
            result = {"engine": engine, "release": release, "added": 0, "changed": 0, "held": len(held)}
            said = []
            if safe:
                added = sum(1 for o in safe if o["op"] == "add")
                msg = f"Librarian: {engine} {release or ''} — {added} flag(s) added, {len(safe) - added} detail(s) updated".replace("  ", " ")
                ok, info = self.file(engine, safe, release, msg)
                if not ok:
                    item = self.hold("failed", engine, release, f"{engine}: a safe-looking change broke the tests, so I put everything back",
                                     ops=safe, problems=[info])
                    self.note(kind="rolled-back", engine=engine, release=release, item=item["id"])
                    return {"engine": engine, "outcome": "rolled-back", "said": f"{engine}: change undone, the tests failed", "item": item["id"]}
                result.update(added=added, changed=len(safe) - added, commit=info)
                said.append(f"filed {added} new flag(s) and {len(safe) - added} detail change(s)")
                self.note(kind="filed", engine=engine, release=release, commit=info, ops=[{k: v for k, v in o.items() if k != "flag"} for o in safe])
            if held:
                item = self.hold("review", engine, release, f"{engine} {release or ''}: {len(held)} change(s) need a person", ops=held)
                result["item"] = item["id"]
                said.append(f"held {len(held)} for you ({item['id']})")
                self.note(kind="held", engine=engine, release=release, item=item["id"], count=len(held))
            if not safe and not held:
                self.note(kind="checked", engine=engine, release=release)
                said.append("nothing new")
            state["seen"][engine] = release
            state["ran"][engine] = dt.datetime.now().isoformat(timespec="seconds")
            self.save_state(state)
            result.update(outcome="filed" if safe else ("held" if held else "unchanged"), said=f"{engine} {release or ''}: " + ", ".join(said))
            return result

    def file_facts(self, ops, message):
        """Like file(), for the facts: write, rebuild the page's copy, test, commit, and put everything back if a test fails."""
        with LOCK:
            path = self.root / "catalog" / "facts.json"
            page = self.root / "index.html"
            before = {path: path.read_text(), page: page.read_text()}
            try:
                write_atomic(path, json.dumps(apply_fact_ops(json.loads(before[path]), ops), indent=1) + "\n")
                self.rebuild()
                ok, tail = self.verify()
                if not ok:
                    raise RuntimeError("tests failed after the change:\n" + tail)
            except Exception as e:
                for p, text in before.items():
                    write_atomic(p, text)
                return False, str(e)
            sha = None
            if self.commit and (self.root / ".git").exists():
                self.run("git", "add", "--", "catalog/facts.json", "index.html")
                env = {**os.environ, "GIT_AUTHOR_NAME": "Librarian", "GIT_AUTHOR_EMAIL": "librarian@modular.local",
                       "GIT_COMMITTER_NAME": "Librarian", "GIT_COMMITTER_EMAIL": "librarian@modular.local"}
                subprocess.run(["git", "commit", "-q", "-m", message, "--", "catalog/facts.json", "index.html"],
                               cwd=self.root, env=env, capture_output=True, text=True, check=True)
                sha = self.run("git", "rev-parse", "--short", "HEAD").stdout.strip()
            return True, sha

    def refresh_facts(self):
        """Re-read what the models and the vLLM recipes say, and file what changed."""
        with LOCK:
            dirty = self.busy()
            if dirty:
                return {"outcome": "deferred", "said": "facts: waiting, these have uncommitted changes: " + ", ".join(dirty)}
            current = json.loads((self.root / "catalog" / "facts.json").read_text())
            try:
                fresh = self.extract_facts()
            except Exception as e:
                return {"outcome": "unreadable", "said": f"facts: could not read: {str(e)[:120]}"}
            safe, held = classify_facts(diff_facts(current, fresh))
            state = self.state()
            state["facts"]["ran"] = dt.datetime.now().isoformat(timespec="seconds")
            said = []
            if safe:
                refs = len({o["ref"] for o in safe})
                ok, info = self.file_facts(safe, f"Librarian: model facts — {len(safe)} change(s) across {refs} model(s)")
                if not ok:
                    item = self.hold("failed", "facts", None, "facts: a change broke the tests, so I put everything back", ops=safe, problems=[info])
                    self.note(kind="rolled-back", engine="facts", item=item["id"])
                    self.save_state(state)
                    return {"outcome": "rolled-back", "said": "facts: change undone, the tests failed", "item": item["id"]}
                said.append(f"filed {len(safe)} change(s) across {refs} model(s)")
                self.note(kind="filed", engine="facts", commit=info, count=len(safe))
            if held:
                item = self.hold("review", "facts", None, f"facts: {len(held)} change(s) need a person", ops=held)
                said.append(f"held {len(held)} for you ({item['id']})")
                self.note(kind="held", engine="facts", item=item["id"], count=len(held))
            if not safe and not held:
                self.note(kind="checked", engine="facts")
                said.append("nothing new")
            self.save_state(state)
            return {"outcome": "filed" if safe else ("held" if held else "unchanged"), "said": "facts: " + ", ".join(said)}

    def remember(self, fingerprints):
        """Keep what a page looked like when we last read from it."""
        if not fingerprints:
            return
        with LOCK:
            state = self.state()
            state["fingerprints"].update(fingerprints)
            self.save_state(state)

    # – the inbox –
    def items(self, status="open"):
        out = [json.loads(p.read_text()) for p in sorted((self.var / "inbox").glob("*.json"))]
        return [i for i in out if status is None or i["status"] == status]

    def item(self, ident):
        p = self.var / "inbox" / f"{ident}.json"
        if not p.exists():
            raise KeyError(f"no inbox item {ident}")
        return json.loads(p.read_text()), p

    def resolve(self, ident, apply):
        with LOCK:
            item, p = self.item(ident)
            if item["status"] != "open":
                return f"{ident} is already {item['status']}"
            if apply:
                if item["kind"] not in ("review", "failed"):
                    return f"{ident} is a note, not a change: dismiss it once you have looked"
                dirty = self.busy()
                if dirty:
                    return "not now: these have uncommitted changes: " + ", ".join(dirty)
                if item["engine"] == "facts":
                    ok, info = self.file_facts(item["ops"], f"Librarian: model facts — approved: {len(item['ops'])} change(s)")
                else:
                    ok, info = self.file(item["engine"], item["ops"], item["release"], f"Librarian: {item['engine']} {item['release'] or ''} — approved: {len(item['ops'])} change(s)")
                if not ok:
                    return "undone, the tests failed:\n" + info
                self.note(kind="approved", engine=item["engine"], item=ident, commit=info)
                if item["engine"] != "facts":
                    state = self.state()
                    state["seen"][item["engine"]] = item["release"]
                    state["ran"][item["engine"]] = dt.datetime.now().isoformat(timespec="seconds")
                    self.save_state(state)
            item["status"] = "applied" if apply else "dismissed"
            write_atomic(p, json.dumps(item, indent=1, ensure_ascii=False) + "\n")
            return f"{ident}: {item['status']}"

    # – keeping the page's copy in step –
    def sync(self):
        """Safe by construction: rewrites only the generated block, and only from data files that pass inspection."""
        bad = []
        for p in sorted(self.flags.glob("*.json")):
            try:
                d = json.loads(p.read_text())
                problems = validate(d.get("engine"), d, None)
            except Exception as e:
                problems = [str(e)]
            if problems:
                bad.append(f"{p.name}: {problems[0]}")
        if bad:
            return False, "not touching the page: a data file needs a person first: " + "; ".join(bad)
        self.rebuild()
        return True, "the page's copy matches the data files"

    def gate(self):
        """For before a deploy: in step, or brought in step safely, or a clear message for a person."""
        r = self.run("node", "tools/bundle.mjs", "--check", check=False)
        if r.returncode == 0:
            return True, "in sync"
        ok, said = self.sync()
        if not ok:
            return False, said
        r = self.run("node", "tools/bundle.mjs", "--check", check=False)
        return r.returncode == 0, ("brought into step: commit index.html" if r.returncode == 0 else "still out of step: " + r.stdout.strip())
