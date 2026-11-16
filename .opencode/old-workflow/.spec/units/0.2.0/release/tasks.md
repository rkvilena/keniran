# Tasks — 0.2.0 (release chores)

- [x] REL-001: Version bump to 0.2.0
  status: done (commit 0fa1860)
  depends: -
  gated: 0.2.0/model-layout, 0.2.0/linux-audit, 0.2.0/ratio-scoring, 0.2.0/storage-mounts
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8)
  acceptance:
    `[project] version = "0.2.0"`; `python -m pytest -q` still green (no code change;
    version string surfaces wherever --version reads it).
    acceptance commands: python -m pytest -q
  out-of-scope: changelog file creation (recorded in REL-002/REL-003 docs sweep)

- [x] REL-002: Update plan/decisions.md to the 0.2.0 record
  status: done (no commit — plan/ is gitignored by design; file updated on disk, verified 183 green)
  depends: -
  gated: 0.2.0/model-layout, 0.2.0/linux-audit, 0.2.0/ratio-scoring, 0.2.0/storage-mounts
  files: plan/decisions.md
  pattern: existing plan/decisions.md structure and tone
  acceptance:
    Header updated: status "BINDING for 0.2.0", date of the update, document no longer
    says "v1"/"v2" generation labels (mapping noted: 0.1.0 current, 0.2.0 this release,
    post-0.2.0 backlog). §5 rewritten to the ratio semantics (RAM/VRAM scored,
    storage-only cap, min-of-all). §4 hardware section gains the package layout and
    platform-dispatch description. §1 gets the any-local-mount storage rule. §9 backlog
    updated: adds Steam-library mount detection (`libraryfolders.vdf`); keeps LLM
    adapter, refined CPU scoring; `--search` deferred with the explicit web-UI-era
    note. All superseded 0.1.0 text either removed or explicitly marked superseded
    (no contradictory leftovers).
    acceptance commands: python -m pytest -q (suite untouched, prove nothing broke)
  out-of-scope: detailed-flow.md / benchmark-db.md rewrites (only if they contradict
  0.2.0 semantics — surgical line fixes allowed there)

- [x] REL-003: README Linux support section
  status: done (commit 9f0766f)
  depends: -
  gated: 0.2.0/model-layout, 0.2.0/linux-audit
  files: README.md (or the repo's root readme file if named differently)
  pattern: existing README structure
  acceptance:
    States Linux support, the fact chains and their honest `unverified ⚠` fallbacks,
    the WSL-vs-native caveat (WSL smoke ≠ native validation proof), and that storage
    checks any local fixed mount. No invented capabilities beyond what units deliver.
    acceptance commands: python -m pytest -q
  out-of-scope: Windows/v0.1.0 content beyond a version note

- [x] REL-004: Full acceptance gate run for 0.2.0
  status: done (commits e286278 + 9fc6934 — gate follow-up fixes; see run log)
  depends: -
  gated: 0.2.0/model-layout, 0.2.0/linux-audit, 0.2.0/ratio-scoring, 0.2.0/storage-mounts
  files: (none — verification only)
  pattern: §7 agent loop contract from plan/decisions.md
  acceptance:
    All four gates pass and their output is quoted in the run log: `python -m ruff
    format .`, `python -m ruff check .`, `python -m mypy`, `python -m pytest -q`; plus
    the WSL loop: `wsl -e bash -lc "cd <repo> && python -m pytest -q"`. Any failure
    loops back into the owning feature unit as a RESOLVE; this chore itself writes no
    code.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"
  out-of-scope: code fixes (they belong to the failing unit)
