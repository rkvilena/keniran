"""Textual application for the ``keniran tui`` entry point.

The TUI is the second renderer of the renderer-agnostic
:class:`~keniran.core.models.Report` (plan/decisions.md §3 swap contract): it
collects a Steam app id, runs the same pipeline as the one-shot CLI, and
displays the resulting report with the inherited honesty semantics.

The pipeline runs in a Textual *thread* worker so the UI stays responsive
while Steam and the hardware audit are in flight. The report itself is mounted
from :func:`keniran.rendering.report_view.report_renderables`, the same ordered
renderables the CLI prints.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Header, Input, Static
from textual.worker import Worker, WorkerState

from keniran.adapters import steam
from keniran.core.models import Report, SystemSpec
from keniran.rendering.report_view import report_renderables
from keniran.services.check_game import BenchmarkDatabase, check_game

APP_ID_INPUT_ID: Final = "app-id-input"
RUN_BUTTON_ID: Final = "run-button"
STATUS_ID: Final = "check-status"
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

    def __init__(
        self,
        *,
        fetch_steam: Callable[[int], steam.SteamRequirements] | None = None,
        load_spec: Callable[..., SystemSpec] | None = None,
        cpu_db: BenchmarkDatabase | None = None,
        gpu_db: BenchmarkDatabase | None = None,
    ) -> None:
        """Create the app, forwarding the ``check_game`` injection seams.

        The keyword arguments are stored untouched and passed to
        :func:`~keniran.services.check_game.check_game` on every run; tests
        inject fakes here to keep pilot runs fully offline.
        """
        super().__init__()
        self._fetch_steam = fetch_steam
        self._load_spec = load_spec
        self._cpu_db = cpu_db
        self._gpu_db = gpu_db
        self._check_worker: Worker[Report] | None = None

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
        """Handle the Run button."""
        if event.button.id != RUN_BUTTON_ID:
            return
        self._request_check()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Replace the status line with the report once the worker succeeds."""
        if event.worker is not self._check_worker:
            return
        if event.state is WorkerState.SUCCESS:
            report = event.worker.result
            self._check_worker = None
            if report is not None:
                self._show_report(report)
            else:
                self._set_running(False)
                self._clear_results()
        elif event.state in (WorkerState.ERROR, WorkerState.CANCELLED):
            self._check_worker = None
            self._set_running(False)
            self._clear_results()

    def _request_check(self) -> None:
        """Start one pipeline run for the app id in the input.

        A second request while a check is in flight is ignored: the Run button
        stays disabled for the whole run (the pinned behaviour in the pilot
        tests) and the worker guard covers programmatic calls.
        """
        raw = self.query_one(f"#{APP_ID_INPUT_ID}", Input).value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            return
        if self._check_worker is not None and not self._check_worker.is_finished:
            return

        app_id = int(raw)
        self._show_status(app_id)
        self._set_running(True)
        self._check_worker = self.run_worker(
            partial(self._run_check, app_id),
            name=f"check-{app_id}",
            description=f"Checking Steam app {app_id}",
            thread=True,
            exclusive=True,
        )

    def _run_check(self, app_id: int) -> Report:
        """Run the shared pipeline in the worker thread with the app's fakes."""
        return check_game(
            app_id,
            fetch_steam=self._fetch_steam,
            load_spec=self._load_spec,
            cpu_db=self._cpu_db,
            gpu_db=self._gpu_db,
        )

    def _show_status(self, app_id: int) -> None:
        """Mount the running status line naming the requested app id."""
        self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            Static(f"Checking Steam app {app_id}…", id=STATUS_ID)
        )

    def _show_report(self, report: Report) -> None:
        """Replace the status line with the shared report renderables."""
        self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            *(Static(renderable) for renderable in report_renderables(report))
        )
        self._set_running(False)

    def _clear_results(self) -> None:
        """Remove everything currently mounted in the results area."""
        self.query_one(f"#{RESULTS_ID}", Container).remove_children()

    def _set_running(self, running: bool) -> None:
        """Enable or disable the Run button for the duration of a check."""
        self.query_one(f"#{RUN_BUTTON_ID}", Button).disabled = running


def run_tui() -> None:
    """Launch the keniran Textual application."""
    KeniranTui().run()
