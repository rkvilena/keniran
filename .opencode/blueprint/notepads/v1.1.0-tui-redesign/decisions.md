# Decisions — v1.1.0-tui-redesign

## 2026-11-13 (Plan init)
- Fresh execution: no pre-existing worktrees or `blueprint/*` branches for this plan.
- Only untracked paths in the main checkout were Blueprint artifacts under
  `.opencode/blueprint/**` (drafts, investigations, plans) — expected and preserved.
- Plan worktree created at HEAD: `blueprint/v1.1.0-tui-redesign/_plan`.

## 2026-11-13 (Execution complete)
- All 11 tasks (TUI11-001..006, REL110-001..005) implemented, verified, and merged into `main` via
  fast-forward (`f79f6db` → `adcaacf`). No conflicts at any merge.
- Final gate on `main`: ruff format/check clean, mypy 19 files OK, `pytest -q` 325 passed;
  `keniran --version` → `keniran 1.1.0` (editable install restored to the main checkout).
- All 9 owned worktrees removed (no force) and all 9 `blueprint/v1.1.0-tui-redesign/*` branches deleted
  with `-d` after merge verification. No worktrees/branches remain.
- Deviations disclosed: (1) W6-1 did not run `pip install -e` — deferred to W7-1 to avoid repointing the
  shared venv mid-run; W7-1 then ran it and the install was restored from `main` after the merge.
  (2) The interactive `keniran tui` terminal smoke was replaced by a headless `run_test` smoke and remains
  PENDING USER QA.
- Retries: W1-1 (one: expose a compact-capable gradient builder) and W1-3 (one: correct the spec's task
  table). No task exceeded the retry budget.

## 2026-11-13 (Wave 1 dispositions)
- W1-1 retried once: original implementation only exposed `wordmark_renderable(start, end)`
  (full art hardcoded), which left R7 (compact fallback) unrenderable for the downstream
  hero task (W3-1 may only edit `app.py` + `test_tui.py`). Retry added
  `wordmark_renderable_for(lines, start, end)`; `wordmark_renderable` delegates to it. Commit
  amended so the branch keeps one task commit.
- W1-3 retried once: the spec's task table had swapped W1-1/W1-2 scopes and a wrong Wave
  column, and a self-contradictory Prerequisites paragraph; corrected to match the plan exactly
  (so W7-1 reproduces accurate `tasks.md`). Commit amended.
- Gate commands run in each worktree with `E:/MyProject/test-project/.venv/Scripts/python.exe`.
  `ruff format .` left all 91 files unchanged (no unexpected edits).
