# Active context — v1.0.0/tui

- current task: none — unit created by blueprint 2026-11-11, awaiting `/run v1.0.0/tui`.
- state: tasks TUI-001..004 all unchecked. Implementation notes: (1) the
  Typer-single-command vs group pitfall (unit spec Changed Contracts) is the first
  thing to resolve in TUI-001 — pin the three CLI behaviors with tests before adding
  any command surface. (2) `textual` version pin is chosen at TUI-001 time (newest
  stable; do not copy a guessed version). (3) Theme `tokyo-night` is provisional —
  swappable via palette without touching tasks.
