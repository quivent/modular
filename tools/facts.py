#!/usr/bin/env python3
"""Reads what decides whether a model starts: from each model's own config.json on Hugging Face.

    python3 tools/facts.py                 # every model in the catalog
    python3 tools/facts.py Qwen/Qwen3.8-27B

Writes catalog/facts.json: { ref: { billions, gib, heads, kvHeads, maxCtx, arch, type, custom, quant, kv, fetched } }

  maxCtx   the longest context the model supports (a longer one is refused at startup)
  kv       what one token costs in cache, by attention design, or null when the design is not one we can
           count honestly (a wrong number is worse than none). Shapes:
             full  [layers, kvHeads, headDim]            every token, two tensors (K and V)
             slide [layers, kvHeads, headDim, window]    only the last `window` tokens
             mla   [layers, dim]                         one compressed vector per token
           layers that keep a fixed-size state (linear attention, Mamba) cost nothing per token and are left out
  custom   the repository ships its own modelling code (it needs --trust-remote-code unless the engine has the model natively)
  quant    the quantization the checkpoint was published in, if any

A gated repository's config is only readable with a Hugging Face token (HF_TOKEN). Without one, what is already
known stays, and nothing is invented. Standard library only.
"""
import datetime as dt, json, os, pathlib, re, subprocess, sys, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "catalog" / "facts.json"
WEIGHT = re.compile(r"\.(safetensors)$")


def get(url, token=None):
    headers = {"User-Agent": "modular-facts"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as r:
        return json.load(r)


def kv_descriptor(c):
    """What a token costs in cache for this config, or None when the design is not one we count."""
    t = c.get("text_config") or c
    layers = t.get("num_hidden_layers")
    heads = t.get("num_attention_heads")
    kv_heads = t.get("num_key_value_heads") or heads
    dim = t.get("head_dim") or (t["hidden_size"] // heads if t.get("hidden_size") and heads else None)
    types = t.get("layer_types")
    if t.get("compress_ratios"):  # DeepSeek V4's compressed caches: the scheme is not one we can count
        return None
    # compressed-latent attention (MLA, and DeepSeek's sparse variant of it)
    if t.get("kv_lora_rank"):
        width = t["kv_lora_rank"] + (t.get("qk_rope_head_dim") or 0)
        lin = t.get("linear_attn_config") or {}
        if lin.get("full_attn_layers"):  # a hybrid: only these layers keep a per-token cache
            return {"mla": [len(lin["full_attn_layers"]), width]}
        if types:
            n = sum(1 for x in types if x not in ("linear_attention", "mamba"))
            return {"mla": [n, width]}
        return {"mla": [layers, width]}
    if t.get("layers_block_type") and kv_heads and dim:  # Mamba hybrids list a block type for every layer
        n = sum(1 for x in t["layers_block_type"] if x == "attention")
        return {"full": [n, kv_heads, dim]} if n else None
    if not (layers and kv_heads and dim):
        return None
    out = {}
    if types:
        full = sum(1 for x in types if x == "full_attention")
        slide = sum(1 for x in types if x == "sliding_attention")
        if full + slide + sum(1 for x in types if x == "linear_attention") != len(types):
            return None  # a layer kind we do not know
        if full:
            g_heads = t.get("num_global_key_value_heads") or kv_heads
            g_dim = t.get("global_head_dim") or dim
            out["full"] = [full, g_heads, g_dim]
        if slide:
            if not t.get("sliding_window"):
                return None
            out["slide"] = [slide, kv_heads, dim, t["sliding_window"]]
        return out or None
    if t.get("sliding_window") and t.get("use_sliding_window"):
        return {"slide": [layers, kv_heads, dim, t["sliding_window"]]}
    return {"full": [layers, kv_heads, dim]}


def from_config(c):
    t = c.get("text_config") or c
    return {
        "heads": t.get("num_attention_heads"),
        "kvHeads": t.get("num_key_value_heads") or t.get("num_attention_heads"),
        "maxCtx": t.get("max_position_embeddings") or c.get("max_position_embeddings"),
        "kv": kv_descriptor(c),
    }


def read(ref, token=None):
    """Facts for one repository, from the API (always) and its config.json (when readable)."""
    info = get(f"https://huggingface.co/api/models/{ref}?blobs=true&expand[]=config&expand[]=safetensors&expand[]=gated", token)
    cfg = info.get("config") or {}
    facts = {"arch": cfg.get("architectures") or [], "type": cfg.get("model_type")}
    if cfg.get("quantization_config"):
        facts["quant"] = cfg["quantization_config"].get("quant_method") or "quantized"
    st = info.get("safetensors") or {}
    if st.get("total"):
        facts["billions"] = round(st["total"] / 1e9, 2)
    sizes = [s.get("size") or 0 for s in info.get("siblings", [])
             if "/" not in s["rfilename"] and WEIGHT.search(s["rfilename"]) and not s["rfilename"].startswith("consolidated")]
    if sizes:
        facts["gib"] = round(sum(sizes) / 1073741824, 1)
    try:
        c = get(f"https://huggingface.co/{ref}/raw/main/config.json", token)
        facts.update({k: v for k, v in from_config(c).items() if v is not None})
        facts["custom"] = bool(c.get("auto_map"))
        if c.get("quantization_config") and "quant" not in facts:
            facts["quant"] = c["quantization_config"].get("quant_method") or "quantized"
    except urllib.error.HTTPError as e:
        facts["unreadable"] = e.code  # gated: needs a token
    return facts


def catalog():
    out = subprocess.run(["node", str(ROOT / "tools" / "catalog.mjs")], capture_output=True, text=True, check=True).stdout
    return [m for m in json.loads(out) if m["kind"] in ("language", "retrieval", "audio")]


def main():
    token = os.environ.get("HF_TOKEN")
    refs = sys.argv[1:] or [m["ref"] for m in catalog()]
    known = json.loads(OUT.read_text()) if OUT.exists() else {}
    for ref in refs:
        try:
            new = read(ref, token)
        except Exception as e:
            print(f"{ref:<55} could not read: {str(e)[:60]}")
            continue
        old = known.get(ref, {})
        merged = {**old, **new}
        if "unreadable" not in new:
            merged.pop("unreadable", None)
        merged["fetched"] = dt.date.today().isoformat()
        known[ref] = merged
        kv = merged.get("kv")
        print(f"{ref:<55} ctx {str(merged.get('maxCtx') or '?'):>8}  kv {json.dumps(kv) if kv else ('-' if 'unreadable' not in merged else 'needs HF_TOKEN')}")
    OUT.write_text(json.dumps(dict(sorted(known.items())), indent=1) + "\n")


if __name__ == "__main__":
    main()
