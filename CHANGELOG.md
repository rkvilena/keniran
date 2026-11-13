# Changelog

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
