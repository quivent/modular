"""Tests for the librarian. They work on a throwaway copy of the repository, never the real one."""
import copy, json, pathlib, shutil, subprocess, tempfile, unittest, urllib.request

from . import feeds, models, serve, service, triggers
from .core import ROOT, Librarian, apply_ops, classify, diff, flags_of, validate


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Shelf(unittest.TestCase):
    """A copy of the repo's data, the page and the bundler, under git."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="librarian-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "tools").mkdir()
        shutil.copy(ROOT / "index.html", self.tmp / "index.html")
        shutil.copy(ROOT / "tools" / "bundle.mjs", self.tmp / "tools" / "bundle.mjs")
        shutil.copy(ROOT / ".gitignore", self.tmp / ".gitignore")
        shutil.copytree(ROOT / "catalog" / "flags", self.tmp / "catalog" / "flags")
        shutil.copy(ROOT / "catalog" / "facts.json", self.tmp / "catalog" / "facts.json")
        sh(self.tmp, "git", "init", "-q")
        sh(self.tmp, "git", "config", "user.email", "t@t")
        sh(self.tmp, "git", "config", "user.name", "t")
        sh(self.tmp, "git", "add", "-A")
        sh(self.tmp, "git", "commit", "-q", "-m", "base")
        self.count = len(flags_of(json.loads((self.tmp / 'catalog/flags/vllm.json').read_text())))  # whatever the shelf holds today
        self.told = []
        self.ok = (True, "")
        self.world = {}  # what each engine's source looks like right now: engine -> data
        self.lib = Librarian(self.tmp, extract=lambda e: copy.deepcopy(self.world.get(e) or self.lib.load(e)),
                             verify=lambda: self.ok, tracker=lambda *a: self.told.append(a))

    def data(self, engine="vllm"):
        return self.lib.load(engine)

    def head(self):
        return sh(self.tmp, "git", "rev-parse", "HEAD")

    def in_sync(self):
        return subprocess.run(["node", "tools/bundle.mjs", "--check"], cwd=self.tmp, capture_output=True).returncode == 0

    def with_new_flag(self, engine="vllm", name="--brand-new-thing", help="Does a brand new thing."):
        d = self.data(engine)
        d["sections"][0]["flags"].append({"name": name, "aliases": [], "negation": None, "choices": None, "default": None, "help": help})
        return d


class Judging(Shelf):
    def test_new_flags_and_better_descriptions_are_safe_but_removals_and_guarded_changes_are_held(self):
        cur = self.data()
        new = copy.deepcopy(cur)
        new["sections"][0]["flags"].append({"name": "--extra", "aliases": [], "negation": None, "choices": None, "default": None, "help": "x"})
        new["sections"][0]["flags"][0]["help"] = "A better description."
        gone = new["sections"][0]["flags"].pop(1)["name"]
        safe, held = classify(diff(cur, new), {"--port"})
        self.assertEqual({(o["op"], o["name"]) for o in safe}, {("add", "--extra"), ("set", new["sections"][0]["flags"][0]["name"])})
        self.assertEqual([(o["op"], o["name"]) for o in held], [("remove", gone)])
        # a default that changes is held for a flag the app's commands use, and filed for one they do not
        other = copy.deepcopy(cur)
        flag = other["sections"][0]["flags"][0]
        flag["default"] = "changed"
        self.assertEqual(len(classify(diff(cur, other), {flag["name"]})[1]), 1)
        self.assertEqual(len(classify(diff(cur, other), set())[0]), 1)

    def test_a_read_that_looks_wrong_is_not_trusted(self):
        cur = self.data()
        thin = copy.deepcopy(cur)
        thin["sections"][0]["flags"] = thin["sections"][0]["flags"][:3]
        thin["sections"] = thin["sections"][:1]
        self.assertTrue(any("changed shape" in p for p in validate("vllm", thin, cur)))
        odd = copy.deepcopy(cur)
        odd["sections"][0]["flags"][0]["name"] = "<div>nav</div>"
        self.assertTrue(any("do not look like flags" in p for p in validate("vllm", odd, cur)))
        twice = copy.deepcopy(cur)
        twice["sections"][0]["flags"].append(copy.deepcopy(twice["sections"][0]["flags"][0]))
        self.assertTrue(any("twice" in p for p in validate("vllm", twice, cur)))
        self.assertEqual(validate("vllm", cur, cur), [])

    def test_applying_changes_keeps_everything_else_and_never_drops_what_it_was_not_told_to(self):
        cur = self.data()
        before = {f["name"]: f for f in flags_of(cur)}
        out = apply_ops(cur, [{"op": "add", "name": "--z", "section": "Brand new section", "flag": {"name": "--z", "help": "h"}}], "v9", "2030-01-01")
        self.assertEqual(out["fetched"], "2030-01-01")
        self.assertEqual(out["release"], "v9")
        self.assertEqual(out["count"], len(before) + 1)
        self.assertEqual(out["sections"][-1]["title"], "Brand new section")
        self.assertTrue(all(before[n] == f for n, f in ((f["name"], f) for f in flags_of(out)) if n in before))
        self.assertEqual(list(out)[:4], ["engine", "source", "fetched", "release"])
        gone = flags_of(cur)[0]["name"]
        self.assertNotIn(gone, [f["name"] for f in flags_of(apply_ops(cur, [{"op": "remove", "name": gone}]))])


class Filing(Shelf):
    def test_a_release_with_new_flags_is_filed_tested_and_committed_by_the_librarian(self):
        self.world["vllm"] = self.with_new_flag()
        before = self.head()
        r = self.lib.handle("vllm", "v9.9.9")
        self.assertEqual(r["outcome"], "filed")
        self.assertEqual(r["added"], 1)
        self.assertIn("--brand-new-thing", [f["name"] for f in flags_of(self.data())])
        self.assertTrue(self.in_sync(), "the page's copy was rebuilt")
        self.assertNotEqual(self.head(), before)
        self.assertEqual(sh(self.tmp, "git", "log", "-1", "--format=%an"), "Librarian")
        self.assertEqual(self.data()["release"], "v9.9.9")
        self.assertEqual(self.lib.handle("vllm", "v9.9.9")["outcome"], "seen", "the same release is not handled twice")
        self.assertEqual(sh(self.tmp, "git", "status", "--porcelain"), "")

    def test_a_removal_waits_for_a_person_and_is_filed_when_approved(self):
        d = self.data()
        gone = d["sections"][0]["flags"].pop(0)["name"]
        self.world["vllm"] = d
        r = self.lib.handle("vllm", "v2")
        self.assertEqual(r["outcome"], "held")
        self.assertIn(gone, [f["name"] for f in flags_of(self.data())], "nothing was deleted")
        self.assertEqual(len(self.lib.items()), 1)
        self.assertEqual(len(self.told), 1, "it left a note on the tracker")
        before = self.head()
        self.assertIn("applied", self.lib.resolve(r["item"], apply=True))
        self.assertNotIn(gone, [f["name"] for f in flags_of(self.data())])
        self.assertNotEqual(self.head(), before)
        self.assertEqual(self.lib.items(), [])

    def test_dismissing_changes_nothing(self):
        d = self.data()
        d["sections"][0]["flags"].pop(0)
        self.world["vllm"] = d
        r = self.lib.handle("vllm", "v2")
        before = self.head()
        self.assertIn("dismissed", self.lib.resolve(r["item"], apply=False))
        self.assertEqual(self.head(), before)
        self.assertEqual(len(flags_of(self.data())), self.count)

    def test_it_will_not_touch_files_a_person_has_changed(self):
        self.world["vllm"] = self.with_new_flag()
        page = self.tmp / "index.html"
        page.write_text(page.read_text() + "\n<!-- my unsaved work -->\n")
        before = self.head()
        r = self.lib.handle("vllm", "v3")
        self.assertEqual(r["outcome"], "deferred")
        self.assertEqual(self.head(), before)
        self.assertIn("my unsaved work", page.read_text())
        self.assertNotIn("--brand-new-thing", [f["name"] for f in flags_of(self.data())])
        self.assertNotIn("vllm", self.lib.state()["seen"], "it will try again later")

    def test_a_read_that_looks_wrong_changes_nothing_and_asks_for_a_person(self):
        thin = self.data()
        thin["sections"] = thin["sections"][:1]
        thin["sections"][0]["flags"] = thin["sections"][0]["flags"][:2]
        self.world["vllm"] = thin
        before = self.head()
        r = self.lib.handle("vllm", "v4")
        self.assertEqual(r["outcome"], "held")
        self.assertEqual(self.head(), before)
        self.assertEqual(len(flags_of(self.data())), self.count)
        self.assertEqual(self.lib.items()[0]["kind"], "unreadable")

    def test_if_the_tests_fail_everything_is_put_back_exactly(self):
        self.world["vllm"] = self.with_new_flag()
        files = {p: p.read_bytes() for p in (self.tmp / "index.html", self.tmp / "catalog/flags/vllm.json")}
        self.ok = (False, "1 failed")
        before = self.head()
        r = self.lib.handle("vllm", "v5")
        self.assertEqual(r["outcome"], "rolled-back")
        self.assertEqual(self.head(), before)
        self.assertEqual({p: p.read_bytes() for p in files}, files)
        self.assertEqual(self.lib.items()[0]["kind"], "failed")

    def test_the_page_copy_is_brought_into_step_or_refused_safely(self):
        page = self.tmp / "index.html"
        page.write_text(page.read_text().replace('"--host"', '"--hOST"', 1))
        self.assertFalse(self.in_sync())
        ok, said = self.lib.gate()
        self.assertTrue(ok, said)
        self.assertTrue(self.in_sync())
        bad = self.tmp / "catalog/flags/mlx.json"
        bad.write_text("{ not json")
        page.write_text(page.read_text().replace('"--host"', '"--hOST"', 1))
        ok, said = self.lib.gate()
        self.assertFalse(ok)
        self.assertIn("needs a person", said)
        self.assertEqual(bad.read_text(), "{ not json", "it did not 'fix' the broken file")


class World(unittest.TestCase):
    ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom">
    <entry><title>v1.2.0rc1: [CI] a long description of this release (#12)</title><link href="https://github.com/a/b/releases/tag/v1.2.0rc1"/></entry>
    <entry><title>v1.1.0</title><link href="https://github.com/a/b/releases/tag/v1.1.0"/></entry></feed>"""

    def test_release_feeds_give_the_tag_not_the_description(self):
        self.assertEqual(feeds.releases("a/b", lambda url: self.ATOM), ["v1.2.0rc1", "v1.1.0"])

    def test_webhooks_are_checked_and_understood(self):
        beat = json.loads((ROOT / "librarian" / "beat.json").read_text())
        ev = feeds.from_webhook({"action": "published", "repository": {"full_name": "vllm-project/vllm"}, "release": {"tag_name": "v1"}}, beat)
        self.assertEqual(ev, {"engine": "vllm", "release": "v1"})
        self.assertIsNone(feeds.from_webhook({"action": "published", "repository": {"full_name": "vllm-project/vllm"}, "release": {"tag_name": "v1", "draft": True}}, beat))
        self.assertIsNone(feeds.from_webhook({"action": "published", "repository": {"full_name": "someone/else"}, "release": {"tag_name": "v1"}}, beat))
        import hashlib, hmac
        body = b'{"a":1}'
        good = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
        self.assertTrue(feeds.signed("s", body, good))
        self.assertFalse(feeds.signed("s", body, "sha256=00"))
        self.assertFalse(feeds.signed("s", body, None))

    def test_the_models_desk_only_points_at_what_is_new(self):
        scan = {"curated": [{"id": "a/old", "suggested": "retired", "reasons": ["b/new has more downloads"]}, {"id": "a/ok", "suggested": "current"}],
                "labs": {"lab": {"new": [{"id": "lab/big", "downloads": 90000, "created": "2026-09-01"}, {"id": "lab/tiny", "downloads": 10, "created": "2026-09-01"}]}}}
        found = dict(models.notable(scan, set()))
        self.assertEqual(sorted(found), ["a/old=retired", "new=lab/big"])
        self.assertEqual(models.notable(scan, set(found)), [])
        self.assertEqual(sorted(dict(models.notable(scan, set(), retired={"a/old"}))), ["new=lab/big"], "a model the catalog already retired is not news")

    def test_the_catalog_can_be_read_without_opening_a_browser(self):
        cat = models.catalog(ROOT)
        self.assertTrue(cat["Qwen/Qwen3.8-27B"] is False and cat["Qwen/Qwen3-8B"] is True and len(cat) > 60)

    def test_the_login_agent_starts_serve_from_this_folder_and_keeps_it_running(self):
        a = service.agent(ROOT, python="/usr/bin/python3", path="/opt/homebrew/bin:/usr/bin")
        self.assertEqual(a["ProgramArguments"][1:5], ["-m", "librarian", "serve", "--port"])
        self.assertEqual(a["WorkingDirectory"], str(ROOT))
        self.assertTrue(a["RunAtLoad"] and a["KeepAlive"])
        self.assertIn("/opt/homebrew/bin", a["EnvironmentVariables"]["PATH"])  # it must find node and git
        self.assertTrue(a["StandardOutPath"].endswith("librarian/var/librarian.log"))
        import plistlib
        self.assertEqual(plistlib.loads(plistlib.dumps(a))["Label"], "com.modular.librarian")

    def test_the_listener_hands_events_to_the_desk_one_at_a_time(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="librarian-listen-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "catalog").mkdir()
        shutil.copytree(ROOT / "catalog" / "flags", tmp / "catalog" / "flags")
        shutil.copy(ROOT / "index.html", tmp / "index.html")
        handled = []
        lib = Librarian(tmp, extract=lambda e: lib.load(e), verify=lambda: (True, ""), tracker=lambda *a: None)
        lib.handle = lambda engine, release=None, force=False: (handled.append((engine, release)), {"said": f"{engine} ok"})[1]
        beat = json.loads((ROOT / "librarian" / "beat.json").read_text())
        listener = serve.Listener(lib, beat, port=0, watch=False, log=lambda *_: None).start()
        self.addCleanup(listener.close)
        url = f"http://127.0.0.1:{listener.port}"
        post = lambda path, obj: urllib.request.urlopen(urllib.request.Request(url + path, data=json.dumps(obj).encode(), method="POST")).status
        self.assertEqual(post("/event", {"engine": "sglang", "release": "v7"}), 202)
        self.assertEqual(post("/event", {"engine": "not-an-engine"}), 202)  # ignored politely
        for _ in range(40):
            if handled:
                break
            __import__("time").sleep(0.1)
        self.assertEqual(handled, [("sglang", "v7")])
        status = json.load(urllib.request.urlopen(url + "/status"))
        self.assertEqual(status["open"], 0)


class Triggers(Shelf):
    """What wakes the librarian: a new release, a changed page, or neither."""
    ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>v9.0.0</title><link href="https://github.com/o/r/releases/tag/v9.0.0"/></entry></feed>"""
    BEAT = {"default_cooldown_hours": 24, "models": {"scan_every_hours": 24}, "engines": {"vllm": {"repo": "o/r"}}}

    def pages(self, changed):
        calls = []
        def probe(url, previous):
            calls.append(url)
            fp = {"sha": "new" if changed else "same"}
            return (changed or not previous), (previous if not changed and previous else fp)
        return probe, calls

    def test_a_new_release_wakes_the_desk_and_a_changed_page_wakes_it_between_releases(self):
        data = self.data()
        probe, calls = self.pages(changed=False)
        ev = triggers.poll(self.lib, self.BEAT, fetch=lambda u: self.ATOM, probe=probe)
        self.assertEqual([(e["engine"], e["why"], e["release"]) for e in ev], [("vllm", "release", "v9.0.0")])
        self.assertEqual(calls, [data["source"]], "it looked at the page the data came from")
        # the same release has been handled; the page is unchanged -> nothing to do
        self.lib.handle("vllm", "v9.0.0", force=True)
        s = self.lib.state(); s["ran"]["vllm"] = "2000-01-01T00:00:00"; self.lib.save_state(s)
        self.lib.remember({data["source"]: {"sha": "same"}})
        probe, _ = self.pages(changed=False)
        self.assertEqual(triggers.poll(self.lib, self.BEAT, fetch=lambda u: self.ATOM, probe=probe), [])
        # no new release, but the page changed: a docs-only change is caught
        probe, _ = self.pages(changed=True)
        ev = triggers.poll(self.lib, self.BEAT, fetch=lambda u: self.ATOM, probe=probe)
        self.assertEqual([(e["engine"], e["why"], e["release"]) for e in ev], [("vllm", "page", None)])

    def test_an_engine_read_recently_is_left_alone(self):
        s = self.lib.state(); s["ran"]["vllm"] = dt_now_iso(); self.lib.save_state(s)
        probe, calls = self.pages(changed=True)
        self.assertEqual(triggers.poll(self.lib, self.BEAT, fetch=lambda u: self.ATOM, probe=probe), [])
        self.assertEqual(calls, [], "and not even asked about")

    def test_what_a_page_looked_like_is_kept_only_once_the_read_it_caused_is_dealt_with(self):
        fp = {"https://x/": {"sha": "abc"}}
        self.lib.handle = lambda engine, release=None, force=False: {"said": "x", "outcome": "deferred"}
        triggers.process(self.lib, [{"engine": "vllm", "release": None, "fingerprints": fp}], log=lambda *_: None)
        self.assertEqual(self.lib.state()["fingerprints"], {}, "a busy tree means we try again")
        self.lib.handle = lambda engine, release=None, force=False: {"said": "x", "outcome": "unchanged"}
        triggers.process(self.lib, [{"engine": "vllm", "release": None, "fingerprints": fp}], log=lambda *_: None)
        self.assertEqual(self.lib.state()["fingerprints"], fp)

    def test_the_pages_a_data_file_came_from_are_recorded_as_a_safe_change(self):
        staged = self.data(); staged["sources"] = ["https://a/", "https://b/"]
        self.world["vllm"] = staged
        r = self.lib.handle("vllm", None, force=True)
        self.assertEqual(r["outcome"], "filed")
        self.assertEqual(self.data()["sources"], ["https://a/", "https://b/"])
        self.assertEqual(triggers.sources_of(self.lib, "vllm"), ["https://a/", "https://b/"])
        self.assertEqual(len(flags_of(self.data())), self.count, "and no flag was touched")

    def test_probe_asks_cheaply_and_notices_a_change(self):
        import http.server, threading
        state = {"body": b"one", "etag": '"1"'}
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get("If-None-Match") == state["etag"]:
                    self.send_response(304); self.end_headers(); return
                self.send_response(200); self.send_header("ETag", state["etag"]); self.send_header("Content-Length", str(len(state["body"]))); self.end_headers(); self.wfile.write(state["body"])
            def log_message(self, *a): pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        changed, fp = feeds.probe(url, {})
        self.assertTrue(changed, "a page never seen is treated as changed")
        changed, fp2 = feeds.probe(url, fp)
        self.assertFalse(changed, "unchanged: the server answers 304 and nothing is downloaded")
        state.update(body=b"two", etag='"2"')
        changed, fp3 = feeds.probe(url, fp2)
        self.assertTrue(changed)
        self.assertNotEqual(fp3["sha"], fp["sha"])

    def test_hugging_face_webhooks_wake_the_models_desk(self):
        self.assertEqual(feeds.from_hf_webhook({"event": {"action": "update", "scope": "repo.content"}, "repo": {"type": "model", "name": "a/b"}}), {"models": True})
        self.assertIsNone(feeds.from_hf_webhook({"event": {"action": "update"}, "repo": {"type": "dataset", "name": "a/b"}}))
        self.assertIsNone(feeds.from_hf_webhook({"hello": 1}))


def dt_now_iso():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    unittest.main()
