"""What the vLLM recipes say a model needs in order to start: read from github.com/vllm-project/recipes.

Each recipe is a YAML file with the minimum vLLM version, whether the nightly build is required, the arguments and
environment every launch needs, and the packages to install first. Used by tools/facts.py. A recipe that cannot be
read is skipped, never guessed at. Standard library only.
"""
import concurrent.futures as cf, json, sys, pathlib, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import miniyaml  # noqa: E402

REPO = "vllm-project/recipes"
_INDEX = {}


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "modular-recipes"}), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def index():
    """{ lowercase model id: (path, parsed recipe) } for every recipe that can be read."""
    if _INDEX:
        return _INDEX
    tree = json.loads(_get(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"))["tree"]
    paths = [t["path"] for t in tree if t["path"].startswith("models/") and t["path"].endswith(".yaml")]

    def one(path):
        try:
            return path, miniyaml.load(_get(f"https://raw.githubusercontent.com/{REPO}/main/{path}"))
        except Exception:
            return path, None

    with cf.ThreadPoolExecutor(12) as pool:
        for path, doc in pool.map(one, paths):
            model = doc.get("model") if isinstance(doc, dict) else None
            if not isinstance(model, dict):
                continue
            ids = [model.get("model_id")] + [v.get("model_id") for v in (doc.get("variants") or {}).values() if isinstance(v, dict)]
            for i in ids:
                if isinstance(i, str):
                    _INDEX.setdefault(i.lower(), (path, doc))
    return _INDEX


def for_model(ref):
    """The compact requirements of one model, or None when it has no recipe."""
    hit = index().get(ref.lower())
    if not hit:
        return None
    path, doc = hit
    m = doc["model"]
    image = m.get("docker_image")
    image = image.get("nvidia") if isinstance(image, dict) else image
    install = m.get("install") if isinstance(m.get("install"), dict) else {}
    deps = []
    for d in doc.get("dependencies") if isinstance(doc.get("dependencies"), list) else []:
        if isinstance(d, dict) and (d.get("command") or d.get("note")):
            deps.append({k: d[k] for k in ("note", "command") if d.get(k)})
    version = m.get("min_vllm_version")
    out = {
        "source": f"https://github.com/{REPO}/blob/main/{path}",
        "minVllm": str(version) if version is not None else None,
        "nightly": bool(m.get("nightly_required")) or version == "nightly",
        "pip": False if install.get("pip") is False else None,
        "image": image if isinstance(image, str) else None,
        "args": [str(a) for a in (m.get("base_args") or [])],
        "env": {str(k): str(v) for k, v in (m.get("base_env") or {}).items()} if isinstance(m.get("base_env"), dict) else {},
        "deps": deps,
    }
    # empty things are left out; a false is kept only where it says something ("pip": false = PyPI is not supported)
    return {k: v for k, v in out.items() if v not in (None, [], {}) and (v is not False or k == "pip")}
