"""Prints SQL that seeds task_groups and tasks from ROADMAP.md.
Run: python3 db/seed_from_roadmap.py | sqlite3 db/modular.db
"""
import pathlib, re

lines = (pathlib.Path(__file__).parent.parent / "ROADMAP.md").read_text().splitlines()
q = lambda s: "'" + s.replace("'", "''") + "'"
group = None
print("BEGIN;")
gpos = 0
for line in lines:
    if line.startswith("### "):
        title = line[4:].strip()
        gpos += 1
        group = title.lower()
        print(f"INSERT OR IGNORE INTO task_groups (slug, title, position) VALUES ({q(group)}, {q(title)}, {gpos});")
        tpos = 0
    m = re.match(r"- \[( |x)\] \*\*\d+\. (.+?)\*\* ?(.*)", line)
    if m and group:
        tpos += 1
        status = "done" if m.group(1) == "x" else "todo"
        print(f"INSERT INTO tasks (group_id, position, title, detail, status) "
              f"SELECT id, {tpos}, {q(m.group(2).rstrip('.'))}, {q(m.group(3))}, {q(status)} "
              f"FROM task_groups WHERE slug = {q(group)};")
print("COMMIT;")
