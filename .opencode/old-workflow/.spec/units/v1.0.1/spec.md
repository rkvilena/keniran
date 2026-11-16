unit-id: v1.0.1
task-prefix: REL101

## Goal & Version

Prepare Keniran **v1.0.1** as the intended first public release, preserving the completed
v1.0.0 units as frozen, unpublished local history. This release-specific decision
supersedes the earlier first-public target recorded in the global blueprint; the global
spec itself remains unchanged. v1.0.1 fixes the FC27 false-negative caused by OR-listed
hardware requirements and vendor-name fuzzy matching, then polishes the Textual TUI using
the user's Bagels terminal screenshot as visual inspiration. The one-shot CLI remains
available and unchanged in behavior.

## Feature Units

| Order | unit-id | One-line scope | Why here |
|---|---|---|---|
| 1 | v1.0.1/requirement-alternatives | Split CPU/GPU OR alternatives internally, apply vendor-alias normalization, choose the least demanding resolvable alternative, and pin FC27 regression | Correctness is the user's priority and should land before design polish |
| 2 | v1.0.1/tui-redesign | Give the Textual home screen a branded visual hierarchy, reference-inspired palette, and short-terminal vertical responsiveness | Improves the visual quality of the existing TUI without changing its pipeline or report semantics |

The sequence is intentional and linear; do not start the TUI redesign before the matching
feature is complete.

## Prerequisites

`v1.0.1/requirement-alternatives` must be complete before
`v1.0.1/tui-redesign` starts. Both feature units must be complete before any release chore
runs. Cross-unit execution follows `.spec/conventions.md`.

## Changed Contracts

- `GameRequirements.cpu_name` and `.gpu_name` remain strings containing the cleaned
  original requirement text; no public model/schema change. The pipeline splits
  standalone `or` alternatives internally for matching, evaluates each independently,
  and uses the least demanding candidate with a positive benchmark score. A below-gate
  `best_guess` with a score is still resolvable/scorable; unmatched or unscorable
  candidates are ignored. If no candidate resolves, preserve the current unverified
  behavior. Reports continue showing the original full OR requirement in `required_value`
  and disclose the selected benchmark name/confidence as today.
- Normalize the paired vendor terms `NVIDIA`/`GeForce` and `AMD`/`Radeon` consistently
  for requirement probes and database names before exact/fuzzy comparison.
- Preserve the v0.2.1 confidence policy: below-gate `best_guess` matches remain scorable
  and visible with the ⚡ badge; this release does not qualify the verdict solely due to
  match confidence.
- TUI redesign only: use a dark slate/navy base, muted lavender as primary highlight,
  and restrained warm accent; show a clear Keniran title/header, large `keniran`
  wordmark, a short compatibility tagline, and the App ID/Run controls as the main
  command box. Preserve the existing worker, errors, shared report renderables, and
  one-shot CLI. Maintain horizontal usability and allow vertical scrolling when terminal
  height is constrained. Keep `tokyo-night` as the default Textual theme and retain
  runtime theme switching.
- Version target: `pyproject.toml` `[project] version = "1.0.1"`; this is the first
  intended public version while v1.0.0 remains unpublished local history.

## Open Questions

- Exact CSS color values, spacing, and compact-height breakpoint are left flexible because
  the reference is a mood/layout reference, not a pixel mockup. Assumption: choose
  accessible values within the agreed palette and prefer scrolling over clipping.
- GitHub publication/push remains user-controlled; the release unit prepares a local
  annotated `v1.0.1` tag after verification.
