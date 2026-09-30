<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/cover-mobile.png">
  <img src="assets/readme/cover.png" alt="Modular. Model serving, with room to breathe. A sculpture of precisely balanced glass and ceramic square frames." width="100%">
</picture>

<br>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp; · &nbsp;
  <a href="#inside-modular">Workspace</a> &nbsp; · &nbsp;
  <a href="DESIGN.md">Design notes</a>
</p>

<br>

**A difficult task deserves a thoughtful place to do it.**

Serving a model means bringing checkpoints, engines, hardware, and runtime settings into agreement. The requirements are strict, the conventions differ, and the details keep changing.

Modular gives that work a calmer shape. A spacious browser interface keeps the main decisions clear, opens deeper controls where they matter, and shows the command taking shape beside you. Enough room to think. Enough detail to stay in control.

<br>

<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/output-mobile.png">
  <img src="assets/readme/workspace.png" alt="Actual Modular interface: six engines and a custom path beside the generated vLLM command, saved configurations, flag map, and checks. On narrow screens, the live output panel is shown in detail." width="100%">
</picture>

<br>

## Inside Modular

**01 &nbsp; Choose your starting point.** Browse models by family, bring a reference or path, or load public repositories from a Hugging Face profile. Keep favorites and a default close at hand.

**02 &nbsp; Give the workload what it needs.** Choose an engine, context, weight format, and hardware. Scheduling, cache, offload, and network controls appear where relevant. Engine changes preserve choices and call out selected settings that do not translate.

**03 &nbsp; See what your choices mean.** The live command, flag map, and checks keep the result inspectable. Copy an export or save a configuration in the browser for another session.

<details>
<summary>Models, engines, and output formats</summary>

| Dimension | Available in the prototype |
| --- | --- |
| Models | 15 curated starting points; custom references, tags, URLs, and paths; up to 100 public repositories from a Hugging Face profile |
| Model-specific controls | Ornith 1.5 checkpoint choices and conditional reasoning and tool-call parsers |
| Engines | vLLM, SGLang, TGI, llama.cpp, Ollama, MLX LM, and a custom command template |
| Tuning | Context, GPU count and memory, quantization, plus applicable scheduling, precision, cache, offload, network, and extra-argument controls |
| Output | Readable CLI, one-line CLI, and JSON; Docker for vLLM |

Catalog inclusion does not establish engine compatibility. Model, engine, hardware, and runtime choices remain separate dimensions.

</details>

<br>

## Quick start

From this directory:

```sh
python3 -m http.server 8000
```

Open [localhost:8000](http://localhost:8000). No build step or account is required. Start with Qwen3 8B and vLLM, change a choice, and open **Where each choice goes** beneath the output.

Modular is a working prototype that produces a **starting specification**. Its checks cover selected conflicts; confirm the output against the engine version, checkpoint, and hardware you intend to use.

<details>
<summary>What the prototype checks</summary>

Checks catch cases such as GPU oversubscription, settings omitted by an engine, and extra arguments that repeat generated flags. The checkpoint fit note estimates weight memory only.

The page does not install or launch a server. It does not verify engine versions, architecture support, checkpoint contents, actual memory headroom, or arbitrary extra arguments. “No setting conflicts detected” means no implemented check found one.

[DESIGN.md](DESIGN.md) records the intended direction, including versioned engine profiles and broader compatibility rules that are not implemented yet.

</details>

<details>
<summary>Local data and project files</summary>

Favorites, a default model, and saved configurations live in browser local storage. Recent models last for the current page session. The optional Hugging Face profile picker reads public data without asking for a token and remembers the profile name locally. Google Fonts and the public profile lookup are the page’s external requests.

| File | Purpose |
| --- | --- |
| [index.html](index.html) | Live, self-contained prototype |
| [next.html](next.html) | Current working copy |
| [DESIGN.md](DESIGN.md) | Product direction and iteration history |
| [catalog-draft.html](catalog-draft.html), [original.html](original.html) | Earlier explorations |
| [assets/readme](assets/readme) | Artwork, actual interface captures, and editable README compositions |

</details>
