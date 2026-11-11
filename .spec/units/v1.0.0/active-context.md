# Active context — v1.0.0 (release)

- current task: unit complete — REL10-001..003 all done.
- last commit: dee3cc2 REL10-002; REL10-003 closed with no commit (verification).
- state: v1.0.0 RELEASE UNIT DONE. Run summary (2026-11-11):
  - Tasks done: TUI-001..004 (0cb0685, 8ed3ff8, ac3645a, 5b8003e), TUI-005
    RESOLVE fix (c76e650), REL10-001 (754313f), REL10-002 (dee3cc2; plan/
    gitignored by design), REL10-003 (no commit).
  - Blocked: none.
  - Gate: host 263 passed + ruff/mypy clean; WSL 262 passed / 1 skipped
    (dev-host guard test, documented environment skip); manual checks: bare
    `keniran` → help exit 0, `--version` → keniran 1.0.0, one-shot
    `keniran 1091500` byte-identical to the 0.2.1 tree, `keniran tui` launches.
  - Interpretation notes: (1) TUI-001's "bare keniran = current help behavior"
    premise was wrong (0.2.1 console actually errored; CliRunner masked it) —
    resolved toward the unit contract's help behavior via TUI-005; help usage
    line now reads `[OPTIONS] [app_id]`. (2) canned Reports fake the
    `check_game` seam (fetch_steam returns SteamRequirements, not Report).
    (3) WSL python default is 3.8-only; loop runs via `.venv-wsl/py311`.
  - Remaining (user-visible, next steps outside .spec): make the repo public /
    create the GitHub release tag v1.0.0 — that is the release's stated purpose
    and is a user action, not a pipeline task.
- state: chores REL10-001..003 all unchecked, each gated on v1.0.0/tui (TUI-001..004).
  Notes: (1) pyproject target `1.0.0` **confirmed** (user 2026-11-11 — first public
  release). (2) Global `.spec/spec.md` §3/§5 already patched by blueprint
  (Planned v1.0.0 shape note + backlog row in-progress); REL10-002's doc sweep must
  stay consistent with it, not regress it.
