# Tasks — v1.0.1 release chores

- [ ] REL101-001: Version bump to 1.0.1
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8); v1.0.0 REL10-001
  context: .spec/units/v1.0.0/tasks.md
  acceptance:
    `[project] version = "1.0.1"`; `python -m pytest -q` passes. No dependency or
    tool configuration changes in this chore.
    acceptance commands:
      python -m pytest -q
  out-of-scope: feature code, changelog, README/plan edits, tag creation
  status: blocked: pending-feature (v1.0.1/requirement-alternatives incomplete: ALT-001 blocked: failed-review; ALT-003 blocked: depends-on ALT-001)

- [ ] REL101-002: Add concise 1.0.1 changelog entry
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: CHANGELOG.md
  pattern: new scaffold; concise Markdown release notes grouped under Added / Changed / Fixed
  context: README.md, .spec/units/v1.0.1/spec.md
  acceptance:
    Create `CHANGELOG.md` with a `1.0.1` release heading and entries describing the
    OR-alternative matching correction and TUI redesign; do not claim unshipped search,
    persistence, or scoring-policy changes. `python -m pytest -q` passes.
    acceptance commands:
      python -m pytest -q
  out-of-scope: version bump, README or plan/decisions edits, release tag
  status: blocked: pending-feature (v1.0.1/requirement-alternatives incomplete: ALT-001 blocked: failed-review; ALT-003 blocked: depends-on ALT-001)

- [ ] REL101-003: Docs sweep — README + canonical plan decisions
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: README.md, plan/decisions.md
  pattern: README.md v1.0.0 TUI section; plan/decisions.md amendment structure
  context: README.md, plan/decisions.md, .spec/decisions.md
  acceptance:
    README identifies 1.0.1 as the intended first public release and documents the
    refreshed TUI hierarchy/palette/vertical-scroll behavior, the one-shot CLI remaining
    available, and CPU/GPU `or` plus vendor-alias matching. Update the FC27 example to
    the corrected Pass only if the shipped offline regression establishes it. The
    canonical plan records a dated v1.0.1 amendment superseding its previous first-public
    target and removes contradictory v1.0.0-in-progress wording. `python -m pytest -q`
    passes. Note: `plan/` is gitignored; verify its on-disk edit separately.
    acceptance commands:
      python -m pytest -q
  out-of-scope: global `.spec/spec.md` edits; feature implementation; changelog; tag
  status: blocked: pending-feature (v1.0.1/requirement-alternatives incomplete: ALT-001 blocked: failed-review; ALT-003 blocked: depends-on ALT-001)

- [ ] REL101-004: Full v1.0.1 acceptance run
  depends: REL101-001, REL101-002, REL101-003
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: (none — verification only)
  pattern: `.spec/conventions.md` acceptance commands; v1.0.0 REL10-003 WSL loop
  context: .spec/conventions.md, .spec/units/v1.0.1/spec.md, .spec/units/v1.0.0/tasks.md, pyproject.toml
  acceptance:
    Host ruff format/check, mypy, and all pytest tests pass. The WSL fixture loop passes
    with only environment-documented skips. Refresh editable-install metadata as needed;
    verify `keniran --version` reports 1.0.1. The
    offline FC27 regression asserts the meet-any result; existing CLI tests keep
    `keniran <APP_ID>` one-shot; and a manual TUI smoke starts `keniran tui`, shows
    the redesigned home screen, and exits cleanly with Ctrl+Q. Quote outputs in the run
    log. Any failure returns to the relevant feature unit as a RESOLVE; this task writes
    no code.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      wsl -e bash -lc "cd /mnt/e/MyProject/test-project && .venv-wsl/py311/bin/python -m pytest -q"
      keniran --version
      keniran tui
  out-of-scope: code fixes, documentation edits, tag creation
  status: blocked: pending-feature (v1.0.1/requirement-alternatives incomplete: ALT-001 blocked: failed-review; ALT-003 blocked: depends-on ALT-001)

- [ ] REL101-005: Create annotated v1.0.1 tag
  depends: REL101-004
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: (none — release metadata only)
  pattern: annotated release tag; no prior tag format is established in the repo
  context: .spec/units/v1.0.1/spec.md, .spec/units/v1.0.1/tasks.md
  acceptance:
    Create local annotated tag `v1.0.1` at the fully accepted release commit, with
    message `Keniran v1.0.1`; do not move or overwrite an existing tag. Verify it
    resolves to the accepted commit.
    acceptance commands:
      git tag -a v1.0.1 -m "Keniran v1.0.1"
      git show-ref --verify refs/tags/v1.0.1
  out-of-scope: pushing the tag or publishing a GitHub release (user-controlled action)
  status: blocked: pending-feature (v1.0.1/requirement-alternatives incomplete: ALT-001 blocked: failed-review; ALT-003 blocked: depends-on ALT-001)
