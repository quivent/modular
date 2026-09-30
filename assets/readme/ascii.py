"""Generates the colored ASCII-art SVGs used in README.md (no dependencies).
Run: python3 assets/readme/ascii.py
"""
import html, pathlib

OUT = pathlib.Path(__file__).parent
BG, INK = "#16211a", "#e9efe4"
LIME, CELADON, SAGE, AMBER, ROSE, SKY, DIM = "#def5b6", "#a9d6a0", "#5f8f63", "#f2c879", "#ee8b7d", "#8ec5e6", "#5d6e60"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
CW, LH, FS = 9.6, 20, 16


def svg(name, rows, pad=28, title=""):
    """rows: list of lines; each line is a list of (text, color) segments."""
    w = int(max(sum(len(t) for t, _ in r) for r in rows) * CW + pad * 2)
    h = int(len(rows) * LH + pad * 2)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}">',
         f'<rect width="{w}" height="{h}" rx="14" fill="{BG}"/>',
         f'<g font-family="{FONT}" font-size="{FS}" xml:space="preserve">']
    for i, r in enumerate(rows):
        y = pad + LH * i + FS - 3
        x = pad
        for t, c in r:
            chars = [(ch, x + k * CW) for k, ch in enumerate(t) if ch != " "]
            if chars:
                xs = " ".join(f"{cx:.1f}" for _, cx in chars)
                o.append(f'<text x="{xs}" y="{y}" fill="{c}">{html.escape("".join(ch for ch, _ in chars))}</text>')
            x += len(t) * CW
    o.append("</g></svg>")
    (OUT / name).write_text("\n".join(o))


def L(*segs):
    return list(segs)

# ── 1. banner ──────────────────────────────────────────────────────────
logo = [
    "███╗   ███╗ ██████╗ ██████╗ ██╗   ██╗██╗      █████╗ ██████╗ ",
    "████╗ ████║██╔═══██╗██╔══██╗██║   ██║██║     ██╔══██╗██╔══██╗",
    "██╔████╔██║██║   ██║██║  ██║██║   ██║██║     ███████║██████╔╝",
    "██║╚██╔╝██║██║   ██║██║  ██║██║   ██║██║     ██╔══██║██╔══██╗",
    "██║ ╚═╝ ██║╚██████╔╝██████╔╝╚██████╔╝███████╗██║  ██║██║  ██║",
    "╚═╝     ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
]
grad = [LIME, "#cdeeaa", "#bde5a3", "#a9d6a0", "#8dc397", "#6fa87e"]
sculpt = [
    "      ┌────────┐      ",
    "      │ ┌────┐ │      ",
    "  ┏━━━┿━┿━━┓ │ │      ",
    "  ┃   │ └──╂─┘ │      ",
    "  ┃  ┌┴────╂───┘      ",
    "  ┗━━┿━━━━━┛          ",
    "     └───────╴        ",
]
rows = [L(("", DIM))]
rows.append(L(("  model ", DIM), ("▸", SAGE), (" engine ", DIM), ("▸", SAGE), (" hardware ", DIM), ("▸", SAGE), (" command", LIME)))
rows.append(L(("", DIM)))
for i, l in enumerate(logo):
    rows.append(L(("  ", DIM), (l, grad[i])))
rows.append(L(("", DIM)))
rows.append(L(("  ", DIM), ("░▒▓", SAGE), (" model serving, with room to breathe ", INK), ("▓▒░", SAGE)))
rows.append(L(("", DIM)))
rows.append(L(("  $ ", DIM), ("vllm serve ", INK), ("Qwen/Qwen3-8B", LIME), (" --max-model-len ", SKY), ("32768", AMBER),
              (" --tensor-parallel-size ", SKY), ("1", AMBER), (" █", CELADON)))
rows.append(L(("", DIM)))
svg("banner.svg", rows, title="MODULAR — model serving, with room to breathe")

# ── 2. pipeline ────────────────────────────────────────────────────────
C1, C2, C3, C4 = LIME, SKY, AMBER, CELADON
def box(col, title, lines, w=22):
    top = "╭" + "─" * w + "╮"
    bot = "╰" + "─" * w + "╯"
    body = ["│" + (" " + t).ljust(w) + "│" for t in [title] + [""] + lines]
    return col, [top] + body + [bot]

boxes = [
    box(C1, "01 MODEL", ["15 curated picks", "custom ref / path", "HF profile (≤100)", "★ favorites"]),
    box(C2, "02 ENGINE", ["vLLM  · SGLang", "TGI   · llama.cpp", "Ollama· MLX LM", "custom template"]),
    box(C3, "03 HARDWARE", ["GPU count", "memory per GPU", "context length", "quantization"]),
    box(C4, "04 OUTPUT", ["readable CLI", "one-line CLI", "JSON", "Docker (vLLM)"]),
]
h = len(boxes[0][1])
rows = [L(("", DIM))]
rows.append(L(("  one semantic configuration  ", INK), ("→", SAGE), ("  many command dialects", INK)))
rows.append(L(("", DIM)))
for i in range(h):
    segs = [("  ", DIM)]
    for j, (col, ls) in enumerate(boxes):
        segs.append((ls[i], col))
        if j < 3:
            segs.append((" ━━▶ " if i == h // 2 else "     ", SAGE))
    rows.append(L(*segs))
rows.append(L(("", DIM)))
rows.append(L(("  ", DIM), ("╰─", SAGE), (" checks ", ROSE), ("GPU oversubscription · dropped flags · duplicate args · weight-fit estimate", DIM)))
rows.append(L(("", DIM)))
svg("pipeline.svg", rows, title="Model to engine to hardware to output pipeline")

# ── 3. flag map ────────────────────────────────────────────────────────
rows = [
    L(("", DIM)),
    L(("  where each choice goes", INK), ("   (vLLM · Qwen3 8B · 1 GPU)", DIM)),
    L(("", DIM)),
    L(("  Model     ", LIME), ("●━━━━━━━━━━━━━━", SAGE), ("▶ ", SAGE), ("vllm serve ", INK), ("Qwen/Qwen3-8B", LIME)),
    L(("  Context   ", SKY), ("●━━━━━━━━━━━━━━", SAGE), ("▶ ", SAGE), ("--max-model-len ", INK), ("32768", AMBER)),
    L(("  Devices   ", SKY), ("●━━━━━━━━━━━━━━", SAGE), ("▶ ", SAGE), ("--tensor-parallel-size ", INK), ("1", AMBER)),
    L(("  Memory    ", AMBER), ("●━━━━━━━━━━━━━━", SAGE), ("▶ ", SAGE), ("--gpu-memory-utilization ", INK), ("0.90", AMBER)),
    L(("  Caching   ", CELADON), ("●━━━━━━━━━━━━━━", SAGE), ("▶ ", SAGE), ("--enable-prefix-caching", INK)),
    L(("", DIM)),
    L(("  ✓ ", LIME), ("no setting conflicts detected", DIM), ("   (means: no implemented check found one)", DIM)),
    L(("", DIM)),
]
svg("flagmap.svg", rows, title="Flag map: each setting traced to its command part")

# ── 4. switch engines ──────────────────────────────────────────────────
rows = [
    L(("", DIM)),
    L(("  switch engine, keep intent", INK)),
    L(("", DIM)),
    L(("  vLLM    ", LIME), ("--tensor-parallel-size 2", INK), ("  ━━━━━━━▶ ", SAGE), ("SGLang  ", SKY), ("--tp 2", INK)),
    L(("  vLLM    ", LIME), ("--max-model-len 32768", INK), ("    ━━━━━━━▶ ", SAGE), ("SGLang  ", SKY), ("--context-length 32768", INK)),
    L(("  vLLM    ", LIME), ("--cpu-offload-gb 8", INK), ("       ━━━━━━━▶ ", SAGE), ("SGLang  ", SKY), ("✗ ", ROSE), ("not translated, flagged in Checks", ROSE)),
    L(("  vLLM    ", LIME), ("--tensor-parallel-size 2", INK), ("  ━━━━━━━▶ ", SAGE), ("Ollama  ", AMBER), ("OLLAMA_NUM_PARALLEL=2", INK)),
    L(("", DIM)),
    L(("  nothing is silently discarded", DIM)),
    L(("", DIM)),
]
svg("engines.svg", rows, title="Switching engines preserves intent and flags what cannot translate")
