"""Which model architectures each engine can run, read from the engine's own source.

Used by tools/flags.py (it stores the list beside each engine's flags) and checked by the page: a model whose
architecture the engine does not list is likely to fail at startup with "model architecture not supported".
Standard library only.
"""
import json, re, urllib.request

UA = {"User-Agent": "modular-support"}
SEEN = []  # the single files a list was read from, so the librarian can watch them (not the many a loop reads)


def raw(url, track=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        body = r.read().decode("utf-8", "replace")
    if track and url not in SEEN:
        SEEN.append(url)
    return body


def tree(repo, path):
    """File names in a GitHub folder (the public API, no login)."""
    with urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{repo}/contents/{path}", headers=UA), timeout=60) as r:
        return [x["name"] for x in json.load(r) if x["type"] == "file"]


def vllm():
    """vLLM's registry: HF architecture class name -> implementation. The Transformers fallback is not counted here."""
    src = raw("https://raw.githubusercontent.com/vllm-project/vllm/main/vllm/model_executor/models/registry.py", track=True)
    return sorted(set(re.findall(r'^\s*"([A-Za-z0-9_]+)":\s*\(', src, re.M)))


def llama():
    """llama.cpp's converters each register the HF architectures they handle."""
    archs = set()
    for name in tree("ggml-org/llama.cpp", "conversion"):
        if not name.endswith(".py") or name in ("__init__.py", "base.py"):
            continue
        src = raw(f"https://raw.githubusercontent.com/ggml-org/llama.cpp/master/conversion/{name}")
        for call in re.findall(r"@ModelBase\.register\(([^)]*)\)", src):
            archs.update(re.findall(r'"([A-Za-z0-9_]+)"', call))
    return sorted(archs)


def trtllm():
    src = raw("https://raw.githubusercontent.com/NVIDIA/TensorRT-LLM/main/docs/source/models/supported-models.md", track=True)
    return sorted(set(re.findall(r"`([A-Za-z0-9_]+(?:ForCausalLM|ForConditionalGeneration|ForSequenceClassification|Model|LMHeadModel))`", src))
                  | set(re.findall(r"\|\s*([A-Z][A-Za-z0-9_]+(?:ForCausalLM|ForConditionalGeneration|Model|LMHeadModel))\s*\|", src)))


def stems(repo, path):
    """Engines that keep one module per model: the module names are the model types."""
    return sorted(n[:-3] for n in tree(repo, path) if n.endswith(".py") and not n.startswith("_") and n not in ("utils.py",))


def mlx():
    """mlx-lm loads the module named by a config's model_type, after its own remapping of a few types."""
    names = set(stems("ml-explore/mlx-lm", "mlx_lm/models"))
    utils = raw("https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/utils.py", track=True)
    block = re.search(r"MODEL_REMAPPING\s*=\s*\{(.*?)\n\}", utils, re.S)
    if block:
        names.update(re.findall(r'"([A-Za-z0-9_\-]+)":', block.group(1)))
    return sorted(names)


def sglang():
    """Each SGLang module declares the architecture classes it serves in `EntryClass`."""
    import concurrent.futures as cf
    files = [n for n in tree("sgl-project/sglang", "python/sglang/srt/models") if n.endswith(".py") and not n.startswith("_")]

    def entry(name):
        try:
            src = raw(f"https://raw.githubusercontent.com/sgl-project/sglang/main/python/sglang/srt/models/{name}")
        except Exception:
            return set()
        found = set()
        for m in re.finditer(r"^EntryClass\s*=\s*(\[[^\]]*\]|[A-Za-z0-9_]+)", src, re.M):
            found.update(re.findall(r"[A-Za-z][A-Za-z0-9_]*", m.group(1)))
        return found
    with cf.ThreadPoolExecutor(12) as pool:
        out = set().union(*pool.map(entry, files))
    return sorted(out)


def tgi():
    """TGI lists model families by name."""
    src = raw("https://raw.githubusercontent.com/huggingface/text-generation-inference/main/docs/source/supported_models.md", track=True)
    return sorted(set(re.findall(r"^- \[([^\]]+)\]", src, re.M)))


# What each engine's list is made of, so the page knows how to compare.
#   arch  exact architecture class names      type  module or family names matched against the model type
SOURCES = {"vllm": ("arch", vllm), "llama": ("arch", llama), "trtllm": ("arch", trtllm),
           "mlx": ("type", mlx), "sglang": ("arch", sglang), "tgi": ("type", tgi)}


def read(engine):
    """{ "by": "arch" | "type", "names": [...] } or None when the engine has no list we read."""
    if engine not in SOURCES:
        return None
    by, fn = SOURCES[engine]
    return {"by": by, "names": fn()}
