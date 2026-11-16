# Tasks — v1.0.0 (release chores)

- [x] REL10-001: Version bump to 1.0.0
  status: done (commit 754313f)
  depends: -
  gated: v1.0.0/tui
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8)
  acceptance:
    `[project] version = "1.0.0"`; `python -m pytest -q` still green (no code
    change in this chore).
    acceptance commands:
      python -m pytest -q
  out-of-scope: changelog file creation (doc sweep is REL10-002);
    plan/decisions.md (also REL10-002)

- [x] REL10-002: Docs sweep — README + plan/decisions.md
  status: done (commit dee3cc2 — README.md tracked; plan/decisions.md updated on
  disk only, gitignored by design)
  depends: -
  gated: v1.0.0/tui
  files: README.md, plan/decisions.md
  pattern: README.md structure from 0.2.1's doc sweep; plan/decisions.md §5/§9 wording
  acceptance:
    README: header line now says it documents **1.0.0**; a new "TUI (1.0.0)"
    section documents `keniran tui` — what it shows (verdict table with all
    honesty semantics: unverified ⚠ rows, ⚡ best-guess badges, ST-warning,
    verdict percentage), how to switch themes via the command palette, and the
    explicit statement that the one-shot CLI remains unchanged/default. No
    invented capabilities beyond what TUI-001..004 deliver (no search box —
    say so if the README's backlog/deferred section mentions it).
    plan/decisions.md: §5 renderer contract extended with the TUI as second
    renderer (one-shot CLI unchanged); §9 backlog updated — the "UI (TUI/web)"
    entry becomes "TUI delivered by 1.0.0; search box still deferred (natural
    home: a TUI Input widget)"; the `--search` deferral entry is marked as still
    deferred by user decision 2026-11-11; 1.0.0 noted with today's date; no
    contradictory leftovers.
    acceptance commands:
      python -m pytest -q
  out-of-scope: global `.spec/spec.md` edits (already patched by blueprint
    2026-11-11 — keep wording consistent, do not regress the in-progress note);
    detailed-flow.md / benchmark-db.md (surgical fixes only if a revision
    reveals a contradiction)

- [x] REL10-003: Full acceptance gate run for v1.0.0
  status: done (no commit — verification chore; run log 2026-11-11, two passes:
  first pass found the bare-`keniran` no-args console failure → RESOLVE loop-back
  fixed as TUI-005 (commit c76e650); re-run all green)
  depends: -
  gated: v1.0.0/tui
  files: (none — verification only)
  pattern: §7 agent loop contract from plan/decisions.md
  acceptance:
    All four gates pass with output quoted in the run log: `python -m ruff format .`,
    `python -m ruff check .`, `python -m mypy`, `python -m pytest -q` (now including
    tests/test_tui.py and tests/test_report_view.py); plus the WSL loop
    `wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"` — Textual pilot
    tests are headless and must pass there unchanged. Also verify the three pinned
    CLI behaviors manually once: `keniran <APP_ID>` one-shot output identical to
    0.2.1's, `keniran tui` launches the TUI, bare `keniran` prints help. Any
    failure loops back into `v1.0.0/tui` as a RESOLVE; this chore writes no code.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"
  out-of-scope: code fixes (they belong to v1.0.0/tui)
