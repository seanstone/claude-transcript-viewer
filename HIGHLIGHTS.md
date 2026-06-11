# Working with Claude — talk highlights

A curated read of three projects' transcripts, mined for moments worth showing an
audience. **93 bookmarks** in total; the full, clickable index is
[`transcripts-html/bookmarks.html`](transcripts-html/bookmarks.html), and every
bookmark deep-links into the rendered session at the exact message.

Links below open the rendered transcript and jump to the moment.

---

## The arc

The three sessions tell one story about the same physical board:

1. **zyro-gnss** — a GNSS board on a Zynq-7000 FPGA. General hardware/FPGA work
   (resource budgets, a real Gray-code FIFO bug, parallel agents auditing the codebase).
2. **meshtastic-lora-rs** — a Rust LoRa radio app; the spine is a 5-stage refactor
   merging two binaries into one shared-code app with web + desktop GUIs.
3. **layout-engine** — the centerpiece. The Zynq↔DDR routing on the zyro-gnss board
   was too painful in KiCad, so the work was **spun out into a brand-new repo** and a
   from-scratch PCB layout tool driven by a *screenshot-iterate visual loop*. This is
   where the visual-calibration story lives. (Two sessions: a short "run 1" and the
   66k-line main session.)

> Note: layout-engine is a **topical** continuation of zyro-gnss — same board, work
> moved into a new repo — not a literal session resume. See the bottom of this file.

---

## Theme 1 — Planning large goals & scoping

The strongest planning beats are about *what not to build*.

- **[Scoping the PCB sandbox](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-9a558698-3792-40f2-9704-c5112db5dda4)** — Claude's opening pushback frames the whole project: *"scoping it tightly to just the Zynq↔DDR region is the key move, since building a real PCB CAD from scratch would be a black hole."* Don't build a DRC engine; defer electrical length; export once instead of parsing KiCad.
- **Single-binary dual-GUI architecture plan** (meshtastic) and **Sean refines the plan** — a clean example of the human tightening an AI-proposed staged refactor before any code is written.
- **Design the LLM-in-router loop** — planning a subagent runtime-planner with a tool budget and a rollback invariant.

## Theme 2 — The visual-calibration story (the heart of the talk)

The project's premise is that Claude can't see coordinates well, so it must *look* at
renders. Getting that loop trustworthy took real calibration — and Claude's most candid
self-assessment of the whole corpus.

- **[Asking Claude to route like it thinks](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-9b364f30-a679-448b-8801-9ccfc1d653b1)** → Reverse-engineering its own manual-routing intuition → the **strand-aware scheduler breakthrough** where the lesson emerges from simulation instead of being hard-coded.
- **["I got the ranking wrong"](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-9f3391f8-6e16-4639-bf36-81043229d57b)** — an honest scorecard: Claude's difficulty predictions were essentially backwards. *"Scary numbers ≠ structural truth. I substituted a metric for structural truth."* Followed by **Naming its own failure pattern**.
- **[Five-render readability table](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-0113ee9d-e5b0-41eb-a252-dc611f8b86c4)** — the empirical core: render the same board at five window sizes to find what's actually countable by eye vs. gestalt-only.
- **[Calibration codified to docs](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-05d9d8e1-94b4-46be-b237-bb052cd9138a)** — the standard, written down: *render at ~800px / ~16mm, crosshair k≈0.40, defer exact counts to numeric.*
- **[The coordinate-free cursor loop](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-49ec1b9a-7d8b-4e2f-9c0d-429ed51924d3)** — Sean states the interaction they converged on: *"Place the cursor at some landmark → look → move m steps → look → move n steps … it doesn't have to one-shot."*
- Supporting beats: **"I literally can't read this render"**, **800px hid the bug** (the agent's own downscaled render concealed a defect the human saw at full res), **Zoomed render reveals rail collapse**, **0.04mm teeth read off-screen**.

## Theme 3 — Honest self-assessment

A recurring, demo-worthy pattern: Claude grading itself and *shipping the failure*.

- **Honest 15-lane failure** — ships a failing attempt with 77 DRC violations and a candid writeup instead of hiding it.
- **Why earlier runs faked 15/15** / **Cosmetic 15/15 caught by eye** — Claude catches that a "passing" score was an artifact, not a real solution.
- **[I was wrong, I killed its work](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-11a29d94-dea7-4346-adbf-2cdb7d896fec)** — a striking human-side moment of accountability in the collaboration.
- **Admitting the env's limits** (meshtastic) — Claude declines to fake a browser test it couldn't actually run.

## Theme 4 — Human↔AI collaboration patterns

- **[Three cooperating layers](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-a8c48fc9-5443-4103-a56d-4336f8feb856)** — Claude articulates the division of labor (human intent / tool primitives / AI composition): *"What I don't do: invent geometry out of thin air. The DSL has to expose the primitive… or I can't compose the directive."* The conceptual heart of the whole collaboration.
- **Draw expected before testing** and **Sean reveals his planning method** — the human teaching working style, not just requirements.
- **Conceding the 45-vs-135 geometry argument** — Claude reverses its position after Sean hand-draws the solution.
- **Restart from blank, end in mind** — Sean's mentoring: *"A negative result is normal… restart, keeping the end goal in mind."*

## Theme 5 — Debugging breakthroughs

Great "war story" slides:

- **The dirCode slot collision** — a routing regression bisected to a one-line hash collision (`dirCode(1,1)=8 == DIR_NONE=8`) silently conflating A* states.
- **[135,940 log lines stall the server](transcripts-html/-home-en-meshtastic-lora-rs/3ab43d01-eea0-4141-a20d-61aa0d24d89e.html#msg-e52d6090-c86b-40b9-b359-1f596b039588)** (meshtastic) — blocking `eprintln!` calls choke the async runtime; the split-runtime fix lands 10 Hz with zero stalls.
- **[100x speedup: the agent-render tax](transcripts-html/-Users-en-Developer-layout-engine/7ba4f33e-6fd1-49a2-99b0-f6b420016302.html#msg-a7e85da0-9e1f-4d0a-910f-c6059a0fed28)** — 6000ms → 51ms replan; the cost of rendering *for the agent* becomes the bottleneck.
- **Stale obstacle cache blocks push**, **Two state models fighting**, **Fix works, browser cached old code** — classic "the bug isn't where you think" moments.
- **[Parallel agents review codebase](transcripts-html/-home-en-zyro-gnss/8be34b12-9fb0-47e9-95f2-b8af7f0026da.html#msg-c2f8b3f7-219f-4045-8a75-a19ba799890c)** (zyro) — fan-out review that surfaces a **real Gray-code FIFO bug**.

---

## If you only show five slides

1. **Scoping the PCB sandbox** — AI talking the human *out* of over-building.
2. **Three cooperating layers** — the human/tool/AI division of labor, stated plainly.
3. **"I got the ranking wrong"** — honest self-assessment; metric ≠ truth.
4. **The coordinate-free cursor loop** — the interaction model they invented together.
5. **135,940 log lines stall the server** — a satisfying, legible debugging win.

---

## Appendix — your two questions

**Was layout-engine a continuation of zyro-gnss?** *Topically, yes; technically, no.*
The main layout-engine session opens by pointing at the zyro-gnss KiCad files
(`/Users/en/Developer/zyro-gnss/HW/lib/...`) and Sean says *"I have a new git repo set
up in /Users/en/Developer/layout-engine/ … our new working space."* So the painful
Zynq↔DDR routing sub-problem of the zyro-gnss board was spun out into a fresh repo and a
fresh session — not a `--resume`/compaction fork of the old session.

**Can the lost zyro-gnss transcript be restored from HTML?** *Partially.* The JSONL for
session `a323010b` is gone from `~/.claude`, but its rendered
`transcripts-html/-Users-en-Developer-zyro-gnss/a323010b-….html` (35.7 MB) survives, so
the **conversation content is readable and re-extractable**. A faithful JSONL
restoration is **not** possible: that HTML was rendered before the anchor feature, so it
has no message UUIDs/parent links/token usage, tool results were truncated at 8 KB, and
attachments/images were dropped. You can recover *what was said*, not the exact
structured transcript.
