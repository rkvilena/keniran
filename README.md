# keniran

> Can I run it? Audit this machine against a Steam game's minimum requirements.

`keniran <APP_ID>` audits the local machine, fetches a Steam game's minimum PC
requirements, and prints a per-component comparison with a bottom-line verdict.

This README documents **1.0.0**. (1.0.0 adds the Textual TUI via `keniran tui`;
the one-shot CLI is unchanged.)

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

## TUI (1.0.0)

`keniran tui` launches a terminal UI that renders the same `Report` as the
one-shot CLI. `keniran <APP_ID>` is unchanged and remains the default — the TUI
is an alternative front end, not a replacement.

Type a Steam App ID and press **Run**. The check runs in a background worker, so
the UI stays responsive; while it runs, a status line names the app id, then the
results area shows:

- the per-component verdict table (required vs your system, result, notes);
- `unverified ⚠` rows, which are excluded from the verdict rather than guessed;
- `⚡` best-guess badges with the match confidence for fuzzy-matched names;
- the single-thread CPU warning when multi-thread performance passes but ST is
  below ~70%;
- the bold verdict percentage at the bottom (or the graceful "No PC
  requirements published" message when a game has none).

Errors — an invalid App ID, a Steam lookup failure, or an unexpected exception —
are shown inline in bold red instead of crashing the app; fix the input and
press Run again in the same session.

The default theme is `tokyo-night`. Themes are runtime-swappable through
Textual's command palette: press `Ctrl+P`, then choose **Theme** (or type a
theme name such as `tokyo-night`).

The TUI accepts an App ID only — there is no title search box. Title search
(`--search`) remains deferred (plan/decisions.md §9), with a TUI `Input` widget
as its natural future home.

## Reading the report

Each component is compared by ratio (yours ÷ required); the verdict is the
worst verified component. A row marked `unverified ⚠` means keniran couldn't
confirm that value and it's excluded from the verdict — keniran never guesses.

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
