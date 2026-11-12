# Active context — v1.0.1/requirement-alternatives

- current task: ALT-001.
- state: feature blueprint ready; no implementation started.
- contract: preserve scalar `GameRequirements.cpu_name` / `gpu_name` and report source text;
  split alternatives with the parser helper and reduce valid benchmark matches in
  `check_game` using the lowest positive target score. Scored `best_guess` remains valid.
- release prerequisite: complete this feature before `v1.0.1/tui-redesign`.
- acceptance commands are verified in `.spec/conventions.md` and each task block.
- open: separator scope is standalone English `or` only; do not expand to commas/slashes.
