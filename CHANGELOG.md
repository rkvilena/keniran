# Changelog

## 1.2.0 - 2026-11-15

TUI-only usability pass; the one-shot `keniran <APP_ID>` CLI remains available and unchanged.

### Added

- A clickable **Check** button beside the App ID input; **Enter** still submits.

### Changed

- The home subtitle now explains how to check: enter the game's Steam App ID,
  then press Enter.
- README documents isolated `pipx` and `uv tool` installs so the `keniran`
  command runs without activating a virtual environment.

### Fixed

- Benchmark databases now ship as package data (`keniran.database`) and load
  through `importlib.resources`, so `pipx`/`uv tool` installs (and any
  non-editable install) can score games instead of failing to find
  `database/*.json`.

## 1.1.2 - 2026-11-15

TUI and shared-renderer refinement; no change to matching, confidence, or scoring.

### Changed

- The matched-benchmark marker is now `🔎` (was `⚡`), with a subdued caption
  under the table explaining that the percentage is match confidence and the
  result compares your system against that benchmark.
- The TUI command box hugs its controls and leaves a blank row before results.

## 1.1.1 - 2026-11-15

TUI layout and Footer cleanup; the one-shot CLI is unchanged.

### Changed

- The home block (wordmark, subtitle, and command box) is centered as one group
  above the docked Footer.
- The Footer shows a single **F1** command-palette hint instead of a duplicate
  menu entry.

## 1.1.0 - 2026-11-13

TUI-only visual redesign of `keniran tui` matching the opencode TUI aesthetic; the one-shot `keniran <APP_ID>` CLI remains available and unchanged.

### Added

- Centered ASCII-art `keniran` wordmark with a left→right gray gradient and a
  compact fallback on short terminals.
- Muted subtitle prompting for the target game's Steam App ID; results replace
  the hero after a check starts.
- Custom near-black `keniran` theme (monochrome gray with a single amber accent),
  now the default.
- `Reset` button and `Esc` keybinding that restore the home screen and clear the
  input and results.

### Changed

- The App ID field submits on **Enter**; the check runs in a background worker
  with a busy status line naming the app id.
- `tokyo-night` remains selectable at runtime through the command palette (Ctrl+P).
- The `Header` is dropped; the `Footer` is kept.

### Removed

- The `Run` button (Enter now submits).

## 1.0.1 - 2026-11-12

The one-shot `keniran <APP_ID>` CLI remains available and unchanged.

### Added

- Redesigned TUI home screen: a Keniran header, a large `keniran` wordmark, the
  tagline "Check whether your PC can run a Steam game.", and a bordered App ID /
  Run command box.
- Dark slate/navy base with a muted lavender highlight and a restrained warm accent.
- Vertical scrolling on the home and results views so short terminals are not clipped.

### Changed

- CPU/GPU requirements joined by `or` are treated as independent alternatives and
  matched separately, so the least demanding alternative that resolves is the one
  scored (meet-any).
- Common vendor aliases normalize on both the requirement and benchmark-database
  sides before matching: NVIDIA ≡ GeForce and AMD ≡ Radeon.

### Fixed

- FC27 false-negative: a GPU requirement like "AMD RX 570 or Nvidia GTX 1050 Ti" was
  scored against a wrong single match; `keniran 4080220` now reports Pass instead of
  84% / Poor.
