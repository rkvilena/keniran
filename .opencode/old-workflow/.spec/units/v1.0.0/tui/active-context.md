# Active context — v1.0.0/tui

- current task: unit complete — v1.0.0 release run finished 2026-11-11.
- last commit: c76e650 TUI-005 (REL10-003 resolve); release chores closed per the
  release unit's active-context run summary.
- state: v1.0.0/tui DONE except RESOLVE (2026-11-11, from REL10-003 gate run):
  bare `keniran` on the real console exits 2 ("Missing argument 'app_id'") because
  Typer's `no_args_is_help` is ignored in single-command mode — this was ALSO 0.2.1's
  behavior; TUI-001's acceptance assumed "current = help" from a CliRunner test that
  exercises a different parse path than the real console. The unit contract (unit
  spec Changed Contracts + the pinned tests) says bare `keniran` → help. RESOLVE:
  align the console with the contract (print help on no args) — code fix belongs
  here (cli/app.py is TUI-001's file set). REL10-003 re-runs after the fix.
- earlier notes (TUI-004): errors render inline as bold-red Static under ERROR_ID,
  matching cli _fail wording ("Invalid APP_ID..." / "Steam app N was not found" /
  "Unexpected error: ..."); worker uses `exit_on_error=False` so unexpected
  exceptions never kill the app. Recovery proven: same-session valid check after
  an error works. Message-only reports render through the shared renderer unchanged.
