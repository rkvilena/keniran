# Active context — 0.2.0/model-layout

- current task: unit complete — all 3 model-layout tasks done.
- last commit: 0c71484 SYS-003: Make vram_gb optional with interim unverified handling
- state: model-layout unit DONE (SYS-001 f43e66b, SYS-002 652cb14, SYS-003 0c71484); full suite 132 green.
- interpretation note (SYS-003): unknown user-side VRAM renders "unverified"
  (existing UNVERIFIED_VALUE constant); reviewer ruled acceptable.
- collateral note (SYS-003): scoring.py one-line typing widening (float | None in
  minimum_shortfalls tuple) forced by mypy strict gate — typing-only, approved by reviewer.
- interpretation note (SYS-002): platform check in _read_cache runs before full payload
  validation — a mismatched malformed cache re-audits instead of raising
  HardwareCacheError (reviewer ruled correct: stale-by-OS beats corruption check).
- collateral note (SYS-002): tests/test_scoring.py + tests/test_check_game.py fixture
  updates were forced by required `platform` field + full-suite acceptance command
  (reviewer ruled minimal-necessary, not scope creep).
- interpretation note (SYS-001): "raise UnsupportedPlatformError otherwise" applied to
  `audit` (and cache-miss path of `load`); `save`/`parse_dxdiag` and cached `load`
  stay platform-agnostic — matches pre-split behavior, pinned by tests.
