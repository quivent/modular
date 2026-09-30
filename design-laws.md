# Design laws

Written down from the rulings in the project history. Phase 4 of the loop scores every artifact
against each law that applies (PASS or FAIL with what was observed, or N/A with the reason).

- **LAW-1 Spacious and simple.** The default view looks calm and friendly. Depth comes from data
  and disclosure, not from visible clutter.
- **LAW-2 Name the confusion.** For every UI change, name the most likely confusion and remove it
  before presenting the change.
- **LAW-3 Only what was asked.** No unrequested UI: no counts, notes, tags, filters, or toggles. A
  suggestion voiced as "we could" is a proposal, not a request. Work that was kept is never deleted.
- **LAW-4 The practitioners' words.** Use the term people in the field use ("Multimodal",
  "Language"). Do not invent friendlier paraphrases for standard terms.
- **LAW-5 Kinds are defined by output.** Language, Image, Video, Audio, Embeddings, Reranker.
  Input variants are options inside a family. There is no "Other / custom" kind.
- **LAW-6 Facts come from sources.** Engine flags, defaults, and hardware figures come from the
  engine's own docs or the vendor's specs, are dated, and are never taken from memory. Unknown
  stays unknown.
- **LAW-7 Current generation only.** Catalog entries are the newest version of a family, with a
  stated reason for any exception (Wan 2.2 and FLUX.1 dev are the standing ones).
- **LAW-8 Every flag, uncommented.** The panel lists all flags of the engine as real lines. No
  counts, no filters, no descriptions that only restate the flag name.
- **LAW-9 Safe defaults.** Listen on this machine only, remote code off unless the model needs it.
- **LAW-10 No wrong commands.** Never show a command Modular cannot stand behind. If there is none,
  say so plainly.
- **LAW-11 Never break saved data.** Older data upgrades on read; newer data is preserved and never
  overwritten; retired models keep their meaning.
- **LAW-12 Local only, nothing pushed.** Commits stay local. No deploy from inside the loop.
