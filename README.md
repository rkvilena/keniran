# keniran

> Can I run it? Audit this machine against a Steam game's minimum requirements.

`keniran <APP_ID>` audits the local machine, fetches a Steam game's minimum PC
requirements, and prints a per-component comparison with a bottom-line verdict.

Keniran doubles as an **agentic-workflow experiment** — a small, real tool used
to exercise an agent-driven development process. The technical decisions behind
it are recorded in [`docs/decisions.md`](docs/decisions.md); the workflow's
development artifacts are archived in [`.opencode/`](.opencode/). Release
history is in [`CHANGELOG.md`](CHANGELOG.md).

## Install

Requires Python 3.11 (the project is pinned to it). From a clone, choose either
pipx or uv to install Keniran in an isolated environment and make the `keniran`
command available on PATH:

```bash
git clone https://github.com/rkvilena/keniran
cd keniran
pipx install --python 3.11 .
# or:
uv tool install --python 3.11 .
```

After installation, run `keniran tui` or `keniran <APP_ID>` from a terminal;
you do not need to activate the tool's environment. pipx or uv must be
installed first. For contributor setup, see [Developing](#developing) below.

## Usage

```bash
keniran <APP_ID>
```

`APP_ID` is the Steam appid (the number in a store page URL, e.g.
`keniran 1091500`). The first run audits your hardware and caches it in
`generated/system_spec.json`; later runs reuse the cache. Pass
`--refresh-spec` to force a fresh audit.

## TUI

`keniran tui` launches a terminal UI that renders the same `Report` as the
one-shot CLI. `keniran <APP_ID>` is unchanged and remains the default — the TUI
is an alternative front end, not a replacement.

The home screen is a centered brand hero: the ASCII-art `keniran` wordmark
shaded in a left→right gray gradient, with a small muted subtitle beneath it —
“Can I run it? Enter the game's Steam App ID, then press Enter to check this PC
against its minimum requirements.” — above the App ID input and its **Check**
and **Reset** buttons, grouped in one bordered command box.
A terminal too small for the full six-row wordmark gets a compact four-row
fallback instead, re-applied on resize. The palette is a near-black gray
monochrome with exactly one amber accent (the default theme is `keniran`), and
the home block and results share one vertically scrollable body, so short
terminals scroll long content into view instead of clipping it.

Type a Steam App ID and press **Enter** or click **Check** to submit. The check
runs in a background worker, so the UI stays responsive; while it runs, a
status line names the app id. Results replace the hero: as soon as a status
line, a report, or an error is mounted, the hero steps aside and the results
area shows:

- the per-component verdict table (required vs your system, result, notes);
- `unverified ⚠` rows, which are excluded from the verdict rather than guessed;
- `🔎` benchmark-match markers with a match-confidence percentage; the result
  compares your system with that benchmark;
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

Themes are runtime-swappable through Textual's command palette: press `F1`,
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

## Requirements & limitations

- Runs on Windows and POSIX hosts (native Linux and WSL2).
- Compares against Steam's **minimum** requirements only; recommended
  requirements are out of scope.
- Hardware facts come from fallback chains per platform. When a value can't
  be verified (e.g. VRAM on some Linux setups), the row degrades to
  `unverified ⚠` rather than fabricating a number. Details:
  [`docs/decisions.md`](docs/decisions.md).

## Developing

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"    # on Windows: .venv\Scripts\pip
```

The editable install points the `keniran` command at your live source tree.
The venv is a contributor-only artifact; end users never need it. On WSL, a
separate `.venv-wsl/` may exist because the distro's system Python is older
than the 3.11 pin requires.

## Documentation

- [`docs/decisions.md`](docs/decisions.md) — the technical decision record:
  what was chosen, why, and what was rejected.
- [`CHANGELOG.md`](CHANGELOG.md) — per-release history.
- [`.opencode/`](.opencode/) — the workflow's development artifacts
  (blueprints, unit specs, run logs). `.opencode/old-workflow/` is archived;
  `.opencode/engino/` is the active workflow.
