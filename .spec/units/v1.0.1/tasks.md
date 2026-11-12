# Tasks — v1.0.1 release chores

- [ ] REL101-001: Version bump to 1.0.1
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8); v1.0.0 REL10-001
  context: pyproject.toml, .spec/units/v1.0.0/tasks.md
  acceptance:
    `[project] version = "1.0.1"`; `python -m pytest -q` passes. No dependency or
    tool configuration changes in this chore.
    acceptance commands:
      python -m pytest -q
  out-of-scope: feature code, changelog, README/plan edits, tag creation

- [ ] REL101-002: Add concise 1.0.1 changelog entry
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: CHANGELOG.md
  pattern: new scaffold; concise Markdown release notes, grouped under Added / Changed / Fixed
  context: README.md, .spec/units/v1.0.1/spec.md
  acceptance:
    Create `CHANGELOG.md` with a `1.0.1` release heading and entries describing the
    FC27/OR-alternative matching correction and TUI redesign; do not claim unshipped
    search, persistence, or scoring-policy changes. `python -m pytest -q` passes.
    acceptance commands:
      python -m pytest -q
  out-of-scope: version bump, README or plan/decisions edits, release tag

- [ ] REL101-003: Docs sweep — README + canonical plan decisions
  depends: -
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: README.md, plan/decisions.md
  pattern: README.md v1.0.0 TUI section; plan/decisions.md amendment structure
  context: README.md, plan/decisions.md, .spec/decisions.md
  acceptance:
    README identifies the 1.0.1 release and documents the refreshed TUI mood/home
    screen, vertical-scroll behavior, and the CLI remaining available. Explain that
    `or`-listed CPU/GPU requirements are alternatives and that vendor aliases are
    normalized; update the FC27 example to the corrected Pass result only if the
    shipped regression test establishes it. Canonical plan records a dated 1.0.1
    amendment superseding the old first-public-version note, and updates backlog or
    delivered sections without contradictory 1.0.0-in-progress wording. `python -m
    pytest -q` passes. Note: `plan/` is gitignored; verify its on-disk edit separately.
    acceptance commands:
      python -m pytest -q
  out-of-scope: global `.spec/spec.md` edits; feature implementation; changelog; tag

- [ ] REL101-004: Full v1.0.1 acceptance run
  depends: REL101-001, REL101-002, REL101-003
  gated: v1.0.1/requirement-alternatives, v1.0.1/tui-redesign
  files: (none — verification only)
  pattern: `.spec/conventions.md` acceptance commands; v1.0.0 REL10-003 WSL loop
  context: .spec/conventions.md, .spec/units/v1.0.1/spec.md, .spec/units/v1.0.0/tasks.md
  acceptance:
    Host gates pass: ruff format, ruff check, mypy, and all pytest tests. WSL fixture
    loop passes with only environment-documented skips. Verify `--version` reports
    1.0.1; the offline FC27 regression test asserts the expected meet-any result;
    existing CLI tests keep `keniran <APP_ID>` one-shot; and a manual TUI smoke
    starts `keniran tui` and displays the redesigned home screen. Quote outputs in the
    run log. Any failure
    returns to the relevant feature unit as a RESOLVE; this task writes no code.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      wsl -e bash -lc "cd /mnt/e/MyProject/test-project && .venv-wsl/py311/bin/python -m pytest -q"
  out-of-scope: code fixes, documentation edits, tag creation

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
      git show-ref --verify refs/tags/v1.0.1
  out-of-scope: pushing the tag or publishing a GitHub release (user-controlled action)
