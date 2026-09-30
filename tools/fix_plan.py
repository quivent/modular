#!/usr/bin/env python3
"""Writes @fix_plan.md from the tracker database, so the loop's task list always matches the tracker.

    python3 tools/fix_plan.py

Edit tasks in the tracker (or through /api/tasks), then run this again. Standard library only.
"""
import pathlib, sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARK = {"todo": " ", "doing": "~", "done": "x", "blocked": "!"}


def main():
    db = sqlite3.connect(ROOT / "db" / "modular.db")
    db.row_factory = sqlite3.Row
    deps, blocks = {}, {}
    for r in db.execute("SELECT task_id, depends_on_id FROM task_dependencies ORDER BY task_id, depends_on_id"):
        deps.setdefault(r["task_id"], []).append(r["depends_on_id"])
        blocks.setdefault(r["depends_on_id"], []).append(r["task_id"])
    status = {r["id"]: r["status"] for r in db.execute("SELECT id, status FROM tasks")}
    out = ["# Fix plan", "",
           "Generated from the tracker by `python3 tools/fix_plan.py`. Do not edit here: change the task in the tracker.",
           "Legend: `[ ]` todo, `[~]` doing, `[x]` done, `[!]` blocked. A task is ready when it is `[ ]` and everything it depends on is `[x]`.", ""]
    for g in db.execute("SELECT id, title FROM task_groups ORDER BY position"):
        out += [f"## {g['title']}", ""]
        for t in db.execute("SELECT * FROM tasks WHERE group_id = ? ORDER BY position, id", (g["id"],)):
            out.append(f"- [{MARK[t['status']]}] **#{t['id']} {t['title']}**")
            if t["detail"]:
                out.append(f"  {t['detail']}")
            if deps.get(t["id"]):
                open_deps = [d for d in deps[t["id"]] if status[d] != "done"]
                shown = ", ".join(f"#{d}" for d in deps[t["id"]]) if len(deps[t["id"]]) <= 6 else f"#{min(deps[t['id']])} to #{max(deps[t['id']])} (all)"
                out.append(f"  Depends on: {shown}" + (f"  (waiting on {len(open_deps)})" if open_deps and t["status"] == "todo" else ""))
            if blocks.get(t["id"]) and len(blocks[t["id"]]) <= 6:
                out.append("  Blocks: " + ", ".join(f"#{b}" for b in blocks[t["id"]]))
        out.append("")
    ready = [t for t in db.execute("SELECT t.id, t.title FROM tasks t JOIN task_groups g ON g.id = t.group_id WHERE t.status = 'todo' ORDER BY g.position, t.position, t.id")
             if all(status[d] == "done" for d in deps.get(t["id"], []))]
    out += ["## Ready now (highest priority first)", ""] + [f"1. #{t['id']} {t['title']}" for t in ready] + [""]
    (ROOT / "@fix_plan.md").write_text("\n".join(out))
    print(f"@fix_plan.md: {len(status)} tasks, {len(ready)} ready")


if __name__ == "__main__":
    main()
