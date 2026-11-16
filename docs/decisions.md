# Technical Decisions

This is the maintained record of **why** keniran is built the way it is. It is
the project's documentation: each entry states a decision, the reasoning behind
it, the alternatives that were rejected, and whether the decision is still in
force.

The per-release working artifacts (blueprints, unit specs, run logs, review
briefs) live under [`.opencode/`](../.opencode/): `.opencode/old-workflow/`
holds the archived workflow, and `.opencode/engino/` holds the current one.
Those are process history, not the current contract — this file is.

Keniran is primarily an **agentic-workflow experiment**: a small, real tool used
to exercise an agent-driven development process. That context explains a few
recurring choices below (deterministic, offline-testable pieces; a single
source of truth per fact; honesty over guessing).

Status legend: **Current** (in force), **Superseded** (kept for history, no
longer true), **Deferred** (intentionally not done yet).

---

## Product shape

### One-shot CLI is the default; the TUI is additive

**Status: Current.**

`keniran <APP_ID>` audits the machine, fetches a game's minimum requirements,
and prints a comparison. `keniran tui` launches an interactive terminal UI as an
alternative front end; bare `keniran` prints help. The TUI is explicitly
invoked and never changes the one-shot path.

*Why:* the tool's core promise is a single deterministic command with no
prompts. Interactivity is valuable but optional, so it was added as a second
front end rather than folded into the primary path.

*Rejected:* making the TUI the default (it would break the "one command, zero
interactivity" contract and any scripting use); a command group / subcommand
tree (it would break `keniran <APP_ID>`, so `tui` is dispatched as a reserved
positional value instead).

### Compare against minimum requirements only

**Status: Current.**

The report scores the user's machine against Steam's **minimum** PC
requirements. Recommended requirements are out of scope.

*Why:* the product question is "can I run it?" — a yes/no floor — not "how well
will it run?". Minimum is the honest answer to that question and keeps the
verdict unambiguous. Recommended support is tracked as future work.

---

## Architecture

### Layered ports & adapters, not MVC

**Status: Current.**

```
core/       pure domain: models, requirement parsing, scoring math (no I/O)
adapters/   I/O edges: Steam, hardware audit, benchmark lookup, (future) LLM
services/   orchestration: builds a plain Report from adapters + core
rendering/  pure Report -> rich renderables
cli/        one-shot renderer
tui/        Textual renderer
```

`services/check_game.py` returns a plain `Report` dataclass. The CLI and the TUI
are **just renderers of that same Report**, and both consume the shared pure
renderables in `rendering/report_view.py`, so presentation logic and honesty
semantics are written once.

*Why:* MVC's View layer fits forms, not pipelines. Isolating domain logic from
I/O is what makes the pipeline testable offline and what lets a new front end
(web, etc.) join without touching scoring or parsing.

*Rejected:* MVC (poor fit for a pipeline tool); duplicating presentation logic
per renderer (would let the two UIs drift).

### Vendor the benchmark data; keep it offline

**Status: Current.**

CPU scores come from a vendored PassMark export (`src/keniran/database/cpus2a.json`);
GPU scores from a generated PassMark G3D list
(`src/keniran/database/gpu_db.json`, built by `scripts/scrape_gpu.py`). The
databases are committed and shipped as package data, so scoring never needs the
network and works from an installed wheel as well as a source checkout.

*Why:* scoring must be deterministic and reproducible, and the benchmark data
changes slowly. Vendoring removes a runtime dependency and keeps tests offline.

*Rejected:* scraping benchmark sites at runtime (slow, fragile, network-bound);
using the DirectCompute GPU chart (poor correlation with gaming — G3D is the
gaming-relevant baseline).

---

## Hardware audit

### `dxdiag` on Windows; a fallback chain on Linux/WSL

**Status: Current.**

On Windows, the audit runs `dxdiag /t` once and parses CPU, RAM, GPU, and
dedicated VRAM from the report. On Linux/WSL it walks per-field fallback chains
(`/proc/cpuinfo` → `lscpu`, `/proc/meminfo` → `psutil`, `lspci` → `nvidia-smi`,
`nvidia-smi` → `vulkaninfo`). Platform dispatch lives in the
`adapters/hardware/` package facade.

*Why:* `dxdiag` reports dedicated VRAM correctly, while WMI's `AdapterRAM` is a
32-bit field that caps at 4 GB — wrong for modern cards. Each Linux fact has an
independent fallback so a missing tool degrades only its own field.

*Rejected:* WMI `AdapterRAM` (4 GB cap); a plugin registry (two fixed platforms
don't need one).

*Known limitation:* the Linux path is validated with WSL-recorded fixtures; WSL
is not native Linux (GPU passthrough hides real PCI topology), so native-Linux
validation remains open.

### Cache the audit; re-audit only on demand

**Status: Current.**

The audit result is written to `generated/system_spec.json` (gitignored) and
reused on later runs. `--refresh-spec` forces a fresh audit.

*Why:* auditing is the slowest step and the machine rarely changes between
runs, so caching keeps repeat checks fast. The cache is also invalidated when it
was written on a different OS than the current one, so a shared WSL↔Windows
project folder never mixes specs.

### Degrade to `unverified` instead of guessing

**Status: Current.**

When a value can't be determined (e.g. VRAM on some Linux setups, or a
component name with no model number), the row is marked `unverified ⚠` and
excluded from the verdict rather than fabricated.

*Why:* a wrong number is worse than an admitted gap — it silently corrupts the
verdict. This "honesty gate" runs through the parser, the benchmark lookup, and
the hardware audit.

---

## Requirements & scoring

### Rules-based requirement parsing; the LLM stays deferred

**Status: Current** (LLM adapter **Deferred**).

Steam's `pc_requirements` blocks are stereotyped, so a deterministic
labeled-line parser extracts the targets. A protocol for an LLM-based extractor
exists (`adapters/llm/base.py`) but no implementation ships.

*Why:* the parser is offline, free, and deterministic. The LLM's revisit
trigger — "rules parsing proves poor" — has not clearly fired, and the observed
failures were cheaper to fix at the rules level. The interface is pre-paid so an
LLM adapter stays additive if needed.

### Scoring is a ratio; the verdict is the worst verified component

**Status: Current.**

Each component is compared by ratio (`yours ÷ required`). CPU uses PassMark
`cpumark` (multi-thread); GPU uses G3D mark; RAM and VRAM are capacity ratios.
The final ratio is `min()` across verified components, mapped to bands
(Pass ≥ 100%, Borderline 85–99%, Poor 65–84%, below that Unplayable). A passing
CPU whose single-thread ratio is below ~70% prints an informational warning.

*Why:* ratios give proportional leniency instead of a cliff — 15.5/16 GB RAM
reads as ~97% Borderline rather than a hard Fail. `min()` answers "what is the
bottleneck?".

*Rejected:* hard pass/fail caps for RAM/VRAM (the 0.1.0 behavior) — a fixed
margin flips the verdict abruptly and hides how close the machine was.

### Storage is the only shortfall cap

**Status: Current.**

Free disk space is a direct numeric check against **any** eligible local fixed
mount (the mount with the most free space is shown). A storage shortfall caps
the verdict at Fail; RAM/VRAM shortfalls surface through their ratios instead.

*Why:* a game that doesn't fit genuinely cannot be installed — that is a real
floor, unlike a slightly-low ratio. Checking any mount (not just `C:`) matches
reality, where games often live on a secondary drive.

*Deferred:* reading Steam's `libraryfolders.vdf` to check the mount the game
actually installs to, instead of the best eligible one.

### `or` requirements are alternatives; vendor names are normalized

**Status: Current.**

A requirement like `AMD RX 570 or Nvidia GTX 1050 Ti` is a set of alternatives:
each is matched independently and the **least demanding one that resolves** is
scored (meet-any), because the machine only has to satisfy one. Vendor aliases
are normalized before matching (`NVIDIA` ≡ `GeForce`, `AMD` ≡ `Radeon`).

*Why:* treating the whole string as one name produced a false negative (the
FC27 bug). Meet-any is the correct reading of Steam's wording, and alias
normalization lets the fuzzy matcher see equivalent vendor spellings.

---

## Steam data

### Call the store `appdetails` endpoint; cache in memory only

**Status: Current.**

Requirements come from Steam's unauthenticated `appdetails` endpoint (slim
`filters`), cached in memory for the life of the process. A game with no
published requirements yields a graceful message, not an error.

*Why:* it is the direct source. Disk caching would add staleness questions for
almost no benefit, and SteamDB was rejected (no public API, actively
Cloudflare-blocked, and its data derives from the same endpoints).

*Deferred:* a `--search` title → App ID helper. The natural home is a TUI input
widget; with the one-shot CLI the user supplies the App ID directly.

---

## Release & workflow

### Version is single-sourced in `pyproject.toml`

**Status: Current.**

`pyproject.toml` `[project] version` is the one source of truth; `--version`
reads the installed metadata; `CHANGELOG.md` records releases.

### Development artifacts are archived under `.opencode/`

**Status: Current.**

The workflow's planning and history — blueprints, unit specs, run logs, review
briefs — live in `.opencode/`, not at the repo root. `.opencode/old-workflow/`
is archived; `.opencode/engino/` is the active workflow. This file
(`docs/decisions.md`) is the current, curated record; the `.opencode/` tree is
process history.

*Why:* the project doubles as an agentic-workflow experiment, so the raw process
artifacts are worth keeping — but they are noisy and version-specific, so they
are separated from the documentation a reader actually needs.
