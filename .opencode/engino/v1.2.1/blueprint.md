# Engino Blueprint v1.2.1: Refine UI controls and color report results

## Context & Scope
- The Textual home screen and its theme-token CSS are in `src/keniran/tui/app.py`; the custom `keniran` theme already defines amber accent `#E0A64B`, muted green success, and muted red error roles.
- The shared report renderer is `src/keniran/rendering/report_view.py`, used by the CLI and TUI; retain its shared-renderer behavior and existing report wording.
- Scope is limited to home-screen layout/states and report presentation, with focused coverage in `tests/test_tui.py` and `tests/test_report_view.py`.
- Do not change scoring thresholds, verdict semantics, report data, or theme palette.

## Builder Model Preference (advisory)
- Tier: Balanced
- Reason: A focused visual change spans the TUI and shared report renderer and needs regression coverage in both.
- Exact model: not pinned; select with /models

## Tasks

### Task 1: Refine home-screen controls
- Target files: `src/keniran/tui/app.py`, `tests/test_tui.py`
- Instructions: Give the App ID input-to-Check and Check-to-Reset controls equal gaps. Fill Check with the theme amber accent; preserve darker hover and pressed feedback, using amber as the base. Constrain the subtitle to the command box width so long text wraps rather than extending beyond the box; keep it centered and responsive at narrower terminal sizes. Add or update pilot assertions for spacing, sizing/wrapping, and button styles/states without changing submission or reset behavior.
- Verification: `python -m pytest tests/test_tui.py`

### Task 2: Add semantic color to report output
- Target files: `src/keniran/rendering/report_view.py`, `tests/test_report_view.py`
- Instructions: Apply amber (`#E0A64B`) to the comparison table border and bold game-title/Steam-app-ID line. Color each component Result and the overall verdict by the existing semantics: Pass green; Borderline/Poor amber; Unplayable/Fail red; Unverified subdued/neutral. Use component ratios and pass states, and the existing verdict band (including storage shortfall Fail) as the sources of truth; do not alter scoring or displayed wording. Preserve message-only reports and verify styled renderables in tests.
- Verification: `python -m pytest tests/test_report_view.py tests/test_cli_report.py`

## Out of Scope
- Scoring thresholds, verdict semantics or wording, report data, and changes to the theme palette.
