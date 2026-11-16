# Active context — 0.2.1/bench-honesty

- current task: unit complete — HON-001 done.
- last commit: 2abb3aa HON-001 (reviewer-approved; suite 235 green, ruff/mypy clean).
- state: bench-honesty unit DONE. Notes: (1) tests/test_benchmarks.py is a NEW
  module (the spec filenames pre-existing suite is test_benchmark_lookup.py —
  untouched, green). (2) Recorded rule: bare single-token names are placeholder
  only with hex letter [a-f] or 0x prefix — pure decimals ("3080") stay real;
  known trade: hex-letter shorthand like "a100" now degrades to unverified
  (extending the denylist constant later is a one-liner). (3) WSL-smoke re-check
  of real `Device 008e` output happens in REL21-003.
