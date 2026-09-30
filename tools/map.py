#!/usr/bin/env python3
"""Prints a map of the named regions in index.html, computed from its markers.

    python3 tools/map.py                 # every region: name, first line, last line, size
    python3 tools/map.py checks          # print the lines of the region(s) whose name contains 'checks'
    python3 tools/map.py --check         # exit 1 if markers are malformed (duplicate names, etc.)

A region starts at a marker line containing "▸ <name>" (in /* */ or <!-- --> comments)
and ends at the line before the next marker, or at the end of the file. Because the map is
computed from the file each time, it cannot go stale.
"""
import pathlib, re, sys

FILE = pathlib.Path(__file__).resolve().parent.parent / "index.html"
MARK = re.compile(r"(?:/\*|<!--)\s*▸\s*(.+?)\s*(?:\*/|-->)\s*$")


def regions(lines):
    marks = [(i, m.group(1)) for i, l in enumerate(lines, 1) if (m := MARK.search(l))]
    out = []
    for k, (start, name) in enumerate(marks):
        end = marks[k + 1][0] - 1 if k + 1 < len(marks) else len(lines)
        out.append((name, start, end))
    return out


def main():
    lines = FILE.read_text().splitlines()
    regs = regions(lines)
    args = sys.argv[1:]
    if args == ["--check"]:
        names = [n for n, _, _ in regs]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes or not regs:
            print("duplicate or missing markers:", dupes or "none found")
            sys.exit(1)
        print(f"ok: {len(regs)} regions")
        return
    if args:
        hits = [r for r in regs if args[0].lower() in r[0].lower()]
        if not hits:
            sys.exit(f"no region matching {args[0]!r}")
        for name, a, b in hits:
            print(f"── {name}  [{a}–{b}]")
            for n in range(a, b + 1):
                print(f"{n:>5}  {lines[n - 1]}")
        return
    width = max(len(n) for n, _, _ in regs)
    for name, a, b in regs:
        print(f"{name:<{width}}  {a:>5}–{b:<5}  {b - a + 1:>4} lines")


if __name__ == "__main__":
    main()
