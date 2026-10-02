"""The models desk: runs the Hugging Face scan and writes down what a person should look at.

It never edits catalog/curation.json or the model list: choosing models is a person's decision.
"""
import json, os, subprocess, sys

MIN_DOWNLOADS = 20000


def catalog(root):
    """The models in the page's catalog, as {ref: retired}."""
    out = subprocess.run(["node", "tools/catalog.mjs"], cwd=root, capture_output=True, text=True, check=True, timeout=60).stdout
    return {m["ref"]: m["retired"] for m in json.loads(out)}


def notable(scan, seen, retired=()):
    """Things in a scan worth a person's time that we have not already pointed out, or already acted on."""
    found = []
    for c in scan.get("curated", []):
        key = f"{c['id']}={c.get('suggested')}"
        if c["id"] in retired:  # the catalog already retired it: a suggestion to retire it is not news
            continue
        if c.get("suggested") in ("retired", "hot") and key not in seen:
            found.append((key, f"{c['id']}: {c['suggested']}" + (f" ({'; '.join(c.get('reasons', []))})" if c.get("reasons") else "")))
    for lab, info in scan.get("labs", {}).items():
        for m in info.get("new", []):
            key = f"new={m['id']}"
            if key not in seen and m.get("downloads", 0) >= MIN_DOWNLOADS:
                found.append((key, f"new from {lab}: {m['id']} ({m['downloads']:,} downloads in 30 days, released {m['created']})"))
    return found


def run(lib, scan_fn=None):
    """Scan, then file one inbox note for whatever is new. The first scan only learns what already exists."""
    state = lib.state()
    seen = set(state["models"].get("seen", []))
    first = not state["models"]
    out = lib.var / "stage" / "scan.json"
    if scan_fn:
        scan = scan_fn()
    else:
        subprocess.run([sys.executable, "tools/scan.py", "--quiet", "--out", str(out)], cwd=lib.root, check=True, timeout=1800)
        scan = json.loads(out.read_text())
    cat = catalog(lib.root)
    found = notable(scan, seen, {r for r, gone in cat.items() if gone})
    if first:  # an empty memory would report the whole world: remember it, report only the catalog's own status
        found_now = [f for f in found if not f[0].startswith("new=")]
        seen |= {k for k, _ in found if k.startswith("new=")}
    else:
        found_now = found
    item = None
    if found_now:
        item = lib.hold("models", "models", None, f"models: {len(found_now)} thing(s) to look at", problems=[t for _, t in found_now])
    seen |= {k for k, _ in found_now}
    state["models"] = {"seen": sorted(seen), "ran": os.environ.get("LIBRARIAN_NOW", "") or __import__("datetime").datetime.now().isoformat(timespec="seconds")}
    lib.save_state(state)
    lib.note(kind="scanned", found=len(found_now), item=item["id"] if item else None)
    return item
