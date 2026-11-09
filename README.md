# keniran

> Can I run it? Audit this machine against a Steam game's minimum requirements.

`keniran <APP_ID>` audits the local machine, fetches a Steam game's minimum PC
requirements, and prints a per-component comparison with a bottom-line verdict.

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
