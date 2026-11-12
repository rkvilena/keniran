unit-id: v1.0.1
task-prefix: REL101

## Goal & Version

Prepare Keniran **v1.0.1** as the first intended public release, preserving the completed
v1.0.0 units as frozen local history. This release-specific decision supersedes the
global blueprint's earlier `v1.0.0` first-public target; the global spec itself remains
unchanged. The release fixes the FC27 false-negative caused by
OR-listed hardware requirements and fuzzy vendor-name mismatches, then gives the Textual
TUI a cleaner, responsive visual design inspired by the user's Bagels terminal reference.
The one-shot CLI and existing best-guess confidence policy remain in place.

## Feature Units

| Order | unit-id | One-line scope | Why here |
|---|---|---|---|
| 1 | v1.0.1/requirement-alternatives | Match CPU/GPU `or` alternatives independently, use meet-any semantics, normalize vendor aliases, and pin the FC27 regression | Correctness issue is the user's priority and should be fixed before the visual pass |
| 2 | v1.0.1/tui-redesign | Polish the Textual home screen, palette, layout, and vertical responsiveness without changing pipeline/report behavior | Makes the already-functional TUI feel intentional after correctness is addressed |

The order is deliberate and linear; do not run the TUI redesign before the matching fix.

## Prerequisites

`v1.0.1/requirement-alternatives` must be complete before
`v1.0.1/tui-redesign` starts. Both feature units must be complete before any release
chore runs. Release-run ordering follows `.spec/conventions.md`.

## Changed Contracts

- A CPU or GPU requirement containing alternatives joined by `or` is evaluated as
  separate candidates. The machine needs to meet at least one listed alternative;
  compare against the least demanding candidate that resolves to a valid benchmark
  match. If none resolves, retain the current unverified behavior.
- Normalize common vendor aliases (`NVIDIA`/`GeForce`, `AMD`/`Radeon`) before fuzzy
  benchmark matching so vendor wording alone does not push an otherwise matching model
  below the confidence gate.
- Preserve v0.2.1's policy: a `best_guess` match remains scorable and is disclosed with
  its existing ⚡ confidence badge. This release does not make the verdict itself
  uncertain solely because a match is below the confidence threshold.
- The TUI remains an additive renderer; `keniran <APP_ID>` and shared report semantics
  remain unchanged. The redesign's target mood is a dark slate/navy base, muted lavender
  as the primary highlight, and a restrained warm accent. The home screen should show a
  clear Keniran title/header, a large `keniran` wordmark with a short compatibility
  tagline, and the existing App ID / Run controls as the primary command box. Retain
  horizontal usability and allow vertical scrolling when terminal height is constrained.
- Version target: `pyproject.toml` `[project] version = "1.0.1"`.
- Public-release target: v1.0.1 is the first public version; v1.0.0 remains completed
  but unpublished local history.

## Open Questions

- Exact color values, spacing, and compact-terminal breakpoint are intentionally not
  fixed without a precise mockup. Assumption: follow the reference's visual mood rather
  than reproduce its layout pixel-for-pixel; use Textual's responsive layout and
  vertical scrolling rather than clipping content.
- Publishing the GitHub release requires user-controlled repository visibility and
  credentials; this unit prepares and verifies a local annotated `v1.0.1` tag only.
