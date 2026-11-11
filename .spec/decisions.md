# Decision Log — Keniran "Can I Run It?"

Append-only. Newest first within each release block. Every entry inherits the rule from
`plan/decisions.md`: where plan docs conflict with this log, **this log wins**.

---

## Release v1.0.0 (planned; decided 2026-11-11)

- **Versioning rationale locked**: v1.0.0 = the first **public** release — the repo
  goes public and gets its first GitHub release when the UI lands; the 0.1.0–0.2.1
  era was private development and does not count toward public version history.
  pyproject `[project] version` target **confirmed as `1.0.0`** (resolves the
  release unit's Open Question). From 1.0.0 on, semver applies: the CLI contract
  (`keniran <APP_ID>`) and report semantics are the stability promise; breaking
  changes require a major bump. (source: user decision 2026-11-11)
- **Global spec patched at user request (2026-11-11, pre-implementation)**: §3
  gained a "Planned v1.0.0 shape" note (new `tui/` + `rendering/` packages,
  `textual` dep, `keniran tui` entry point, search still deferred); §5 backlog row
  "UI (TUI/web)" marked **in progress as v1.0.0**; header notes the public-release
  versioning convention. REL10-002's doc sweep must not contradict it.
  (source: user request 2026-11-11)
- Release id **v1.0.0** = the UI backlog item made real; feature unit
  `v1.0.0/tui` (prefix `TUI`), release chores prefix `REL10`. The release id
  deliberately leads the pyproject number (currently `0.2.1`) until the REL10-001
  bump lands, per the discussed cadence. (source: user decision 2026-11-11)
- **UI stack = Textual TUI**, chosen over four alternatives by weight + identity +
  ecosystem: tkinter rejected (dated look, theming pain, zero design headroom),
  PyQt6/PySide6 rejected (~60–150MB Qt runtime for a pip utility — violates the
  lightweight-first priority), static-HTML report rejected for this release (lightest
  of all, but cannot ever host a search box due to `file://` CORS — user preferred an
  interactive direction), local web server rejected (heaviest scope: server lifecycle,
  CORS, more deps). Textual: pure Python, terminal-native (fits the tool's CLI
  identity; works under WSL/SSH), same author as Rich so existing rich renderables
  embed directly, MIT, and `textual serve` later gives a browser UI with zero
  rewrite — the "web-UI era" door stays open. (source: user decision 2026-11-11,
  blueprint analysis same day)
- **`--search` stays deferred** through v1.0.0 (user confirmed), despite the backlog
  naming the "UI era" as its trigger — the TUI becomes its natural one-widget home
  later. (source: user decision 2026-11-11)
- **Entry point `keniran tui`; one-shot CLI unchanged and default.** Pinned pitfall:
  adding a second Typer command converts the single-command app into a group,
  breaking `keniran <APP_ID>`; dispatch must preserve `keniran <APP_ID>` (one-shot),
  `keniran tui` (TUI), bare `keniran` (help) — pinned by tests in TUI-001.
  (source: user interview 2026-11-11, blueprint flag)
- **Theme `tokyo-night` default, explicitly non-binding**: themes are
  runtime-swappable via Textual's command palette; a custom "keniran" verdict-colored
  theme and `--theme` persistence are backlog. User explicitly asked for
  reversibility before committing. (source: user decision 2026-11-11)
- **New dependency: `textual`** (exact-pinned to newest stable at TUI-001 time, per
  the repo's fixed-pin convention). No other dep changes. (source: blueprint,
  user-approved stack 2026-11-11)
- **Shared renderer extraction**: `keniran.rendering.report_view` (pure
  Report → rich-renderables functions) replaces the private helpers in
  `cli/app.py`; both CLI and TUI consume it. Keeps the "UIs are renderers of
  Report" contract from duplicating presentation logic across renderers.
  (source: blueprint design, consistent with plan/decisions.md §3)

## Release 0.2.1 (decided 2026-11-08)

- A new patch release **0.2.1** carries the Linux any-local-mount storage follow-up;
  **0.2.0 stays frozen** (done units untouched, feature unit lives at
  `0.2.1/linux-storage`, prefix `LSTO`; release chores prefix `REL21`). Offered the
  user the reopen-0.2.0 option; they chose the fresh release to keep version
  labels canonical. (source: user decision 2026-11-08)
- The WSL-smoke **unnamed-GPU fuzzy-match finding is promoted from backlog into
  0.2.1** as `0.2.1/bench-honesty` (prefix `HON`), parallel-safe with linux-storage
  (disjoint files). (source: user request 2026-11-08)
- Honesty gate placement: **lookup entry, not scoring** — placeholder-shaped names
  are classified model-less *before* Stage 1/2 and return
  `MatchResult(matched_by="unverified")`; `_match_score()` and the ratio pipeline
  stay untouched. Root cause verified in code: `Device 008e` passes
  `has_model_number()` (digits survive), shares one token with a real DB row, and
  its score releases regardless of `score_ratio`. (source: user decision
  2026-11-08 + code audit same day)
- **Placeholder denylist, not a marketing whitelist**: garbage = normalized name
  matching lspci/USB placeholder shapes (`device <hex>`, bare 4+-char hex,
  `unknown device`). Rejected the whitelist approach (require ≥1 marketing token)
  because real names missing from the list would false-degrade to unverified — the
  opposite failure mode. (source: user decision 2026-11-08)
- **`best_guess` stays scorable**: sub-gate fuzzy matches keep releasing scores
  with the confidence badge, as today; only placeholder garbage is rejected.
  Windows dxdiag names unaffected; no existing test expectations change. (source:
  user decision 2026-11-08)
- Linux storage wiring = **reuse the shared helper, no helper edits**:
  `select_storage_free` (STO-001 contract) stays pure and backend-agnostic; all
  Linux-specific filtering lives in the Linux gatherer, mirroring
  `windows.py::_collect_partitions()` — two platforms, same port, no pattern
  change. (source: user decision 2026-11-08)
- **Linux pseudo-filesystem denylist, Linux-side**: `tmpfs` (RAM-sized → inflated
  free space → false PASS), `squashfs` (read-only snap content), `proc`, `sysfs`,
  `devtmpfs`, `efivarfs`, `overlay`, `ramfs` excluded before the helper sees them.
  `fuseblk`/ntfs data partitions deliberately still eligible (low-end dual-boot
  reality). Rejected extending the shared helper with a "writability" concept —
  would reopen frozen STO-001 work for helper logic only Linux needs. (source: user
  decision 2026-11-08)
- **Same-device dedupe**: mounts sharing one block device collapse to the
  mountpoint with the most free space (merged-usr / bind setups present one
  filesystem as several mounts). (source: user decision 2026-11-08)
- **Honesty upgrade on the Linux path**: nothing measurable → `disk_free_gb=None`
  (unverified ⚠) instead of the legacy root-failure `0.0`; `0.0` fabricated a
  number the machine never proved. Windows path already stores None via the
  helper. (source: user decision 2026-11-08)
- **Correction recorded**: 0.2.0 STO-001's expectation that LIN-003 would wire the
  helper into the Linux audit was not implemented (linux.py kept root-only
  `_disk_free_gb`, and `audit()` never set `storage_used_mount`); the README
  honestly labeled it a known follow-up. `0.2.1/linux-storage` realizes the
  deferred wiring. (source: state audit of code + unit ledgers, 2026-11-08)

## Release 0.2.0 (planned; decided 2026-11-08)

- Version labels are canonical, not generational: **0.1.0** (current release), **0.2.0**
  (this scope), **post-0.2.0 backlog** (no invented future versions). Loose "v1/v2"
  language in plan docs gets mapped/retired in the 0.2.0 doc sweep. (source: user decision 2026-11-08)
- Linux support = a **second adapter behind the same port** (`() -> SystemSpec`), not a new
  pattern: `adapters/hardware.py` becomes a package (`__init__.py` facade with unchanged
  `audit`/`load`/`save` signatures, `windows.py` as-is, new `linux.py`), dispatched on
  `sys.platform`. No plugin registry — two platforms, permanent, deterministic. (source: user decision 2026-11-08)
- Linux fact-source chains, each degrading to `unverified ⚠`, never a crash: CPU
  `/proc/cpuinfo`→`lscpu`; RAM `/proc/meminfo` MemTotal→psutil; GPU `lspci`
  (VGA/3D/Display classes)→`nvidia-smi`→`eglinfo`; VRAM `nvidia-smi`→`vulkaninfo`
  device-local heap. Linux adds its own name-cleanup layer (strip `[codename]`, `rev a1`
  noise) so the fuzzy matcher sees PassMark-compatible vocabulary. **No new
  dependencies** (stdlib + psutil + existing toolchain only). (source: user decision 2026-11-08)
- `SystemSpec` gains `vram_gb: float | None` (None → unverified ⚠ row, excluded from the
  verdict min) and `platform: str`; the cache is re-audited when cache platform ≠ current
  OS (protects the shared WSL↔Windows project folder). (source: user decision 2026-11-08)
- **RAM and VRAM become scored ratios** (`user ÷ required`) entering
  `final = min(CPU, GPU, RAM, VRAM)` — replaces §5's hard caps for these two. Rejected the
  fixed 1 GB tolerance idea: proportional leniency falls out of the ratio (15.5/16 GB →
  ~97% Borderline; 4/6 GB VRAM → ~67% Poor, matching the user's Metaphor ReFantazio /
  Gran Trad experience). Unverified components are excluded from min(). (source: user decision 2026-11-08)
- **Storage stays binary**, with fix (b): PASS if **any** local fixed mount has ≥ required
  free space; best mount is displayed; skipped mounts (policy-filtered network mounts)
  are noted, not silent. This also fixes the 0.1.0 Windows bug where only `SYSTEMDRIVE`
  (`C:`) was checked while games live on `E:`. Steam-library detection gets a backlog
  entry, not this release. (source: user decision 2026-11-08)
- `--search` deferred to the web-UI era (folded into the UI backlog entry; the search UX
  only pays off with a front-end for typeahead/browse). (source: user decision 2026-11-08)
- Testing strategy: Linux facts captured as recorded fixtures from WSL (same pattern as
  `dxdiag_sample.txt`); parser tests stay OS-agnostic pure-text runs; end-to-end smoke in
  WSL; documented caveat that WSL GPU visibility ≠ native Linux (`/dev/dxg` bridge, capped
  RAM per `.wslconfig`); native-Linux validation deferred to a future real-Linux CI. (source: user decision 2026-11-08)

## Release 0.1.0 (imported from `plan/decisions.md`, BINDING there)

- Single command, zero interactivity: `keniran <APP_ID> [flags]` → audit (cached) →
  fetch Steam → parse → score → report; every ambiguity resolved deterministically. (source: plan/decisions.md §1)
- v0.1.0 requirement parsing is rules-only (labeled-line parser); LLM adapter is backlog
  behind `llm/base.py` protocol with a defined revisit trigger. (source: plan/decisions.md §2)
- Honesty gate: component names without model numbers are marked `unverified` — never guessed. (source: plan/decisions.md §2)
- Architecture = layered ports & adapters, NOT MVC; CLI/UI are renderers of `Report`. (source: plan/decisions.md §3)
- Hardware audit: `dxdiag /t` once → `generated/system_spec.json` cache; WMI rejected
  (32-bit `AdapterRAM` caps at 4 GB); `--refresh-spec` forces re-audit. (source: plan/decisions.md §4)
- Scoring vs MINIMUM only; CPU = `cpumark`, ST ratio informational (< 0.70 → warning);
  ratio ≥ 1.0 displays as 100%; final ratio = min(CPU, GPU); RAM/VRAM/Storage hard
  pass/fail caps verdict at Fail — **superseded for RAM/VRAM by the 0.2.0 ratio decision**. (source: plan/decisions.md §5)
- SteamDB rejected (Cloudflare-blocked, no API); `appdetails` slim endpoint; per-run
  in-memory cache only; missing requirements → graceful message. (source: plan/decisions.md §6)
- Toolchain pinned exactly; gate order ruff format → ruff check → mypy → pytest. (source: plan/decisions.md §7)
- Databases vendored as-is; version single-sourced in `pyproject.toml`. (source: plan/decisions.md §8)

## Post-0.2.0 backlog — WSL smoke finding (added 2026-11-08)

- **Fuzzy-match honesty threshold on unnamed GPUs:** during the REL-004 WSL smoke,
  `lspci` without the pciutils ID database reported the GPU as `Device 008e` (no
  human-readable name), yet the benchmark matcher still scored it a clean 100% pass
  against the required GPU instead of degrading to `unverified ⚠`. Concern: an
  unnamed/garbage device string can fuzzy-match far enough to produce a confident
  verdict, which sits badly with the honesty gate. Action: define and enforce a
  match-confidence floor for benchmark lookup (e.g. reject matches whose fuzzy score
  or clean-name quality is too low, degrade to unverified), and re-check behavior on
  a native Linux box where real device names exist. **RESOLVED by 0.2.1** (HON-001:
  lookup-entry placeholder floor; regression verified against real `Device 008e`
  output on the WSL box in the REL21-003 run log — see
  `.spec/units/0.2.1/bench-honesty/`). (source: WSL smoke run, app 2679460,
  2026-11-08; resolution 2026-11-08)

## Post-0.2.1 backlog — AMD/Mesa chain completeness (added 2026-11-08)

- **AMD/Mesa GPU/VRAM fallback rungs deferred:** the Linux chain's fallback rungs
  are NVIDIA-shaped (`nvidia-smi`), built from WSL/NVIDIA fixtures; AMD works via
  the `lspci` primary + `vulkaninfo` VRAM, and a pci.ids-less native Linux fails
  loudly (honest crash, not a fake spec). Deferred until a real native-Linux AMD
  failure report exists; candidate rungs (eglinfo/glxinfo, /sys/class/drm) are
  design detail for a future unit spec. (source: user decision 2026-11-08,
  "way later is acceptable")

## Post-v1.0.0 backlog — user test findings (added 2026-11-11)

- **TUI design pass** (next release's feature): v1.0.0 TUI is functional but
  "not clean enough design-wise" — user brings design references (2026-11-12).
  Scope: styling/UX polish of `src/keniran/tui/app.py` (CSS, layout); no
  pipeline/rendering changes. Ship as its own release or fold into the patch
  below — decide when the references land. (source: user testing 2026-11-11)
- **FC27 false-negative bug (correctness; priority over design):**
  `keniran 4080220` printed `84% / Poor` where truth is ~148% → capped 100% Pass.
  Traced offline: (1) `requirements_parser` keeps the whole OR string as one
  `gpu_name` (`"AMD RX 570 or Nvidia GTX 1050 Ti"` → fuzzy best_guess
  `'NVIDIA A40'` @0.75, score 13,900); user GPU 11,718 ÷ 13,900 = 0.843.
  Root fixes: split `Processor:`/`Graphics:` values on " or " into candidates and
  score against the least demanding candidate that resolves (meet-any semantics);
  vendor-alias normalization before fuzzy scoring (`nvidia`↔`geforce`,
  `amd`↔`radeon` — `"Nvidia GTX 1050 Ti"` vs DB `"GeForce GTX 1050 Ti"` scores
  0.759, below the 0.80 gate). Cyberpunk 1091500 worked by luck (whole-string
  match hit `'GeForce GTX 1060'` @1.0). Parked policy question: should a
  below-gate best_guess requirement carry its uncertainty into the verdict line?
  (tweaks 0.2.1's "best_guess stays scorable" decision — user's call). The LLM
  parsing adapter's trigger ("rules-parser accuracy proves poor") technically
  fired, but these rules-level fixes are cheaper; LLM stays backlog.
  (source: user test 2026-11-11 + blueprint offline reproduction)
