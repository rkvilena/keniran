unit-id: 0.2.1
task-prefix: REL21

## Goal & Version

Land two 0.2.0 follow-ups as **0.2.1** — patch-flavored release: two feature units
plus chores. 0.2.0 itself stays frozen: its units are all done and its README
contract ("This README documents 0.2.0") gets superseded by this release's doc
sweep, not edited.

Features delivered:
1. Linux hardware audit checks any local fixed mount (biggest-free wins) using the
   shared 0.2.0 helper, with a pseudo-filesystem denylist and same-device dedupe
   for Linux partition noise; honest `unverified ⚠` when nothing can be measured;
   mount provenance recorded.
2. Benchmark-match honesty floor: placeholder GPU/CPU names (lspci's `Device 008e`
   without the pciutils ID database — the REL-004 WSL-smoke finding) are rejected
   at lookup entry and degrade to `unverified ⚠` instead of fuzzy-matching onto a
   confident false pass.

## Feature Units

| Order | unit-id | One-line scope | Why here |
|---|---|---|---|
| 1 | 0.2.1/linux-storage | Linux gatherer (denylist + dedupe) wired into `audit()` via the shared helper | closes the storage follow-up |
| 1 | 0.2.1/bench-honesty | placeholder-name floor at lookup → `unverified` instead of confident fuzzy pass | closes the REL-004 honesty finding |
| 2 | 0.2.1 (this unit) | version bump, docs sweep, full gate | after all features |

Order 1 units are parallel-safe: disjoint files (`linux.py`/`test_hardware_linux.py`
vs `benchmarks.py`/`test_benchmarks.py`); neither edits `check_game.py` or models.

## Prerequisites

Both feature units must be fully done (LSTO-001 **and** LSTO-002, HON-001 checked)
before the gated chores below run; each chore carries its `gated:` line. Run
semantics follow the Release-run contract in `.spec/conventions.md`.

## Changed Contracts (cross-cutting summary)

See each feature unit's spec. User-visible deltas vs 0.2.0:
- Storage: Linux went from "`/`-only, `0.0` on failure" to "any local fixed mount,
  unverified when nothing is measurable, mount shown in the row".
- Benchmarks: placeholder-shaped names no longer fuzzy-match into confident passes —
  they show the `unverified ⚠` row and are excluded from the verdict `min()`.

No CLI surface change, no new dependencies, no storage.py/scoring.py edits,
no MatchResult/ComponentRow model edits.

## Open Questions

- None blocking. Native-Linux live validation inherits 0.2.0's deferred posture
  (recorded in the feature unit's Open Questions).
