"""Textual application for the ``keniran tui`` entry point.

The TUI is the second renderer of the renderer-agnostic
:class:`~keniran.core.models.Report` (plan/decisions.md §3 swap contract): it
collects a Steam app id, runs the same pipeline as the one-shot CLI, and
displays the resulting report with the inherited honesty semantics.

This scaffold only provides the shell; the pipeline worker and report display
land in TUI-003.
"""

from __future__ import annotations

from typing import Final

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Header, Input, Static

APP_ID_INPUT_ID: Final = "app-id-input"
RUN_BUTTON_ID: Final = "run-button"
RESULTS_ID: Final = "results"


class KeniranTui(App[None]):
    """Minimal keniran TUI shell: app-id input, Run button, results area."""

    TITLE = "keniran"
    SUB_TITLE = "Can I run it?"
    theme = "tokyo-night"

    CSS = """
    #app-id-row {
        height: auto;
        padding: 1 2;
    }

    #app-id-input {
        width: 32;
    }

    #run-button {
        margin-left: 2;
    }

    #results {
        height: 1fr;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="app-id-row"):
            yield Input(
                placeholder="Steam App ID",
                id=APP_ID_INPUT_ID,
                restrict=r"[0-9]*",
            )
            yield Button("Run", id=RUN_BUTTON_ID, variant="primary")
        yield Container(id=RESULTS_ID)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the Run button (the pipeline worker lands in TUI-003)."""
        if event.button.id != RUN_BUTTON_ID:
            return
        self._request_check()

    def _request_check(self) -> None:
        """Show a placeholder result for the requested app id.

        The real ``check_game`` worker replaces this stub in TUI-003; for now
        the shell only proves the input/button/result wiring works.
        """
        raw = self.query_one(f"#{APP_ID_INPUT_ID}", Input).value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            return
        results = self.query_one(f"#{RESULTS_ID}", Container)
        results.remove_children()
        results.mount(Static(f"Requested a check for App ID {raw}."))


def run_tui() -> None:
    """Launch the keniran Textual application."""
    KeniranTui().run()
