#!/usr/bin/env python3
"""Extracts EVERY flag of each serving engine from the engine's own documentation.

    python3 tools/flags.py              # all engines
    python3 tools/flags.py vllm         # one engine

Writes catalog/flags/<engine>.json: { engine, source, fetched, sections: [ { title, flags: [ {
name, aliases, negation, choices, default, help } ] } ] }. Nothing is filtered or summarized: the page
shows all of it. Standard library only.
"""
import datetime as dt, html, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "catalog" / "flags"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "modular-flag-extractor"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def clean(title):
    return title.replace("\u200b", "").replace("¶", "").strip()


def write(engine, source, sections, extra=None):
    for s in sections:
        s["title"] = clean(s["title"])
    n = sum(len(s["flags"]) for s in sections)
    data = {"engine": engine, "source": source, "fetched": dt.date.today().isoformat(), "count": n,
            "sections": [s for s in sections if s["flags"]]}
    if extra:
        data.update(extra)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{engine}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"{engine:<8} {n:>4} flags in {len(data['sections']):>2} sections  <- {source}")
    return data


# ── vLLM: mkdocs page, one <h4> per flag inside <h3> sections ─────────────────────────────
def vllm():
    url = "https://docs.vllm.ai/en/latest/cli/serve/"
    page = fetch(url)
    body = page[page.find("<article") : page.find("</article>")] or page
    sections, current = [], None
    token = re.compile(r"<h[23][^>]*>(.*?)</h[23]>|<h4[^>]*>(.*?)</h4>\s*(?:<dl>(.*?)</dl>)?", re.S)
    for m in token.finditer(body):
        if m.group(1) is not None:
            title = text(m.group(1))
            current = {"title": title, "flags": []}
            sections.append(current)
            continue
        if current is None:
            continue
        names = [n.strip() for n in text(m.group(2)).rstrip("¶").split(",")]
        primary = [n for n in names if n.startswith("--") and not n.startswith("--no-")]
        if not primary:
            continue
        flag = {"name": primary[0], "aliases": [n for n in names if re.fullmatch(r"-[A-Za-z]+", n)] +
                [n for n in primary[1:]],
                "negation": next((n for n in names if n.startswith("--no-")), None),
                "choices": None, "default": None, "help": ""}
        for dd in re.findall(r"<dd>(.*?)</dd>", m.group(3) or "", re.S):
            t = text(dd)
            if t.startswith("Possible choices:"):
                flag["choices"] = [c.strip() for c in t[len("Possible choices:"):].split(",") if c.strip()]
            elif t.startswith("Default:"):
                flag["default"] = t[len("Default:"):].strip()
            else:
                flag["help"] = (flag["help"] + " " + t).strip()
        current["flags"].append(flag)
    # drop the page's own non-flag headings (title, "JSON CLI Arguments" keeps its --json-arg)
    return write("vllm", url, sections)


# ── SGLang: docs tables with Argument | Description | Defaults | Options ────────────────────────
def sglang():
    url = "https://docs.sglang.io/advanced_features/server_arguments.html"
    page = fetch(url)
    heads = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", page, re.S))
    sections = []
    for i, h in enumerate(heads):
        block = page[h.end() : heads[i + 1].start() if i + 1 < len(heads) else len(page)]
        section = {"title": text(h.group(1)), "flags": []}
        for table in re.findall(r"<table.*?</table>", block, re.S):
            rows = re.findall(r"<tr.*?</tr>", table, re.S)
            header = [text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.S)] if rows else []
            if not header or header[0] != "Argument":
                continue
            for row in rows[1:]:
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
                if len(cells) < 2:
                    continue
                names = [text(c) for c in re.findall(r"<code[^>]*>(.*?)</code>", cells[0], re.S)]
                names = [n for n in names if n.startswith("-")] or re.findall(r"--?[A-Za-z][\w-]*", text(cells[0]))
                longs = [n for n in names if n.startswith("--")]
                if not longs:
                    continue
                default = text(cells[2]) if len(cells) > 2 else ""
                options = text(cells[3]) if len(cells) > 3 else ""
                flag = {"name": longs[0], "aliases": longs[1:] + [n for n in names if not n.startswith("--")],
                        "negation": None, "choices": None, "default": default or None, "help": text(cells[1])}
                if options and not options.startswith("Type:"):
                    flag["choices"] = [c.strip() for c in options.split(",") if c.strip()]
                elif options:
                    flag["type"] = options[len("Type:"):].strip()
                section["flags"].append(flag)
        sections.append(section)
    return write("sglang", url, sections)


# ── llama.cpp: markdown tables in the server README ────────────────────────────────────────
def llamacpp():
    url = "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md"
    sections, current = [], None
    for line in fetch(url).split("\n"):
        h = re.match(r"#{2,3} (.+)", line)
        if h:
            current = {"title": h.group(1).strip(), "flags": []}
            sections.append(current)
            continue
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$", line)
        if not (m and current and m.group(1).lstrip().startswith("-")):
            continue
        cell, desc = m.group(1), m.group(2)
        longs = re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", cell)
        shorts = re.findall(r"(?<![-\w])-[A-Za-z][A-Za-z0-9]*(?=[ ,]|$)", cell)
        if not longs:
            continue
        env = re.search(r"\(env: ([A-Z0-9_]+)\)", desc)
        default = re.search(r"\(default: ([^)]*)\)", desc)
        help_text = re.sub(r"\((?:default|env): [^)]*\)", "", desc.replace("<br/>", " ")).strip()
        arg = re.sub(r"^(?:-{1,2}[A-Za-z0-9-]+,?\s*)+", "", cell).strip()
        flag = {"name": longs[0], "aliases": longs[1:] + shorts, "negation": None, "choices": None,
                "default": default.group(1).strip() if default else None, "help": re.sub(r"\s+", " ", help_text)}
        if arg:
            flag["value"] = arg
        if env:
            flag["env"] = env.group(1)
        current["flags"].append(flag)
    return write("llama", url, sections)


# ── TGI: the launcher reference, one block per option ──────────────────────────────────────
def tgi():
    url = "https://raw.githubusercontent.com/huggingface/text-generation-inference/main/docs/source/reference/launcher.md"
    md = fetch(url)
    flags = []
    for block in re.findall(r"^## [A-Z0-9_]+\n```shell\n(.*?)\n```", md, re.S | re.M):
        lines = block.split("\n")
        head = lines[0].strip()
        longs = re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", head)
        if not longs:
            continue
        shorts = re.findall(r"(?<![-\w])-[A-Za-z](?=[ ,]|$)", head)
        body = [l.strip() for l in lines[1:]]
        env = re.search(r"\[env: ([A-Z0-9_]+)", block)
        default = re.search(r"\[default: ([^\]]*)\]", block)
        possible = re.search(r"\[possible values: ([^\]]*)\]", block)
        help_text = " ".join(l for l in body if l and not l.startswith("["))
        flag = {"name": longs[0], "aliases": longs[1:] + shorts, "negation": None,
                "choices": [c.strip() for c in possible.group(1).split(",")] if possible else None,
                "default": default.group(1).strip() if default else None, "help": help_text}
        arg = re.sub(r"^(?:-{1,2}[A-Za-z0-9-]+,?\s*)+", "", head).strip()
        if arg:
            flag["value"] = arg
        if env:
            flag["env"] = env.group(1)
        flags.append(flag)
    return write("tgi", url, [{"title": "text-generation-launcher options", "flags": flags}])


# ── Ollama: the environment variables it documents in its own source ───────────────────────
def ollama():
    url = "https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go"
    src = fetch(url)
    body = src[src.find("func AsMap()") :]
    body = body[: body.find("return ret")]
    flags = []
    for m in re.finditer(r'"([A-Za-z_]+)":\s*\{"\1",\s*.*?,\s*"((?:[^"\\]|\\.)*)"\}', body):
        name, desc = m.group(1), m.group(2).replace('\\"', '"')
        default = re.search(r"\(default:? ?([^)]*)\)", desc)
        flags.append({"name": name, "aliases": [], "negation": None, "choices": None,
                      "default": default.group(1).strip() if default else None,
                      "help": re.sub(r"\s*\(default:? ?[^)]*\)", "", desc).strip(), "env": name})
    return write("ollama", url, [{"title": "Environment variables", "flags": flags}])


# ── MLX LM: the argument parser of its server ──────────────────────────────────────────────
def mlx():
    import ast
    url = "https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/server.py"
    tree = ast.parse(fetch(url))
    flags = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            names = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            longs = [n for n in names if n.startswith("--")]
            if not longs:
                continue
            kw = {}
            for k in node.keywords:
                try:
                    kw[k.arg] = ast.literal_eval(k.value)
                except Exception:
                    kw[k.arg] = None
            default = kw.get("default")
            flags.append({"name": longs[0], "aliases": longs[1:] + [n for n in names if not n.startswith("--")],
                          "negation": None, "choices": kw.get("choices"),
                          "default": None if default is None else str(default), "help": kw.get("help") or ""})
    return write("mlx", url, [{"title": "mlx_lm.server options", "flags": flags}])


ENGINES = {"vllm": vllm, "sglang": sglang, "llama": llamacpp, "tgi": tgi, "ollama": ollama, "mlx": mlx}

if __name__ == "__main__":
    for name in sys.argv[1:] or ENGINES:
        ENGINES[name]()
