#!/usr/bin/env python3
"""Modular local server: serves the app and a small JSON API over SQLite.

    python3 server.py            # http://127.0.0.1:8000
    python3 server.py --port 9000

The database (db/modular.db) is created from db/schema.sql on first run and
seeded from ROADMAP.md. The server only listens on localhost.
"""
import argparse, json, mimetypes, pathlib, re, sqlite3, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
DB_PATH = ROOT / "db" / "modular.db"
STATUSES = ("todo", "doing", "blocked", "done")
PRIVATE = {"db", "archive"}  # never served as static files
LOCAL_HOSTS = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    fresh = not DB_PATH.exists()
    with connect() as conn:
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
            data = json.loads(self.rfile.read(min(length, 65536)) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    # ── static ──
    def do_GET(self):
        if not self.host_ok():
            return self.send_json(403, {"error": "forbidden host"})
        path = self.path.split("?", 1)[0]
        if path == "/api/tasks":
            return self.send_json(200, list_tasks())
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
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── API writes ──
    def api_write(self, method):
        if not self.host_ok():
            return self.send_json(403, {"error": "forbidden host"})
        data = self.body_json() if method != "DELETE" else {}
        if data is None:
            return self.send_json(400, {"error": "expected a JSON object"})
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
                cur = conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
                return self.send_json(200 if cur.rowcount else 404, {"deleted": cur.rowcount})
            else:
                return self.send_json(405, {"error": "method not allowed"})
            row = conn.execute(
                "SELECT t.id, g.slug AS 'group', t.position, t.title, t.detail, t.status, t.done_at "
                "FROM tasks t JOIN task_groups g ON g.id = t.group_id WHERE t.id = ?", (tid,)).fetchone()
        self.send_json(code, task_row(row))

    def do_POST(self): self.api_write("POST")
    def do_PATCH(self): self.api_write("PATCH")
    def do_DELETE(self): self.api_write("DELETE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    init_db()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Modular on http://127.0.0.1:{args.port}  (db: {DB_PATH.relative_to(ROOT)})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
