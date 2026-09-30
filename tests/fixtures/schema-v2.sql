-- Modular state schema (SQLite). Run: sqlite3 db/modular.db < db/schema.sql
-- Timestamps are ISO-8601 UTC text. Ids are integers; slugs are stable keys.

PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;          -- bump with each migration (see migrate() in server.py)

-- ── Tracker ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_groups (
  id        INTEGER PRIMARY KEY,
  slug      TEXT NOT NULL UNIQUE,        -- 'foundation', 'trust', ...
  title     TEXT NOT NULL,
  position  INTEGER NOT NULL DEFAULT 0   -- display order
);

CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY,
  group_id    INTEGER NOT NULL REFERENCES task_groups(id) ON DELETE RESTRICT,
  position    INTEGER NOT NULL DEFAULT 0,  -- order within the group
  title       TEXT NOT NULL,
  detail      TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'todo'
              CHECK (status IN ('todo','doing','blocked','done')),
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  done_at     TEXT                         -- set when status becomes 'done'
);
CREATE INDEX IF NOT EXISTS tasks_by_group  ON tasks(group_id, position);
CREATE INDEX IF NOT EXISTS tasks_by_status ON tasks(status);

-- A task can wait on another (roadmap items are ordered by dependency).
CREATE TABLE IF NOT EXISTS task_dependencies (
  task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, depends_on_id),
  CHECK (task_id <> depends_on_id)
);

-- Append-only history of status changes, kept automatically by triggers.
CREATE TABLE IF NOT EXISTS task_events (
  id         INTEGER PRIMARY KEY,
  task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  from_status TEXT,
  to_status   TEXT NOT NULL,
  at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TRIGGER IF NOT EXISTS tasks_touch
AFTER UPDATE OF title, detail, status, group_id, position ON tasks
BEGIN
  UPDATE tasks
     SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
         done_at    = CASE WHEN NEW.status = 'done'
                           THEN COALESCE(OLD.done_at, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                           ELSE NULL END
   WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tasks_done_on_insert
AFTER INSERT ON tasks
WHEN NEW.status = 'done' AND NEW.done_at IS NULL
BEGIN
  UPDATE tasks SET done_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tasks_log_insert
AFTER INSERT ON tasks
BEGIN
  INSERT INTO task_events (task_id, from_status, to_status) VALUES (NEW.id, NULL, NEW.status);
END;

CREATE TRIGGER IF NOT EXISTS tasks_log_status
AFTER UPDATE OF status ON tasks
WHEN OLD.status <> NEW.status
BEGIN
  INSERT INTO task_events (task_id, from_status, to_status) VALUES (NEW.id, OLD.status, NEW.status);
END;

-- ── Preserved app state ───────────────────────────────────────────────
-- Replaces the browser's local storage: saved setups, favorites, default model.
CREATE TABLE IF NOT EXISTS saved_configurations (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL DEFAULT '',
  model_ref  TEXT NOT NULL,               -- e.g. 'Qwen/Qwen3-8B'
  engine     TEXT NOT NULL,               -- 'vllm', 'sglang', ...
  settings   TEXT NOT NULL CHECK (json_valid(settings)),  -- the full configuration
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Favorites are kept by model reference so they survive catalog reordering.
CREATE TABLE IF NOT EXISTS favorite_models (
  model_ref  TEXT PRIMARY KEY,
  position   INTEGER NOT NULL DEFAULT 0,
  added_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Small key/value preferences: defaultModel (a model ref), hfNamespace, ...
CREATE TABLE IF NOT EXISTS preferences (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL CHECK (json_valid(value))
);
