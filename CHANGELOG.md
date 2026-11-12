# Changelog

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
