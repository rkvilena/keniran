# Engino Blueprint v1.1.2: Refine the input panel and explain benchmark matches

## Context & Scope
- The Textual home screen and results share a scrollable body; the Footer remains docked.
- Make the centered App ID/Reset panel hug its controls, preserve a narrow-terminal width limit, and add modest space before results.
- The shared report renderer serves both the TUI and CLI. Replace the ambiguous ⚡ benchmark marker with 🔎 and explain the match badge in a subdued caption.
- Keep benchmark matching, confidence calculation, and scoring behavior unchanged.
- Touched paths: `src/keniran/tui/app.py`, `tests/test_tui.py`, `src/keniran/rendering/report_view.py`, `tests/test_report_view.py`, `tests/test_cli_report.py`.

## Builder Model Preference (advisory)
- Tier: Balanced
- Reason: Focused layout and shared report presentation changes with responsive behavior to preserve.
- Exact model: not pinned; select with /models

## Tasks

### Task 1: Clarify the benchmark match badge
- Target files: `src/keniran/rendering/report_view.py`, `tests/test_report_view.py`, `tests/test_cli_report.py`
- Instructions: Replace ⚡ with 🔎 in the matched benchmark badge and update the renderer description accordingly. Add a subdued helper line immediately after the component table and before conditional unverified-result warnings: “🔎 marks the benchmark match for the listed CPU/GPU requirement; its % is match confidence. Result compares your system with that benchmark.” Keep this presentation-only; do not change match selection, confidence, or scoring. Update shared-renderer and CLI expectations for the icon and caption.
- Verification: `.venv/Scripts/python.exe -m pytest tests/test_report_view.py tests/test_cli_report.py -q`

### Task 2: Refine the TUI input panel and results spacing
- Target files: `src/keniran/tui/app.py`, `tests/test_tui.py`
- Instructions: Change the centered App ID/Reset panel from its fixed wide size to a content-hugging width based on its controls, retaining a maximum width so it remains within narrow terminals. Add a modest gap between the panel and the first result line. Preserve the centered arrangement, scrolling behavior, and results layout. Update layout assertions and the TUI report integration coverage to verify the 🔎 badge and explanatory caption render.
- Verification: `.venv/Scripts/python.exe -m pytest tests/test_tui.py -q`

## Out of Scope
- Changes to benchmark matching, confidence calculation, requirements selection, or scoring.
