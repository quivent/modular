# Modular

<p align="center">
  <img src="assets/readme-cover.svg" alt="Modular cover: Hard work, held lightly, beside woven green contours surrounding a quiet center" width="100%">
</p>

**Model serving is exacting. The workspace for it can be calm.**

Checkpoints, engines, hardware, and runtime flags all have strict requirements. Their rules differ, their syntax is unforgiving, and the details keep changing. Modular gathers those decisions in a spacious browser interface so you can work through them without facing a wall of settings.

## 01 / Space to think

Choose a **model**, then an **engine**, then the **capacity and tuning** the workload needs. The first view stays quiet: generous space, warm off-white, restrained green, plain labels, and direct choices. More specific controls open near the decisions they affect.

A live command sits beside the workspace. **Where each choice goes** traces its parts back to controls; **Checks** points out selected conflicts and settings an engine cannot express. The command is one part of the experience. The larger aim is to make difficult configuration feel clear enough to reason through and comfortable enough to stay with.

## 02 / Open the workspace

```sh
python3 -m http.server 8000
```

Open [localhost:8000](http://localhost:8000). The page starts with Qwen3 8B and vLLM. Change the engine, GPU count, or context window and watch the relevant controls and output respond. No build step or account is required.

## 03 / Depth where it matters

- **Models:** 15 curated starting points, a pasted reference or path, and up to 100 public models loaded from a Hugging Face profile. Ornith 1.5 adds published checkpoint and parser choices. Catalog inclusion does not establish engine compatibility.
- **Engines:** vLLM, SGLang, TGI, llama.cpp, Ollama, and MLX LM, plus an **Other server** command template. Choices remain in the page when engines change; selected settings that do not translate are called out.
- **Configuration:** context, GPU count, memory per GPU, and weight format up front; scheduling, cache, offload, network, and extra arguments where relevant. The checkpoint fit note estimates weight memory only.
- **Output:** readable CLI, one-line CLI, and JSON to copy or download; vLLM also has Docker output. The flag map and checks make generated choices easier to inspect.

Favorites, a default model, and saved configurations live in browser local storage. Recent models last for the current page session. The optional Hugging Face profile picker requests public data without a token.

## 04 / Honest boundaries

Modular produces a **starting specification**. It does not install an engine, download weights, or launch a server. Checks cover selected cases; they do not verify engine versions, architecture support, checkpoint contents, actual memory headroom, or arbitrary extra arguments. “No setting conflicts detected” means no implemented check found one. Confirm the output against the engine version and checkpoint you intend to run.

[DESIGN.md](DESIGN.md) records the longer term direction, including versioned engine profiles and broader compatibility rules. Those are not yet implemented.

## Repository

| File | Purpose |
| --- | --- |
| [index.html](index.html) | Live, self-contained prototype |
| [next.html](next.html) | Current working copy |
| [DESIGN.md](DESIGN.md) | Product direction and iteration history |
| [catalog-draft.html](catalog-draft.html), [original.html](original.html) | Earlier explorations |

The page works locally without a backend. Google Fonts and the optional public Hugging Face lookup are its external requests.
