unit-id: 0.2.0
task-prefix: REL

## Goal & Version

Wrap up **0.2.0** (platform support + scoring-semantics generation):
1. Linux hardware audit (second adapter behind the hardware port),
2. RAM/VRAM scored ratios replacing hard caps,
3. any-local-mount storage check (fixes the C:-vs-E: bug),
4. `SystemSpec` model evolution (`platform`, optional `vram_gb`).

Target version string: **0.2.0** (canonical labels everywhere: 0.1.0 / 0.2.0 /
post-0.2.0; retire loose "v1.1"/"v2" language; `v` prefix reserved for git tags only).
This unit coordinates only — it contains no feature implementation.

## Feature Units

| Order | unit-id | One-line scope | Why here |
|---|---|---|---|
| 1 | 0.2.0/model-layout | hardware package split + `SystemSpec` evolution (`platform`, optional vram) | everything else depends on it |
| 2 | 0.2.0/linux-audit | Linux adapter: /proc/lspci/nvidia-smi/vulkaninfo chains → unverified fallback; WSL fixtures | the platform-support core |
| 2 | 0.2.0/ratio-scoring | RAM/VRAM join verdict min(); storage-only shortfall cap | verdict semantics of 0.2.0 |
| 2 | 0.2.0/storage-mounts | any-local-fixed-mount storage check both OSes | parity + Windows bug fix |
| 3 | 0.2.0 (this unit) | docs, version, full gate | after all features |

## Prerequisites

All four feature units MUST be done (all their tasks checked) before the gated chores
below run: REL-001..REL-004 carry `gated:` lines accordingly.
Run semantics ("how does `/run 0.2.0` behave?") are defined by the Release-run contract
in `.spec/conventions.md`.

## Changed Contracts (cross-cutting summary)

See each unit's spec. Global deltas vs 0.1.0: `SystemSpec` (+`platform`, vram
optional, +`storage_used_mount`), verdict = min(CPU, GPU, RAM, VRAM) with storage as
the only shortfall cap, hardware adapter = platform-dispatched package. No CLI surface
changes, no new dependencies.

## Open Questions

- None blocking. Native-Linux CI validation of the GPU chain stays deferred and is
  recorded in the docs sweep (WSL smoke remains the accepted plumbing check).
