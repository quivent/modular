<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/cover-mobile.png">
  <img src="assets/readme/cover.png" alt="Modular. Model serving, with room to breathe. A sculpture of precisely balanced glass and ceramic square frames." width="100%">
</picture>

<br>

<p align="center">
  <img src="assets/readme/banner.svg" alt="MODULAR in green block letters above a vllm serve command" width="820">
</p>

<p align="center">
  <img alt="status: working prototype" src="https://img.shields.io/badge/status-working_prototype-def5b6?style=flat-square&labelColor=233327">
  <img alt="build: none" src="https://img.shields.io/badge/build-none-a9d6a0?style=flat-square&labelColor=233327">
  <img alt="engines: 6 + custom" src="https://img.shields.io/badge/engines-6_%2B_custom-8ec5e6?style=flat-square&labelColor=233327">
  <img alt="models: 15 curated" src="https://img.shields.io/badge/models-15_curated-f2c879?style=flat-square&labelColor=233327">
  <img alt="output: CLI, JSON, Docker" src="https://img.shields.io/badge/output-CLI_·_JSON_·_Docker-ee8b7d?style=flat-square&labelColor=233327">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;·&nbsp;
  <a href="#what-you-can-do-with-it">Use cases</a> &nbsp;·&nbsp;
  <a href="#how-it-works">How it works</a> &nbsp;·&nbsp;
  <a href="#inside-modular">Workspace</a> &nbsp;·&nbsp;
  <a href="#engines">Engines</a> &nbsp;·&nbsp;
  <a href="#honest-limits">Limits</a> &nbsp;·&nbsp;
  <a href="DESIGN.md">Design notes</a>
</p>

<br>

**A difficult task deserves a thoughtful place to do it.**

Serving a model means bringing checkpoints, engines, hardware, and runtime settings into agreement. The requirements are strict, the conventions differ, and the details keep changing.

Modular gives that work a calmer shape. Choose a model, an engine, and the hardware you have. Modular assembles a launch command, explains where every flag came from, and tells you plainly when two choices disagree. The interface is spacious, the deeper controls open only where they apply, and the finished command is always in view beside you.

> **Modular is a prototype.** It is a complete, working interface that generates a *starting specification* for a server. It does not install or launch anything, and it does not yet check against versioned engine profiles. See [Honest limits](#honest-limits) and the [roadmap](ROADMAP.md).

<br>

<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/output-mobile.png">
  <img src="assets/readme/workspace.png" alt="Actual Modular interface: six engines and a custom path beside the generated vLLM command, saved configurations, flag map, and checks. On narrow screens, the live output panel is shown in detail." width="100%">
</picture>

<br>

## What you can do with it

| If you are… | Modular helps you… | Where to look |
| --- | --- | --- |
| 🟢 **Standing up a model for the first time** | Pick a model and an engine, answer a few plain questions, and get a starting command without reading every flag reference. | Quick start |
| 🔵 **Moving between engines** | Switch from vLLM to SGLang or Ollama and keep your intent. Settings that do not translate are named instead of dropped. | Switch engines |
| 🟡 **Sizing for a GPU box** | Set GPU count and memory, tensor and pipeline parallelism, CPU offload, and KV cache. Get a weight-memory note and a warning on oversubscription. | Hardware, Checks |
| 🟠 **Comparing configurations** | Save setups in the browser and restore model, engine, hardware, and settings together. | Save current |
| 🔴 **Handing a setup to someone else** | Copy readable CLI, a one-liner, JSON, or a vLLM Docker command. The flag map explains where each part came from. | Output |
| 🟣 **Trying your own fine-tunes** | Load up to 100 public repositories from a Hugging Face profile, or paste a reference, URL, or path. | Models |

<br>

## How it works

<p align="center">
  <img src="assets/readme/pipeline.svg" alt="Four boxes joined by arrows: model, engine, hardware, output. Checks run beneath them." width="900">
</p>

Modular keeps **what you want** separate from **how each engine spells it**. You choose a model, an engine, and hardware; those choices form one configuration. The renderer turns that configuration into a command, and the checker reads the same configuration to report conflicts. Model, engine, hardware, and runtime settings stay independent dimensions, so changing one does not quietly rewrite another.

<br>

## Inside Modular

**01 &nbsp; Choose your starting point.** Browse models by family, bring a reference or path, or load public repositories from a Hugging Face profile. Keep favorites and a default close at hand.

**02 &nbsp; Give the workload what it needs.** Choose an engine, context, weight format, and hardware. Scheduling, cache, offload, and network controls appear where relevant. Engine changes preserve choices and call out selected settings that do not translate.

**03 &nbsp; See what your choices mean.** The live command, flag map, and checks keep the result inspectable. Copy an export or save a configuration in the browser for another session.

### Every part of the command is traceable

<p align="center">
  <img src="assets/readme/flagmap.svg" alt="Flag map: Model, Context, Devices, Memory, and Caching each connected to the vLLM flag they produce." width="760">
</p>

### Switch engines without losing your intent

<p align="center">
  <img src="assets/readme/engines.svg" alt="Switching from vLLM to SGLang or Ollama: translated settings are mapped, and one that cannot translate is flagged in Checks." width="900">
</p>

<br>

## Principles

- 🟢 **Choices, not typing.** Buttons, presets, sliders, and switches carry the main decisions. Free text appears only where the value is free text: a model link, a host, a path, an extra argument.
- 🔵 **Nothing disappears silently.** If an engine has no equivalent for a setting, Checks says so, and the setting stays saved for when you switch back.
- 🟡 **Every flag has a reason.** The flag map traces each part of the command to the choice that produced it.
- 🟠 **Unknown stays unknown.** Modular never claims a model runs on an engine because both appear in a list.
- 🔴 **Your data stays with you.** No account, no token, no server. Favorites and saved configurations live in your browser.

<br>

## What the checks catch

| | Check | Example |
| --- | --- | --- |
| 🔴 | **GPU oversubscription** | Tensor GPUs × pipeline stages exceeds the GPU count you selected |
| 🟠 | **Settings an engine omits** | A saved device count, memory target, or parser choice the current engine cannot express |
| 🟡 | **Repeated or opposing arguments** | An extra argument duplicates a flag Modular already generated |
| 🟡 | **Fit estimate** | A weight-only memory note for the chosen checkpoint and hardware |
| 🔵 | **Risky combinations** | FP8 KV cache needs hardware support; eager mode disables CUDA graphs; CPU offload moves weights during inference; Docker needs the server bound to all interfaces |
| 🟢 | **Scheduling sanity** | A token batch smaller than the sequence limit may constrain scheduling |
| 🟢 | **Fixed KV cache** | A fixed allocation replaces the GPU memory target, and Modular says which flag it omitted |

<br>

## Engines

| | Engine | Command shape | Notable controls in the prototype |
| --- | --- | --- | --- |
| 🟢 | **vLLM** | `vllm serve …` | Tensor and pipeline parallelism, CPU offload, fixed KV cache, priority scheduling, prefix caching, chunked prefill, dtype, request logging, Docker output |
| 🔵 | **SGLang** | `python -m sglang.launch_server …` | Tensor parallelism, static memory fraction, radix cache toggle, reasoning and tool-call parsers |
| 🟡 | **TGI** | text-generation-inference | Shared context, GPU, and quantization choices |
| 🟠 | **llama.cpp** | llama.cpp server | Shared context, GPU, and quantization choices |
| 🔴 | **Ollama** | `ollama pull` + `ollama serve` with environment settings | Host, context length, parallel requests, GGUF references |
| 🟣 | **MLX LM** | MLX LM server | Shared context and quantization choices |
| ⚪ | **Custom** | your own template | Extra arguments checked for repeats and opposing flags |

<details>
<summary>Models, engines, and output formats</summary>

| Dimension | Available in the prototype |
| --- | --- |
| Models | 15 curated starting points across Ornith, Qwen, Reasoning, Vision, and Other groupings, including Llama 3.3 70B, Gemma 3 27B, Phi-4, Mixtral 8x7B, DeepSeek R1 Distill 32B, Qwen2.5 VL 7B, Whisper large v3, Stable Diffusion XL, and BGE embedding and reranking models; custom references, tags, URLs, and paths; up to 100 public repositories from a Hugging Face profile |
| Views | All, Favorites, Recent, Text, and Other |
| Model-specific controls | Ornith 1.5 checkpoint choices (BF16, FP8, NVFP4, GGUF where published) and conditional reasoning and tool-call parsers |
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

Open [localhost:8000](http://localhost:8000). No build step or account is required.

1. Start with **Qwen3 8B** and **vLLM**.
2. Change a choice: context, GPU count, or engine.
3. Open **Where each choice goes** beneath the output to see the flag it produced.
4. **Save current** to keep the setup, or copy the command.

<br>

## Honest limits

Modular is a working prototype that produces a **starting specification**. Its checks cover selected conflicts; confirm the output against the engine version, checkpoint, and hardware you intend to use.

| ✅ It does | ⚠️ It does not |
| --- | --- |
| Catch GPU oversubscription | Install or launch a server |
| Flag settings an engine omits | Verify engine versions or architecture support |
| Warn when extra arguments repeat or oppose generated flags | Inspect checkpoint contents |
| Estimate weight memory for the chosen checkpoint | Measure real memory headroom, KV cache, or activations |
| Say “no setting conflicts detected” | Promise that message means the setup will run. It means no implemented check found a conflict |

The path to a finished product is in [ROADMAP.md](ROADMAP.md). [DESIGN.md](DESIGN.md) records the intended direction, including versioned engine profiles, source links with last-checked dates, and broader compatibility rules that are not implemented yet.

<br>

<details>
<summary>Local data and project files</summary>

Favorites, a default model, and saved configurations live in browser local storage. Recent models last for the current page session. The optional Hugging Face profile picker reads public data without asking for a token and remembers the profile name locally. Google Fonts and the public profile lookup are the page’s external requests.

| File | Purpose |
| --- | --- |
| [index.html](index.html) | Live, self-contained prototype |
| [next.html](next.html) | Current working copy |
| [DESIGN.md](DESIGN.md) | Product direction and iteration history |
| [ROADMAP.md](ROADMAP.md) | Checklist to a finished release |
| [catalog-draft.html](catalog-draft.html), [original.html](original.html) | Earlier explorations |
| [assets/readme](assets/readme) | Artwork, actual interface captures, generated ASCII-art SVGs (`ascii.py`), and editable README compositions |

</details>

<br>

## Road to a finished release

Modular is a prototype, and this is the plain list of what stands between it and a finished tool. It is ordered roughly by dependency. Items are checked off as they land, and the same list lives in [ROADMAP.md](ROADMAP.md).

### Foundation

- [ ] **1. Separate the working copy.** `index.html` and `next.html` are currently identical. Settle on one flow (edit `next.html`, promote to `index.html`) or remove one, and document it.
- [ ] **2. Split the single file.** Move the ~89 KB page into a configuration model, engine renderers, checks, and UI modules. Stay buildless with ES modules so `python3 -m http.server` keeps working.
- [ ] **3. Reconcile the docs with the app.** `DESIGN.md` still cites 12 models in earlier sections; the app has 15. Keep one current-state summary at the top and move history below it.
- [ ] **4. Version the saved data.** Add a schema version to saved configurations and preferences in local storage, with migrations, so an update never strands someone's saved setups.
- [ ] **5. License and contributing guide.** The repository has no license file yet. Add one, plus short instructions for running, testing, and adding a model or engine.

### Trust

- [ ] **6. Versioned engine profiles.** Describe each engine's flags, defaults, accepted values, and conflicts as data per version, then generate the renderer and checks from it.
- [ ] **7. Engine version selector.** Let people pick the version they run, and show how defaults or spellings differ before export.
- [ ] **8. Source links and last-checked dates.** Link each version-specific flag to its documentation, and label unknown compatibility as unknown.
- [ ] **9. Automated tests.** Golden-file tests for every engine and output format, plus a test for each check (oversubscription, omitted settings, duplicate arguments).
- [ ] **10. Better fit estimates.** Extend the weight-only note to KV cache and activation headroom for the chosen context and batch, clearly labeled as an estimate.
- [ ] **11. Input validation.** Validate pasted references, hosts, ports, paths, and extra arguments, and quote them safely in every output format.

### Reach

- [ ] **12. More command forms.** Add environment-variable output and Kubernetes or Compose snippets, generated from the same configuration state.
- [ ] **13. Complete the remaining engines.** Bring TGI, llama.cpp, and MLX LM to the same depth as vLLM and SGLang.
- [ ] **14. Share and import.** Export a configuration as a link or file and import it, so a setup can move between people and machines.
- [ ] **15. Catalog upkeep.** Refresh the curated models, and add a lightweight way to update the catalog without editing the page.
- [ ] **16. Private repositories.** Offer a clear, token-free path for private Hugging Face repositories beyond pasting an exact reference.

### Polish

- [ ] **17. Accessibility pass.** Keyboard-only walkthrough, screen-reader audit of the checks and flag map, contrast and reduced-motion checks.
- [ ] **18. Phone and tablet audit.** Review every breakpoint on real devices, including the live output panel and saved configurations.
- [ ] **19. Browser support matrix.** Test current Chrome, Safari, and Firefox, including clipboard fallbacks and local storage being unavailable.
- [ ] **20. Self-hosted fonts and offline mode.** Remove the Google Fonts request so the page works fully offline.
- [ ] **21. Continuous checks.** Run the tests and a link and asset check on every change.
- [ ] **22. Release.** Refresh screenshots with `assets/readme/render.py`, tag a version, deploy, and remove the "prototype" label from this README.
