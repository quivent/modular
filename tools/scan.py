#!/usr/bin/env python3
"""Scans Hugging Face for what is new, what is hot, and what has aged out of the catalog.

    python3 tools/scan.py               # scan, write catalog/scan-latest.json, print a summary
    python3 tools/scan.py --shapes 40   # also read config.json for the 40 most-downloaded new models
    python3 tools/scan.py --quiet       # write the file only

It only reads public data and only suggests: catalog/curation.json (the human decisions) is never
edited by this script. Standard library only. Configure with catalog/watch.json.

Suggested statuses, from the numbers in the output:
  hot      the model is on Hugging Face's trending list (with real download volume)
  retired  a newer release from the same lab, in the same task and size band, is out-downloading it
           and the model is older than supersede.min_age_months
  aging    it has a newer sibling, or is older than min_age_months, but is not clearly replaced
  current  none of the above
"""
import argparse, datetime as dt, json, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://huggingface.co/api/models"
EXPAND = ["downloads", "likes", "trendingScore", "createdAt", "lastModified", "pipeline_tag", "safetensors", "gated"]
# Quantized, converted, or adapter repos are variants of a base model, not releases in their own right.
DERIVATIVE = re.compile(
    r"(gguf|awq|gptq|fp8|fp4|nvfp4|int4|int8|bnb|mlx|4bit|8bit|[-_]q\d|eetq|quantized|eagle|draft|lora|onnx|w4a16|w8a8|compressed|mxfp)",
    re.I,
)
TEXTUAL = {"text-generation", "image-text-to-text", "any-to-any", "text2text-generation", None}


def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "modular-catalog-scan"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt < tries - 1:
                time.sleep(2)
                continue
            return None


def listing(**params):
    q = urllib.parse.urlencode([(k, v) for k, v in params.items()] + [("expand[]", e) for e in EXPAND])
    return get(f"{API}?{q}") or []


def when(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def slim(m):
    st = m.get("safetensors") or {}
    return {
        "id": m["id"],
        "author": m["id"].split("/")[0],
        "downloads": m.get("downloads") or 0,
        "likes": m.get("likes") or 0,
        "trending": m.get("trendingScore") or 0,
        "created": (m.get("createdAt") or "")[:10],
        "task": m.get("pipeline_tag"),
        "params_b": round(st["total"] / 1e9, 2) if st.get("total") else None,
        "gated": bool(m.get("gated")),
    }


def shape_of(ref):
    """Architecture numbers the memory estimate needs, from config.json. None for gated or unreadable repos."""
    cfg = get(f"https://huggingface.co/{ref}/raw/main/config.json")
    if not cfg:
        return None
    t = cfg.get("text_config", cfg)
    heads, hidden = t.get("num_attention_heads"), t.get("hidden_size")
    kind = "standard"
    if t.get("kv_lora_rank"):
        kind = "mla"  # compressed KV cache: the simple formula overstates it
    layer_types = t.get("layer_types") or []
    if any(x not in ("full_attention", "sliding_attention") for x in layer_types):
        kind = "hybrid"  # linear-attention or state-space layers: the simple formula does not apply
    elif "sliding_attention" in layer_types or t.get("sliding_window_pattern"):
        kind = "sliding"  # mixed local/global attention: the simple formula is an upper bound
    return {
        "layers": t.get("num_hidden_layers"),
        "heads": heads,
        "kv_heads": t.get("num_key_value_heads") or heads,
        "head_dim": t.get("head_dim") or (hidden // heads if hidden and heads else None),
        "max_position": t.get("max_position_embeddings"),
        "kv_kind": kind,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shapes", type=int, default=20, help="read config.json for this many top new models")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    watch = json.loads((ROOT / "catalog" / "watch.json").read_text())
    curation = json.loads((ROOT / "catalog" / "curation.json").read_text())["models"]
    now = dt.datetime.now(dt.timezone.utc)
    window = dt.timedelta(days=watch["window_days"])
    say = (lambda *a: None) if args.quiet else print

    # ── 1. what each watched lab released recently, and how popular its models are ──
    labs, pool = {}, {}
    for author in watch["authors"]:
        recent = [slim(m) for m in listing(author=author, sort="createdAt", direction=-1, limit=100)]
        top = [slim(m) for m in listing(author=author, sort="downloads", direction=-1, limit=100)]
        base = lambda xs: [m for m in xs if not DERIVATIVE.search(m["id"].split("/")[1])]
        new = [m for m in base(recent) if now - when(m["created"] + "T00:00:00+00:00") <= window]
        new.sort(key=lambda m: -m["downloads"])
        labs[author] = {"found": len(recent) + len(top) > 0, "new": new[:12], "top_downloads": base(top)[:10]}
        for m in base(recent) + base(top):
            pool[m["id"]] = m
        say(f"  {author:<18} {len(new):>3} new in {watch['window_days']}d" + ("" if labs[author]["found"] else "   (no models found: check the name)"))

    # ── 2. what is trending, kept honest by download and size floors ──
    t = watch["trending"]
    trending, seen = [], set()
    for m in map(slim, listing(sort="trendingScore", direction=-1, limit=100)):
        if m["id"] in seen or DERIVATIVE.search(m["id"].split("/")[1]):
            continue
        seen.add(m["id"])
        if m["downloads"] < t["min_downloads_30d"] or (m["params_b"] or 0) < t["min_params_billions"]:
            continue
        m["official"] = m["author"] in watch["authors"]
        trending.append(m)
    trending = trending[: t["limit"]]
    trending_ids = {m["id"]: i + 1 for i, m in enumerate(trending)}

    # ── 3. how each curated model is holding up ──
    s = watch["supersede"]
    curated = []
    for ref in curation:
        info = get(f"{API}/{ref}?" + urllib.parse.urlencode([("expand[]", e) for e in EXPAND]))
        if not info:
            curated.append({"id": ref, "exists": False, "suggested": "retired", "reasons": ["not found on Hugging Face"]})
            continue
        me = slim(info)
        born = when(me["created"] + "T00:00:00+00:00")
        age_months = round((now - born).days / 30.4, 1)
        lo, hi = s["size_band"]
        successors = sorted(
            (
                m
                for m in pool.values()
                if m["author"] == me["author"]
                and m["id"] != ref
                and m["created"] > me["created"]
                and m["task"] == me["task"]
                and m["downloads"] >= s["min_download_ratio"] * me["downloads"]
                and (not me["params_b"] or not m["params_b"] or lo <= m["params_b"] / me["params_b"] <= hi)
            ),
            key=lambda m: -m["downloads"],
        )[:3]
        reasons, status = [], "current"
        if ref in trending_ids:
            status, reasons = "hot", [f"#{trending_ids[ref]} on the trending list"]
        else:
            if successors and age_months >= s["min_age_months"] and successors[0]["downloads"] > me["downloads"]:
                status = "retired"
                reasons.append(f"{successors[0]['id']} (released {successors[0]['created']}) has more downloads")
            elif successors or age_months >= s["min_age_months"]:
                status = "aging"
                reasons.append(
                    f"{len(successors)} newer sibling(s) from {me['author']}" if successors else f"released {age_months} months ago"
                )
        curated.append({**me, "exists": True, "age_months": age_months, "suggested": status, "reasons": reasons,
                        "successors": [{k: m[k] for k in ("id", "created", "downloads", "params_b")} for m in successors]})

    # ── 4. architecture numbers for the most-downloaded new models, to extend the memory estimate ──
    cands = sorted((m for lab in labs.values() for m in lab["new"] if m["task"] in TEXTUAL and not m["gated"]),
                   key=lambda m: -m["downloads"])[: args.shapes]
    shapes = {m["id"]: shape_of(m["id"]) for m in cands}

    out = {"scanned_at": now.isoformat(timespec="seconds"), "labs": labs, "trending": trending,
           "curated": curated, "shapes": {k: v for k, v in shapes.items() if v}}
    (ROOT / "catalog" / "scan-latest.json").write_text(json.dumps(out, indent=1) + "\n")

    if not args.quiet:
        print("\n== curated models (suggested status) ==")
        for c in curated:
            note = "; ".join(c["reasons"]) or "no newer sibling, not old"
            print(f"  {c['suggested']:<8} {c['id']:<44} {note}")
        print("\n== trending, from watched labs ==")
        for m in [m for m in trending if m["official"]][:12]:
            print(f"  {m['id']:<44} trend {m['trending']:<5} dl30d {m['downloads']:>10,}  {m['created']}")
        print("\n== trending, other authors (worth a look, not trusted by default) ==")
        for m in [m for m in trending if not m["official"]][:8]:
            print(f"  {m['id']:<44} trend {m['trending']:<5} dl30d {m['downloads']:>10,}  {m['created']}")
        print(f"\nwrote catalog/scan-latest.json  ({len(shapes)} architecture shapes read)")


if __name__ == "__main__":
    sys.exit(main())
