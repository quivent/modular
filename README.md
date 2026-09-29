<p align="center">
  <img src="assets/readme-cover.svg" alt="Modular: a quiet interface for the dense work of configuring model servers" width="100%">
</p>

<p align="center"><strong>A quiet surface for the noisy work of model serving.</strong></p>

Modular turns a model, a serving engine, and a set of runtime decisions into a command you can read. It brings a wide set of controls into a sparse workspace: make the main choices first, open the detail you need, and keep the resulting command in view.

```text
modular.                                Build a server command.
------------------------------------------------------------------------

01 / MODEL                              YOUR CONFIGURATION
  Qwen3 8B                              +------------------------------+
  Hugging Face / Text                   | CLI  ONE LINE  DOCKER  JSON  |
  All   Favorites   Recent              |                              |
                                        | vllm serve 'Qwen/Qwen3-8B'   |
02 / ENGINE                             |   --max-model-len 8192       |
  [ vLLM ]  SGLang  TGI                 |   --tensor-parallel-size 1  |
  llama.cpp  Ollama  MLX LM             |   --gpu-memory-utilization   |
                                        |     0.90                     |
03 / CONFIGURATION                      |                              |
  Hardware    1 GPU / 24 GB             | [ Copy command ]             |
  Context     8K tokens                 +------------------------------+
  Scheduling  Auto                      CHECKS
  Memory      GPU target                No setting conflicts detected.
  Advanced    Network / flags           WHERE EACH CHOICE GOES [+]

------------------------------------------------------------------------
  15 curated models / 6 named engines / focused controls / live output
```

### The design idea

**Little on the surface. Depth close at hand.** The page uses numbered sections, warm off-white space, fine rules, dark green type, and a single soft green accent. Common choices are visible; tuning controls unfold where they belong. The preview remains beside the controls and can trace generated flags back to the setting that produced them. That contrast between an approachable page and a capable configurator is the point.

### What is inside

- **Models with context.** Fifteen curated starting models, published Ornith checkpoint builds, custom references, and public models loaded from a Hugging Face profile. Favorites, recent models, and a default make the catalog easier to revisit.
- **Engines with their own vocabulary.** vLLM, SGLang, TGI, llama.cpp, Ollama, and MLX LM, plus a custom command template. Engine-specific controls appear when relevant; choices that do not translate are called out.
- **Configuration that stays inspectable.** GPU count and memory, context, quantization, scheduling, cache, networking, and extra arguments feed a live preview. Output is available as readable CLI, one-line CLI, or JSON; vLLM also offers Docker.
- **Checks alongside output.** The page flags selected conflicts, omitted settings, and unchecked extra arguments. The expandable flag map shows where each choice lands in the command.

### Run locally

```sh
python3 -m http.server 8000
```

Open `http://localhost:8000`. Modular is a static page with no build step. The Hugging Face profile option reads public model data from the Hugging Face API. Favorites and saved configurations are kept in your browser.

### In this repository

[`index.html`](index.html) is the live prototype. [`next.html`](next.html) is its working copy. [`DESIGN.md`](DESIGN.md) records the product direction and iteration decisions; [`catalog-draft.html`](catalog-draft.html) and [`original.html`](original.html) preserve earlier explorations.

<sub>Modular builds a starting specification. Check model, weights, hardware fit, and flags against your installed serving engine before deployment.</sub>
