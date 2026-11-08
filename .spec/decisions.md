# Decision Log — Keniran "Can I Run It?"

Append-only. Newest first within each release block. Every entry inherits the rule from
`plan/decisions.md`: where plan docs conflict with this log, **this log wins**.

---

## Release 0.2.0 (planned; defined in interview 2026-11-08)

- Version labels are canonical, not generational: **0.1.0** (current release), **0.2.0**
  (this scope), **post-0.2.0 backlog** (no invented future versions). Loose "v1/v2"
  language in plan docs gets mapped/retired in the 0.2.0 doc sweep. (source: user interview 2026-11-08)
- Linux support = a **second adapter behind the same port** (`() -> SystemSpec`), not a new
  pattern: `adapters/hardware.py` becomes a package (`__init__.py` facade with unchanged
  `audit`/`load`/`save` signatures, `windows.py` as-is, new `linux.py`), dispatched on
  `sys.platform`. No plugin registry — two platforms, permanent, deterministic. (source: user interview 2026-11-08)
- Linux fact-source chains, each degrading to `unverified ⚠`, never a crash: CPU
  `/proc/cpuinfo`→`lscpu`; RAM `/proc/meminfo` MemTotal→psutil; GPU `lspci`
  (VGA/3D/Display classes)→`nvidia-smi`→`eglinfo`; VRAM `nvidia-smi`→`vulkaninfo`
  device-local heap. Linux adds its own name-cleanup layer (strip `[codename]`, `rev a1`
  noise) so the fuzzy matcher sees PassMark-compatible vocabulary. **No new
  dependencies** (stdlib + psutil + existing toolchain only). (source: user interview 2026-11-08)
- `SystemSpec` gains `vram_gb: float | None` (None → unverified ⚠ row, excluded from the
  verdict min) and `platform: str`; the cache is re-audited when cache platform ≠ current
  OS (protects the shared WSL↔Windows project folder). (source: user interview 2026-11-08)
- **RAM and VRAM become scored ratios** (`user ÷ required`) entering
  `final = min(CPU, GPU, RAM, VRAM)` — replaces §5's hard caps for these two. Rejected the
  fixed 1 GB tolerance idea: proportional leniency falls out of the ratio (15.5/16 GB →
  ~97% Borderline; 4/6 GB VRAM → ~67% Poor, matching the user's Metaphor ReFantazio /
  Gran Trad experience). Unverified components are excluded from min(). (source: user interview 2026-11-08)
- **Storage stays binary**, with fix (b): PASS if **any** local fixed mount has ≥ required
  free space; best mount is displayed; skipped mounts (policy-filtered network mounts)
  are noted, not silent. This also fixes the 0.1.0 Windows bug where only `SYSTEMDRIVE`
  (`C:`) was checked while games live on `E:`. Steam-library detection gets a backlog
  entry, not this release. (source: user interview 2026-11-08)
- `--search` deferred to the web-UI era (folded into the UI backlog entry; the search UX
  only pays off with a front-end for typeahead/browse). (source: user interview 2026-11-08)
- Testing strategy: Linux facts captured as recorded fixtures from WSL (same pattern as
  `dxdiag_sample.txt`); parser tests stay OS-agnostic pure-text runs; end-to-end smoke in
  WSL; documented caveat that WSL GPU visibility ≠ native Linux (`/dev/dxg` bridge, capped
  RAM per `.wslconfig`); native-Linux validation deferred to a future real-Linux CI. (source: user interview 2026-11-08)

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
