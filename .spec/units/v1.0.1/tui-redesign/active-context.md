# Active context — v1.0.1/tui-redesign

- current task: TUIX-002 → **done (commit b4efff2)**. Unit complete: TUIX-001 (cb4ce93)
  + TUIX-002 (b4efff2). Both feature tasks verified PASS.
- state: branded home hierarchy landed — `Vertical(id="home")` with `#keniran-title`
  ("Keniran"), `#keniran-wordmark` ("keniran", bold + `$primary`), `#keniran-tagline`
  (`TAGLINE = "Check whether your PC can run a Steam game."`), and bordered
  `#command-box` wrapping the unchanged `#app-id-row` (Input + Run button). Theme-token
  CSS only; `theme == "tokyo-night"` retained; all ids/handlers/worker code unchanged.
  16 TUI pilot tests pass; full gate 283 passed.
- design contract: dark slate/navy base, muted lavender primary highlight, restrained warm
  accent; vertical scrolling at short heights (TUIX-002's scope now).
- preserve: `tokyo-night` default and theme switching, worker/status/results/errors,
  shared renderer output, keyboard access, and the one-shot CLI.
- note: this unit started while `v1.0.1/requirement-alternatives` is blocked (ALT-001
  failed-review). Deviation from the release spec's linear sequencing is recorded in the
  release active-context; the TUIX task blocks carry no `gated:` field, and TUIX is
  independent of the matching code.
- open: exact hex values and spacing are flexible; do not imitate the screenshot's domain
  layout, only its terminal aesthetic.
