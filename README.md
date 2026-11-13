# keniran

> Can I run it? Audit this machine against a Steam game's minimum requirements.

`keniran <APP_ID>` audits the local machine, fetches a Steam game's minimum PC
requirements, and prints a per-component comparison with a bottom-line verdict.

This README documents **1.1.0**, a TUI-only visual redesign. It reworks the
`keniran tui` home screen around a near-black monochrome base with a single
amber accent: a centered ASCII-art `keniran` wordmark, Enter-to-submit, and
results that replace the hero. The audit pipeline, the one-shot
`keniran <APP_ID>` CLI, and how `or`-joined requirements are matched are
unchanged.

## Install

Requires Python 3.11 (the project is pinned to it).

From a clone:

```bash
git clone https://github.com/rkvilena/keniran
cd keniran
pip install .
```

This installs the `keniran` command. No virtualenv needed unless you're
developing — see [Developing](#developing) below.

## Usage

```bash
keniran <APP_ID>
```

`APP_ID` is the Steam appid (the number in a store page URL, e.g.
`keniran 1091500`). The first run audits your hardware and caches it in
`generated/system_spec.json`; later runs reuse the cache. Pass
`--refresh-spec` to force a fresh audit.

## TUI (1.1.0)

`keniran tui` launches a terminal UI that renders the same `Report` as the
one-shot CLI. `keniran <APP_ID>` is unchanged and remains the default — the TUI
is an alternative front end, not a replacement.

The home screen is a centered brand hero: the ASCII-art `keniran` wordmark
shaded in a left→right gray gradient, with a small muted subtitle beneath it —
"Can I run it? Enter the target game's Steam App ID to audit this PC." — above
the App ID input and its **Reset** button, grouped in one bordered command box.
A terminal too small for the full six-row wordmark gets a compact four-row
fallback instead, re-applied on resize. The palette is a near-black gray
monochrome with exactly one amber accent (the default theme is `keniran`), and
the home block and results share one vertically scrollable body, so short
terminals scroll long content into view instead of clipping it.

Type a Steam App ID and press **Enter** to submit. The check runs in a
background worker, so the UI stays responsive; while it runs, a status line
names the app id. Results replace the hero: as soon as a status line, a report,
or an error is mounted, the hero steps aside and the results area shows:

- the per-component verdict table (required vs your system, result, notes);
- `unverified ⚠` rows, which are excluded from the verdict rather than guessed;
- `⚡` best-guess badges with the match confidence for fuzzy-matched names;
- the single-thread CPU warning when multi-thread performance passes but ST is
  below ~70%;
- the bold verdict percentage at the bottom (or the graceful "No PC
  requirements published" message when a game has none).

Errors — an invalid App ID, a Steam lookup failure, or an unexpected exception —
are shown inline in bold red instead of crashing the app; fix the input and
press Enter again in the same session.

**Reset** (the button beside the input) or **Esc** anywhere returns to the home
screen: the hero reappears, and the App ID input and the results are cleared,
ready for the next check.

Themes are runtime-swappable through Textual's command palette: press `Ctrl+P`,
then choose **Theme** — the built-ins, including `tokyo-night`, remain
selectable.

The TUI accepts an App ID only — there is no title search box. Title search
(`--search`) remains deferred, with a TUI `Input` widget as its natural future
home.

## Reading the report

Each component is compared by ratio (yours ÷ required); the verdict is the
worst verified component. A row marked `unverified ⚠` means keniran couldn't
confirm that value and it's excluded from the verdict — keniran never guesses.

## How requirements are matched

A CPU or GPU requirement joined by `or` (for example `AMD RX 570 or Nvidia GTX
1050 Ti`) is a list of alternatives, not one name: keniran matches each
candidate independently and scores the **least demanding alternative that
resolves**, because your machine only has to meet one of them (meet-any). The
requirement column still shows the full original string, next to the benchmark
that was actually selected and its confidence badge. If no alternative resolves,
the row degrades to `unverified ⚠` as usual.

Vendor names are normalized to their GPU family on both the requirement and the
benchmark-database side before matching: NVIDIA ≡ GeForce and AMD ≡ Radeon.

This is what fixed the FC27 false negative: `keniran 4080220` now reports
**Pass** instead of the earlier wrong result.

## Requirements & limitations

- Runs on Windows and POSIX hosts (native Linux and WSL2).
- Compares against Steam's **minimum** requirements only; recommended
  requirements are out of scope.
- Hardware facts come from fallback chains per platform. When a value can't
  be verified (e.g. VRAM on some Linux setups), the row degrades to
  `unverified ⚠` rather than fabricating a number. Details:
  [`.spec/spec.md`](.spec/spec.md).

## Developing

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"    # on Windows: .venv\Scripts\pip
```

The editable install points the `keniran` command at your live source tree.
The venv is a contributor-only artifact; end users never need it. On WSL, a
separate `.venv-wsl/` may exist because the distro's system Python is older
than the 3.11 pin requires.

Project engineering — architecture, decision log, per-release specs — lives
in [`.spec/`](.spec/):

- [`.spec/spec.md`](.spec/spec.md) — the project blueprint: goal, architecture,
  data contracts, and what's explicitly out of scope.
- [`.spec/decisions.md`](.spec/decisions.md) — an append-only decision log with
  the rationale and rejected alternatives behind each release.
- [`.spec/units/`](.spec/units/) — per-release unit specs, task lists, and
  working context.
