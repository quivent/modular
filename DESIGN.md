# Modular — UX direction

The job is to turn a changing set of inference-server flags into a configuration
someone can trust and understand. A model picker alone does not solve that.
Users need to see which settings apply, which conflict, why a command changed,
and how to express the same setup for their deployment method.

## Screen structure

The page is a spacious workspace with four regions:

1. **Stack:** Models and engines are visible on the page, with honest counts.
   The current seed set has 12 models and 6 named engines, plus a custom engine
   path. Select by name. The exact model ID appears as a copyable detail, never
   as a required text field. "Use another model" accepts a pasted link or
   reference and infers its source where possible.
2. **Configuration:** Organize flags by purpose: model compatibility,
   memory/context, throughput, and serving/API. Show the few settings people
   touch most often. "All settings" reveals every applicable flag in those
   same groups, with a visible count. This avoids a flat wall of 15 controls
   without hiding the full tool.
3. **Command:** A live output panel stays in view. The user chooses a command
   form such as native CLI, environment variables, or container launch. Each
   form is generated from the same configuration state.
4. **Checks:** A small, explicit status area says whether the setup is ready,
   has unresolved conflicts, or depends on an unverified model/server
   combination. A conflict points to the exact two settings involved and
   offers a concrete fix. No flag is silently discarded.

A compact wireframe:

    modular.                         Model / Engine / Server version
    ───────────────────────────────────────────────────────────────
    01 Models · 12                   Command form  [CLI] [Env] [Docker]
       visible names                 ┌─────────────────────────────┐
    02 Engines · 6 + custom          │ generated command           │
       visible names                 │ each part traceable         │
    03 Configuration                └─────────────────────────────┘
       Compatibility · 3             Ready / needs attention
       Memory & context · 4
       Throughput · 5
       Serving & API · 3
       [Show all 15 settings]

## Interaction rules

- Put choices directly on the page. Use buttons for choices, a switch for a
  two-state setting, and presets or a slider for numbers. Never require a
  person to type a number or an exact model ID.
- Ask for free text only when the value really is free text: a pasted model
  link, host name, path, or server-specific extra argument.
- The selected model and server version determine which controls appear and
  how each control is translated. Keep the syntax out of the primary choice
  labels; show the resulting flag and its meaning beside the command.
- Show defaults without forcing users to set them. If the installed server
  version changes a default or spelling, show that change before export.
- Preserve user intent when switching engines. Mark settings that cannot be
  translated and ask the user to resolve them.
- Link each version-specific flag to its source documentation and show when
  the rule was last checked. Unknown compatibility is labeled unknown.

## Visual language

A light canvas, strong type, fine separators, and generous vertical space.
Use one restrained accent for selection and resolved states. Put warnings in
plain language near the relevant control and in the checks area. Avoid a
dashboard full of cards, decorative status badges, and dense technical copy.
The command should feel like an explanation of the selected configuration,
not a wall of shell text.

## System behind the interface

Keep a semantic configuration model separate from output syntax. Versioned
server profiles define supported flags, defaults, accepted values, command
forms, and dependencies/conflicts. The renderer compiles that state into a
command; the checker reports unsupported or unverified combinations. This is
what lets the interface stay calm while the servers keep changing.

The live page is in index.html. archive/catalog-draft.html is an unpublished
exploration of inline catalog choices. The previous initial prototype is in
archive/original.html.

## Current iteration (0.4)

The live prototype now keeps the 12 model names and seven engine paths visible,
uses presets, sliders, and switches for the main choices, and generates readable
CLI, one-line CLI, or JSON. The output panel includes a collapsed map from each
emitted command part back to its setting. Extra arguments are checked for flags
that repeat or oppose generated flags. Engine-specific choices remain saved on
switch; unsupported choices are called out in Checks. The model revision field
was removed because it did not affect the command.

The versioned engine profiles, comprehensive compatibility rules, and
additional command forms above remain the product direction; they are not yet
implemented in this prototype. `index.html` is the deployed page; work happens on branches and releases are
git tags.

## Current iteration (0.4.1)

Models are shown in nine family rows with all twelve selections visible; the
selected reference follows the list. The copy action is positioned beside the
preview title and uses a label that matches command or JSON output. Clipboard
fallbacks keep the action useful when direct clipboard access is unavailable.

## Ornith 1.5 deployment pass (0.5)

The catalog now contains the official 9B, 35B-A3B, and 397B models as one
visible family. Checkpoint-build buttons select the real Hugging Face repository
for BF16, FP8, NVFP4, or GGUF where published. Configuration has a hardware
target switch for one RTX 3090 or eight RTX 5090s, with 1/2/4/8 GPU presets
for an instance on the cluster. A conservative weight-only note accompanies
that choice. Reasoning and tool-call parser switches compile to the documented
vLLM and SGLang flags. A vLLM Docker output targets local host port 8080 for
SSH tunneling and never embeds an HF token. Pasted custom Ornith repos can opt
into the same serving profile. The app does not claim that a configuration has
been launched or that a weight-only estimate proves runtime compatibility.

## Profile and structured flags (0.6)

The page still shows 15 seed models and 6 named engines plus a custom path.
An optional Hugging Face profile link loads up to 100 public repositories and
makes each one selectable by name. Selecting an Ornith 1.5 variant enables its
serving profile. Private repositories still use a pasted exact reference;
the static page never asks for a Hugging Face token.

vLLM now exposes tensor and pipeline parallelism separately, CPU weight
offload, fixed KV cache allocation, priority scheduling, and request logging.
The command, JSON, Docker export, and flag map share those choices. Checks
surface GPU oversubscription, settings omitted by another engine, and the
fact that fixed KV allocation replaces the GPU memory target. The profile
picker and all numeric choices use buttons or sliders; free text remains only
for values such as profile names, model links, paths, hosts, and extra flags.

## Model selection pass (0.7)

The first screen now treats a model as a family, a size, and a concrete
checkpoint. It shows the selected repository first, then three Ornith sizes
and the published weight builds for the chosen size. The twelve other curated
models sit in a compact family browser. Loaded Hugging Face variants appear
as selectable rows on the page, grouped separately from the built-in models;
the public profile name is remembered locally so they reappear on a later
visit. This keeps the current trial prominent without presenting three
Ornith sizes as the full set of available checkpoints.

## Minimal pass

The selected checkpoint is a quiet text row with a divider. The page title
states the task, and model labels use short functional names. The family,
weights, profile, and reference paths keep the same behavior without a
promotional hero, colored selection panel, or explanatory sales copy.

## General configurator correction

The current screen starts with the whole 15-model catalog in ten visible
families. Architecture is an explicit choice, and Hugging Face profile models
join the same family-based view. It opens on a general catalog model. Ornith
checkpoint builds and parser settings are conditional model-specific controls,
not the organizing principle of the page. Hardware is expressed as GPU count
and memory per GPU rather than named trial machines; tensor and pipeline
parallelism are separate choices. Model, architecture, engine, quantization,
hardware, tuning, and output remain independent dimensions.

The catalog now compresses to five groupings: Ornith, Qwen, Reasoning, Vision,
and Other. Five model views keep the list calm: All, Favorites, Recent, Text,
and Other. A star remembers favorites, one model can be remembered as the
default, and Save current stores a configuration locally without requiring a
name field. Saved configurations restore the model, engine, hardware, and
settings together.
