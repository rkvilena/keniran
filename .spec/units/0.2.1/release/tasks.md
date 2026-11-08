# Tasks — 0.2.1 (release chores)

- [ ] REL21-001: Version bump to 0.2.1
  depends: -
  gated: 0.2.1/linux-storage, 0.2.1/bench-honesty
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8)
  acceptance:
    `[project] version = "0.2.1"`; `python -m pytest -q` still green (no code
    change in this chore).
    acceptance commands:
      python -m pytest -q
  out-of-scope: changelog file creation (doc sweep is REL21-002); plan/decisions.md
    (also REL21-002)

- [ ] REL21-002: Docs sweep — README + plan/decisions.md
  depends: -
  gated: 0.2.1/linux-storage, 0.2.1/bench-honesty
  files: README.md, plan/decisions.md
  pattern: README.md "Linux support (0.2.0)" section; plan/decisions.md §1/§2/§5 wording
  acceptance:
    README: header line now says it documents **0.2.1**; the "Storage" section's
    scope note is rewritten — the Linux audit no longer measures `/`-only, the
    "wiring the shared helper into the Linux audit is a known follow-up" sentence
    (and its 0.0-degrade description) is removed, replaced by: Linux checks any
    local fixed mount via the shared helper, pseudo-filesystems (tmpfs, squashfs,
    ...) are denylisted Linux-side, same-device mounts dedupe, nothing measurable
    → unverified ⚠ (never 0.0), row shows the chosen mount. A benchmark-honesty
    note is added (fact chains / honesty section): lspci without the pciutils ID
    database yields placeholder names like `Device 008e`; such placeholder-shaped
    names degrade to `unverified ⚠` instead of fuzzy-matching a confident pass.
    No invented capabilities beyond what LSTO-*/HON-* deliver.
    plan/decisions.md: storage rule statements updated to any-mount on **both**
    OSes with the denylist and dedupe recorded; the WSL-smoke backlog entry
    (unnamed-GPU fuzzy-match concern) is marked RESOLVED by 0.2.1 with the
    lookup-entry floor design; 0.2.1 noted with today's date; retired wording
    (`/`-only with 0.0 degrade; unnamed-GPU open concern) marked superseded —
    no contradictory leftovers.
    acceptance commands:
      python -m pytest -q
  out-of-scope: detailed-flow.md / benchmark-db.md (no contradiction expected;
    surgical line fixes only if revision reveals one)

- [ ] REL21-003: Full acceptance gate run for 0.2.1
  depends: -
  gated: 0.2.1/linux-storage, 0.2.1/bench-honesty
  files: (none — verification only)
  pattern: §7 agent loop contract from plan/decisions.md
  acceptance:
    All four gates pass with output quoted in the run log: `python -m ruff format .`,
    `python -m ruff check .`, `python -m mypy`, `python -m pytest -q`; plus the WSL
    loop `wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"` — including
    re-checking that `lspci`-without-pciids placeholder behavior on the WSL box now
    degrades to unverified (HON-001 regression case against real tool output). Any
    failure loops back into the owning feature unit as a RESOLVE; this chore writes no
    code.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"
  out-of-scope: code fixes (they belong to the failing feature unit)
