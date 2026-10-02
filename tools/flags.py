#!/usr/bin/env python3
"""Extracts EVERY flag of each serving engine from the engine's own documentation.

    python3 tools/flags.py              # all engines
    python3 tools/flags.py vllm         # one engine
    python3 tools/flags.py --out DIR vllm   # write there instead of catalog/flags (the librarian stages this way)

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
    return mkdocs_argparse("vllm", "https://docs.vllm.ai/en/latest/cli/serve/")


# vLLM-Omni (text-to-speech and other multi-stage models) publishes its `vllm serve --omni` reference the same way.
def vllm_omni():
    return mkdocs_argparse("vllm-omni", "https://docs.vllm.ai/projects/vllm-omni/en/latest/cli/serve/")


def mkdocs_argparse(engine, url):
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
    return write(engine, url, sections)


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


# ── TensorRT-LLM: sphinx-click reference for `trtllm-serve serve` ─────────────────────────
def trtllm():
    url = "https://nvidia.github.io/TensorRT-LLM/commands/trtllm-serve/trtllm-serve.html"
    page = fetch(url)
    seg = page[page.find('id="syntax"') :]
    start = next(m.start() for m in re.finditer(r"<pre>.*?</pre>", seg, re.S)
                 if text(m.group(0)).startswith("trtllm-serve serve [OPTIONS] MODEL"))
    opt = next(m.start() for m in re.finditer(r'<p class="rubric">Options</p>', seg) if m.start() > start)
    end = next(m.start() for m in re.finditer(r'<p class="rubric">Arguments</p>', seg) if m.start() > opt)
    flags = []
    for dt, dd in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", seg[opt:end], re.S):
        head = text(dt).rstrip("#").strip()
        names_part, _, meta = head.partition(" <")
        names = [n.strip() for n in names_part.split(",")]
        longs = [n for n in names if n.startswith("--")]
        if not longs:
            continue
        body = text(dd)
        body = re.sub(r"^(?:beta|prototype|deprecated|stable)\s+", "", body)
        choices = re.search(r"Options?: ([^.]*?)(?:\.|$)", body)
        default = re.search(r"Defaults? (?:to|is) ([^.]+?)\.(?:\s|$)", body)
        flags.append({"name": longs[0], "aliases": longs[1:] + [n for n in names if not n.startswith("--")],
                      "negation": None,
                      "choices": [c.strip() for c in choices.group(1).split("|")] if choices and "|" in choices.group(1) else None,
                      "default": default.group(1).strip() if default else None, "help": body,
                      **({"value": "<" + meta.rstrip(">") + ">"} if meta else {})})
    return write("trtllm", url, [{"title": "trtllm-serve options", "flags": flags}])


# ── SGLang Diffusion: the `sglang serve` options of its CLI reference (image and video models) ─────────
def sglang_diffusion():
    url = "https://docs.sglang.io/docs/sglang-diffusion/api/cli"
    page = fetch(url)
    body = page[page.find("<h1") :]
    # Server options only: "Sampling and output" lists the options of one generation request, not of the server.
    keep = {"Model and runtime", "Quantization", "Request logging", "Layerwise Offload Tuning", "Generate"}
    sections, current = {}, None
    for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>|<li>(\s*<code>--.*?)</li>", body, re.S):
        if m.group(1):
            title = clean(text(m.group(2)))
            current = sections.setdefault(title, {"title": title, "flags": []}) if title in keep else None
            continue
        if current is None:
            continue
        head, _, desc = m.group(3).partition(":")
        desc = text(desc)
        desc = desc[:1].upper() + desc[1:]
        codes = re.findall(r"(<code>(--[\w.\-]+)([^<]*)</code>)", head)
        if not codes:
            continue
        first = None
        for k, (whole, name, spec) in enumerate(codes):
            between = text(head[head.find(codes[k - 1][0]) + len(codes[k - 1][0]) : head.find(whole)]) if k else ""
            spec = html.unescape(spec).strip()
            if k and ("alias" in between or "/" in between):
                first["aliases"].append(name)  # the same flag under another name
                continue
            choices = re.search(r"\{([^{}]*[|,][^{}]*)\}", spec)
            flag = {"name": name, "aliases": [], "negation": None,
                    "choices": [c.strip() for c in re.split(r"[|,]", choices.group(1))] if choices else None,
                    "default": None, "help": desc}
            if spec and not choices:
                flag["value"] = "<" + spec.strip("{} ") + ">"
            current["flags"].append(flag)
            first = first or flag
    # --port is only shown in the serve examples, never in an option list: record that it is used, with no description
    serve_example = re.search(r"sglang serve[^<]{0,400}?--port", html.unescape(re.sub(r"<[^>]+>", "", body)), re.S)
    if serve_example and not any(f["name"] == "--port" for s in sections.values() for f in s["flags"]):
        sections["In the serve examples"] = {"title": "In the serve examples", "flags": [
            {"name": "--port", "aliases": [], "negation": None, "choices": None, "default": None, "help": "", "value": "<PORT>"}]}
    # The quantization guide shows the flags that choose a precision only in its examples, so read those too.
    guide = "https://docs.sglang.io/docs/sglang-diffusion/quantization"
    try:
        blocks = re.findall(r"<(?:pre|code)[^>]*>(.*?)</(?:pre|code)>", fetch(guide), re.S)  # code only: prose runs words together
        examples = "\n".join(html.unescape(re.sub(r"<[^>]+>", "", b)) for b in blocks)
        have = {f["name"] for sec in sections.values() for f in sec["flags"]}
        found = []
        for m in re.finditer(r"(?<![\w-])--(?:transformer-|component-|quantization)(?:[\w.\-]*[A-Za-z0-9_])?(?=[\s\\=\"'`]|$)", examples):
            if m.group(0) not in have and m.group(0) not in found:
                found.append(m.group(0))
        if found:
            sections["In the quantization guide"] = {"title": "In the quantization guide", "flags": [
                {"name": n, "aliases": [], "negation": None, "choices": None, "default": None, "help": "", "value": "<VALUE>"} for n in found]}
    except Exception as e:
        print("could not read the quantization guide:", e)
    return write("sglang-diffusion", url, list(sections.values()))


ENGINES = {"vllm": vllm, "trtllm": trtllm, "sglang": sglang, "llama": llamacpp, "tgi": tgi, "ollama": ollama, "mlx": mlx, "sglang-diffusion": sglang_diffusion, "vllm-omni": vllm_omni}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--out" in args:
        i = args.index("--out")
        OUT = pathlib.Path(args[i + 1])
        del args[i : i + 2]
    for name in args or ENGINES:
        ENGINES[name]()
