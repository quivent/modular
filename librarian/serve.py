"""The listener: waits for events (a webhook, or its own regular look at the release feeds) and hands them to the desk.

One worker does one thing at a time, so two events can never write the same file together.
"""
import datetime as dt, hmac, json, os, queue, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import feeds, models, triggers


class Listener:
    def __init__(self, lib, beat, port=8431, host="127.0.0.1", watch=True, log=print):
        self.lib, self.beat, self.log, self.watch = lib, beat, log, watch
        self.q = queue.Queue()
        self.stop = threading.Event()
        listener = self

        class H(BaseHTTPRequestHandler):
            def reply(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/status":
                    return self.reply(200, listener.status())
                self.reply(404, {"error": "not found"})

            def do_POST(self):
                body = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1_000_000))
                secret = os.environ.get("LIBRARIAN_SECRET")  # GitHub signs the body; Hugging Face sends the secret itself
                if secret and not (feeds.signed(secret, body, self.headers.get("X-Hub-Signature-256"))
                                   or hmac.compare_digest(self.headers.get("X-Webhook-Secret") or "", secret)):
                    return self.reply(401, {"error": "bad signature"})
                if self.path == "/poll":
                    listener.q.put({"poll": True})
                    return self.reply(202, {"queued": "poll"})
                if self.path != "/event":
                    return self.reply(404, {"error": "not found"})
                try:
                    payload = json.loads(body or b"{}")
                except ValueError:
                    return self.reply(400, {"error": "expected JSON"})
                if "repository" in payload:
                    event = feeds.from_webhook(payload, listener.beat)
                elif "repo" in payload:
                    event = feeds.from_hf_webhook(payload)
                else:
                    event = {"engine": payload.get("engine"), "release": payload.get("release")} if payload.get("engine") in listener.beat["engines"] else None
                if not event:
                    return self.reply(202, {"ignored": True})
                listener.q.put(event)
                self.reply(202, {"queued": event})

            def log_message(self, *a):
                pass

        self.http = ThreadingHTTPServer((host, port), H)
        self.port = self.http.server_address[1]

    def status(self):
        s = self.lib.state()
        return {"open": len(self.lib.items()), "seen": s["seen"], "ran": s["ran"], "queued": self.q.qsize()}

    def work(self):
        while not self.stop.is_set():
            try:
                event = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if event.get("models"):
                    if triggers.models_due(self.lib, 1):  # a burst of Hugging Face events is one scan
                        models.run(self.lib)
                elif event.get("poll"):
                    triggers.process(self.lib, triggers.poll(self.lib, self.beat), self.log)
                    if triggers.models_due(self.lib, self.beat["models"]["scan_every_hours"]):
                        models.run(self.lib)
                else:
                    triggers.process(self.lib, [event], self.log)
            except Exception as e:  # one bad event must not stop the desk
                self.lib.note(kind="error", error=str(e)[:300])
                self.log(f"error: {e}")

    def tick(self):
        minutes = self.beat.get("poll_minutes", 60)
        while not self.stop.is_set():
            self.q.put({"poll": True})
            self.stop.wait(minutes * 60)

    def start(self):
        threads = [threading.Thread(target=self.http.serve_forever, daemon=True), threading.Thread(target=self.work, daemon=True)]
        if self.watch:
            threads.append(threading.Thread(target=self.tick, daemon=True))
        for t in threads:
            t.start()
        return self

    def close(self):
        self.stop.set()
        self.http.shutdown()
        self.http.server_close()
