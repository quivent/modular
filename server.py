#!/usr/bin/env python3
"""Modular local server: serves the app and a small JSON API over SQLite.

    python3 server.py            # http://127.0.0.1:8420
    python3 server.py --port 9000

The database (db/modular.db) is created from db/schema.sql on first run and
seeded from ROADMAP.md. The server only listens on localhost.
"""
import argparse, base64, os, hashlib, json, mimetypes, pathlib, re, socket, sqlite3, struct, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
DB_PATH = pathlib.Path(os.environ.get("MODULAR_DB") or ROOT / "db" / "modular.db")  # tests point this at a temp file
MAX_BODY = 1_000_000
STATE_VERSION = 1  # shape of the /api/state envelope; the page sends and expects the same number
STATUSES = ("todo", "doing", "blocked", "done")
PRIVATE = {"db", "librarian"}  # never served as static files
LOCAL_HOSTS = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
LOCAL_ORIGIN = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn, version):
    """Upgrade a database created by an older schema. schema.sql is the newest shape."""
    if version == 1:  # v2: the default model moved from favorite_models to preferences
        conn.execute("DROP INDEX IF EXISTS one_default_model")
        old_default = conn.execute("SELECT model_ref FROM favorite_models WHERE is_default = 1").fetchone()
        conn.execute("ALTER TABLE favorite_models DROP COLUMN is_default")
        conn.execute("ALTER TABLE favorite_models ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
        if old_default:
            conn.execute("INSERT OR REPLACE INTO preferences (key, value) VALUES ('defaultModel', ?)",
                         (json.dumps(old_default[0]),))
        version = 2
    if version == 2:  # v3: saved configurations record the shape version of their snapshot
        conn.execute("ALTER TABLE saved_configurations ADD COLUMN snapshot_version INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE saved_configurations SET snapshot_version = COALESCE(json_extract(settings, '$.v'), 0)")


def init_db():
    fresh = not DB_PATH.exists()
    with connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if 0 < version < 3:
            migrate(conn, version)
        conn.executescript((ROOT / "db" / "schema.sql").read_text())
    if fresh:
        seed = subprocess.run([sys.executable, str(ROOT / "db" / "seed_from_roadmap.py")],
                              capture_output=True, text=True, check=True).stdout
        with connect() as conn:
            conn.executescript(seed)


def task_row(r):
    return {k: r[k] for k in ("id", "group", "position", "title", "detail", "status", "done_at")}


def list_tasks():
    with connect() as conn:
        groups = conn.execute("SELECT slug, title FROM task_groups ORDER BY position").fetchall()
        rows = conn.execute(
            "SELECT t.id, g.slug AS 'group', t.position, t.title, t.detail, t.status, t.done_at "
            "FROM tasks t JOIN task_groups g ON g.id = t.group_id "
            "ORDER BY g.position, t.position, t.id").fetchall()
    return {"groups": [dict(g) for g in groups], "tasks": [task_row(r) for r in rows]}


# ── live events (WebSocket, server -> page) ──────────────────────────────
def ws_frame(opcode, payload=b""):
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([n])
    elif n < 65536:
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    return head + payload


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError
        buf += chunk
    return buf


def read_frame(sock):
    """Returns (opcode, payload). The page only ever sends ping/pong/close, so frames are tiny."""
    b0, b1 = read_exact(sock, 2)
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", read_exact(sock, 8))[0]
    if length > 65536:
        raise EOFError
    mask = read_exact(sock, 4) if b1 & 0x80 else b""
    payload = read_exact(sock, length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return b0 & 0x0F, payload


class Subscriber:
    def __init__(self, sock):
        self.sock, self.lock = sock, threading.Lock()

    def send(self, frame):
        try:
            with self.lock:
                self.sock.sendall(frame)
            return True
        except OSError:
            return False


SUBSCRIBERS = set()
SUBSCRIBERS_LOCK = threading.Lock()


def broadcast(event):
    frame = ws_frame(0x1, json.dumps(event).encode())
    with SUBSCRIBERS_LOCK:
        subs = list(SUBSCRIBERS)
    for sub in subs:
        if not sub.send(frame):
            with SUBSCRIBERS_LOCK:
                SUBSCRIBERS.discard(sub)


def get_state():
    with connect() as conn:
        favorites = [r[0] for r in conn.execute("SELECT model_ref FROM favorite_models ORDER BY position, added_at")]
        configs = [{"id": r["id"], "name": r["name"], "snapshot": json.loads(r["settings"])}
                   for r in conn.execute("SELECT id, name, settings FROM saved_configurations ORDER BY id")]
        prefs = {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM preferences")}
    default = prefs.pop("defaultModel", None)
    return {"version": STATE_VERSION, "favorites": favorites, "defaultModel": default, "configs": configs, "preferences": prefs,
            "empty": not (favorites or configs or default or prefs)}


def put_state(data):
    """Replace the saved state atomically. The page sends its whole state, as it did to local storage."""
    favorites = data.get("favorites", [])
    configs = data.get("configs", [])
    prefs = data.get("preferences", {})
    default = data.get("defaultModel")
    version = data.get("version", STATE_VERSION)
    if not isinstance(version, int) or version > STATE_VERSION:
        raise ValueError(f"state version {version!r} is newer than this server understands ({STATE_VERSION})")
    if not (isinstance(favorites, list) and all(isinstance(f, str) for f in favorites)
            and isinstance(configs, list) and isinstance(prefs, dict)
            and (default is None or isinstance(default, str))):
        raise ValueError("malformed state")
    for c in configs:
        if not (isinstance(c, dict) and isinstance(c.get("snapshot"), dict)):
            raise ValueError("each config needs a snapshot object")
    with connect() as conn:
        conn.execute("DELETE FROM favorite_models")
        conn.executemany("INSERT OR IGNORE INTO favorite_models (model_ref, position) VALUES (?, ?)",
                         [(f[:300], i) for i, f in enumerate(favorites)])
        conn.execute("DELETE FROM saved_configurations")
        for c in configs:
            snap = c["snapshot"]
            conn.execute("INSERT INTO saved_configurations (name, model_ref, engine, settings, snapshot_version) "
                         "VALUES (?,?,?,?,?)",
                         (str(c.get("name", ""))[:200], str(c.get("modelRef", ""))[:300],
                          str(snap.get("server", ""))[:40], json.dumps(snap),
                          snap.get("v") if isinstance(snap.get("v"), int) else 0))
        conn.execute("DELETE FROM preferences")
        items = dict(prefs)
        if default:
            items["defaultModel"] = default
        conn.executemany("INSERT INTO preferences (key, value) VALUES (?, ?)",
                         [(str(k)[:80], json.dumps(val)) for k, val in items.items()])


def saved_theme():
    """The theme saved in the state, if any. A browser that has never been here still opens in it."""
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = 'theme'").fetchone()
        value = json.loads(row[0]) if row else None
        return value if isinstance(value, str) and re.fullmatch(r"[a-z]{1,20}", value) else None
    except Exception:
        return None


def with_saved_theme(page):
    """Put the saved theme on <html> before the page is sent, so the first paint is already right."""
    theme = saved_theme()
    marker = b'<html lang="en">'
    if not theme or marker not in page:
        return page
    return page.replace(marker, b'<html lang="en" data-theme="' + theme.encode() + b'">', 1)


class Handler(BaseHTTPRequestHandler):
    server_version = "Modular"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    # ── helpers ──
    def send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        # Blocks DNS-rebinding: only answer requests addressed to localhost.
        return bool(LOCAL_HOSTS.match(self.headers.get("Host", "")))

    def body_json(self):
        if not (self.headers.get("Content-Type", "").split(";")[0] == "application/json"):
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY:
                return None
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    # ── live events ──
    def serve_events(self):
        key = self.headers.get("Sec-WebSocket-Key")
        origin = self.headers.get("Origin")
        if origin and not LOCAL_ORIGIN.match(origin):  # WebSockets ignore CORS, so check it here
            return self.send_json(403, {"error": "forbidden origin"})
        if (self.headers.get("Upgrade", "").lower() != "websocket" or not key
                or self.headers.get("Sec-WebSocket-Version") != "13"):
            return self.send_json(400, {"error": "expected a WebSocket upgrade"})
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        # Browsers expect HTTP/1.1 here; BaseHTTPRequestHandler would say HTTP/1.0.
        self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                          "Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())
        self.wfile.flush()
        sock = self.connection
        sub = Subscriber(sock)
        with SUBSCRIBERS_LOCK:
            SUBSCRIBERS.add(sub)
        sub.send(ws_frame(0x1, json.dumps({"event": "hello"}).encode()))
        try:
            while True:
                sock.settimeout(25)
                try:
                    first = sock.recv(1, socket.MSG_PEEK)
                except socket.timeout:
                    if not sub.send(ws_frame(0x9)):  # keep-alive ping
                        break
                    continue
                if not first:
                    break
                sock.settimeout(5)
                opcode, payload = read_frame(sock)
                if opcode == 0x8:
                    sub.send(ws_frame(0x8))
                    break
                if opcode == 0x9:
                    sub.send(ws_frame(0xA, payload))
        except (OSError, EOFError):
            pass
        finally:
            with SUBSCRIBERS_LOCK:
                SUBSCRIBERS.discard(sub)
            self.close_connection = True

    # ── static ──
    def do_GET(self):
        if not self.host_ok():
            return self.send_json(403, {"error": "forbidden host"})
        path = self.path.split("?", 1)[0]
        if path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if path == "/api/tasks":
            return self.send_json(200, list_tasks())
        if path == "/api/state":
            return self.send_json(200, get_state())
        if path == "/api/events":
            return self.serve_events()
        if path.startswith("/api/"):
            return self.send_json(404, {"error": "not found"})
        rel = pathlib.PurePosixPath("/" + path.lstrip("/")).relative_to("/")
        if not rel.parts:
            rel = pathlib.PurePosixPath("index.html")
        target = (ROOT / rel).resolve()
        if (ROOT not in target.parents or target.is_dir() or not target.exists()
                or rel.parts[0] in PRIVATE or any(p.startswith(".") for p in rel.parts)):
            self.send_response(404); self.end_headers(); return
        data = target.read_bytes()
        is_page = rel.parts == ("index.html",)
        if is_page:
            data = with_saved_theme(data)
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        if is_page:
            self.send_header("Cache-Control", "no-store")  # the page differs with the saved theme
        self.end_headers()
        self.wfile.write(data)

    # ── API writes ──
    def api_write(self, method):
        if not self.host_ok():
            return self.send_json(403, {"error": "forbidden host"})
        data = self.body_json() if method != "DELETE" else {}
        if data is None:
            return self.send_json(400, {"error": "expected a JSON object"})
        if self.path.split("?", 1)[0] == "/api/state":
            if method != "PUT":
                return self.send_json(405, {"error": "method not allowed"})
            try:
                put_state(data)
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})
            return self.send_json(200, get_state())
        m = re.fullmatch(r"/api/tasks(?:/(\d+))?", self.path.split("?", 1)[0])
        if not m:
            return self.send_json(404, {"error": "not found"})
        tid = int(m.group(1)) if m.group(1) else None
        with connect() as conn:
            if method == "POST" and tid is None:
                title = str(data.get("title", "")).strip()
                g = conn.execute("SELECT id FROM task_groups WHERE slug = ?", (data.get("group"),)).fetchone()
                if not title or not g:
                    return self.send_json(400, {"error": "title and a valid group are required"})
                pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM tasks WHERE group_id = ?", (g["id"],)).fetchone()[0]
                cur = conn.execute("INSERT INTO tasks (group_id, position, title, detail) VALUES (?,?,?,?)",
                                   (g["id"], pos, title[:200], str(data.get("detail", ""))[:2000]))
                tid = cur.lastrowid
                code = 201
            elif method == "PATCH" and tid is not None:
                sets, args = [], []
                if "status" in data:
                    if data["status"] not in STATUSES:
                        return self.send_json(400, {"error": "invalid status"})
                    sets.append("status = ?"); args.append(data["status"])
                for field, limit in (("title", 200), ("detail", 2000)):
                    if field in data:
                        value = str(data[field]).strip()
                        if field == "title" and not value:
                            return self.send_json(400, {"error": "title cannot be empty"})
                        sets.append(f"{field} = ?"); args.append(value[:limit])
                if not sets:
                    return self.send_json(400, {"error": "nothing to update"})
                cur = conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", (*args, tid))
                if cur.rowcount == 0:
                    return self.send_json(404, {"error": "no such task"})
                code = 200
            elif method == "DELETE" and tid is not None:
                deleted = conn.execute("DELETE FROM tasks WHERE id = ?", (tid,)).rowcount
                code = None
            else:
                return self.send_json(405, {"error": "method not allowed"})
            if code is not None:
                row = conn.execute(
                    "SELECT t.id, g.slug AS 'group', t.position, t.title, t.detail, t.status, t.done_at "
                    "FROM tasks t JOIN task_groups g ON g.id = t.group_id WHERE t.id = ?", (tid,)).fetchone()
        # The with-block above has committed; only now tell the pages.
        if code is None:
            if deleted:
                broadcast({"event": "task.deleted", "id": tid})
            return self.send_json(200 if deleted else 404, {"deleted": deleted})
        task = task_row(row)
        broadcast({"event": "task.created" if code == 201 else "task.updated", "task": task})
        self.send_json(code, task)

    def do_POST(self): self.api_write("POST")
    def do_PATCH(self): self.api_write("PATCH")
    def do_PUT(self): self.api_write("PUT")
    def do_DELETE(self): self.api_write("DELETE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8420)
    args = ap.parse_args()
    init_db()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        sys.exit(f"Cannot listen on 127.0.0.1:{args.port} ({e.strerror}). "
                 f"Something else is using it; try: python3 server.py --port {args.port + 1}")
    print(f"Modular on http://127.0.0.1:{args.port}  (db: {DB_PATH})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
