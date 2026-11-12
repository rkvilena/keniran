"""Textual application for the ``keniran tui`` entry point.

The TUI is the second renderer of the renderer-agnostic
:class:`~keniran.core.models.Report` (plan/decisions.md §3 swap contract): it
collects a Steam app id, runs the same pipeline as the one-shot CLI, and
displays the resulting report with the inherited honesty semantics.

The pipeline runs in a Textual *thread* worker so the UI stays responsive
while Steam and the hardware audit are in flight. The report itself is mounted
from :func:`keniran.rendering.report_view.report_renderables`, the same ordered
renderables the CLI prints.

Failure paths are honest and non-fatal, mirroring the CLI's ``_fail`` helper:
invalid app ids and worker errors (Steam adapter failures or unexpected
exceptions) are mounted as styled inline messages, the Run button is
re-enabled, and the next check can run in the same session.

The home screen is the branded entry point: a ``Keniran`` title, the ``keniran``
wordmark, the approved tagline, and the App ID/Run controls grouped in one
bordered command box. The branding is presentation only; every id, handler and
worker contract below is unchanged.

The home block and the results area share one vertically scrollable body, so
short terminal heights scroll long content into view instead of clipping it.
The scroll region is not focusable, which keeps the App ID input as the
first-focused widget on mount.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
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
ERROR_ID: Final = "check-error"
ERROR_STYLE: Final = "bold red"

TITLE_ID: Final = "keniran-title"
WORDMARK_ID: Final = "keniran-wordmark"
TAGLINE_ID: Final = "keniran-tagline"
COMMAND_BOX_ID: Final = "command-box"
BODY_ID: Final = "body"

TAGLINE: Final = "Check whether your PC can run a Steam game."


class KeniranTui(App[None]):
    """Minimal keniran TUI shell: app-id input, Run button, results area."""

    TITLE = "keniran"
    SUB_TITLE = "Can I run it?"
    theme = "tokyo-night"

    CSS = """
    Screen {
        background: $background;
    }

    #body {
        width: 1fr;
        height: 1fr;
    }

    #home {
        height: auto;
        width: 1fr;
        padding: 1 2 0 2;
    }

    #keniran-title {
        color: $text-muted;
        text-style: bold;
        height: auto;
    }

    #keniran-wordmark {
        color: $primary;
        text-style: bold;
        height: auto;
        padding: 0 0 1 0;
    }

    #keniran-tagline {
        color: $text-muted;
        height: auto;
    }

    #command-box {
        border: round $panel;
        background: $surface;
        height: auto;
        width: 1fr;
        padding: 0 1;
    }

    #app-id-row {
        height: auto;
    }

    #app-id-input {
        width: 32;
    }

    #run-button {
        margin-left: 2;
        border: tall $accent;
    }

    #results {
        height: auto;
        width: 1fr;
        min-height: 3;
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
        with VerticalScroll(id=BODY_ID, can_focus=False):
            with Vertical(id="home"):
                yield Static("Keniran", id=TITLE_ID, classes="brand-title")
                yield Static("keniran", id=WORDMARK_ID, classes="brand-wordmark")
                yield Static(TAGLINE, id=TAGLINE_ID, classes="brand-tagline")
                with (
                    Container(id=COMMAND_BOX_ID, classes="command-box"),
                    Horizontal(id="app-id-row"),
                ):
                    yield Input(
                        placeholder="Steam App ID",
                        id=APP_ID_INPUT_ID,
                        restrict=r"[0-9]*",
                    )
                    yield Button("Run", id=RUN_BUTTON_ID, variant="primary")
            yield Container(id=RESULTS_ID)
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the Run button."""
        if event.button.id != RUN_BUTTON_ID:
            return
        await self._request_check()

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Replace the status line with the report or a styled inline error."""
        if event.worker is not self._check_worker:
            return
        if event.state is WorkerState.SUCCESS:
            report = event.worker.result
            self._check_worker = None
            if report is not None:
                await self._show_report(report)
            else:
                self._set_running(False)
                await self._clear_results()
        elif event.state is WorkerState.ERROR:
            error = event.worker.error
            self._check_worker = None
            self._set_running(False)
            if isinstance(error, steam.SteamAdapterError):
                await self._show_error(str(error))
            else:
                await self._show_error(f"Unexpected error: {error}")
        elif event.state is WorkerState.CANCELLED:
            self._check_worker = None
            self._set_running(False)
            await self._clear_results()

    async def _request_check(self) -> None:
        """Start one pipeline run for the app id in the input.

        An invalid app id never starts a worker: the inline validation message
        (the TUI counterpart of the CLI's ``_fail``) replaces the results
        instead. A second request while a check is in flight is ignored: the
        Run button stays disabled for the whole run (the pinned behaviour in
        the pilot tests) and the worker guard covers programmatic calls.
        """
        entered = self.query_one(f"#{APP_ID_INPUT_ID}", Input).value
        raw = entered.strip()
        try:
            app_id = int(raw)
        except ValueError:
            app_id = 0
        if not raw.isdigit() or app_id <= 0:
            await self._show_error(f"Invalid APP_ID {entered!r}: expected a numeric Steam app id.")
            return
        if self._check_worker is not None and not self._check_worker.is_finished:
            return

        await self._show_status(app_id)
        self._set_running(True)
        self._check_worker = self.run_worker(
            partial(self._run_check, app_id),
            name=f"check-{app_id}",
            description=f"Checking Steam app {app_id}",
            thread=True,
            exclusive=True,
            exit_on_error=False,
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

    async def _show_status(self, app_id: int) -> None:
        """Mount the running status line naming the requested app id."""
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            Static(f"Checking Steam app {app_id}…", id=STATUS_ID)
        )

    async def _show_error(self, message: str) -> None:
        """Mount one styled inline error (the TUI's counterpart of ``_fail``)."""
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            Static(Text(f"Error: {message}", style=ERROR_STYLE), id=ERROR_ID)
        )

    async def _show_report(self, report: Report) -> None:
        """Replace the status line with the shared report renderables."""
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            *(Static(renderable) for renderable in report_renderables(report))
        )
        self._set_running(False)

    async def _clear_results(self) -> None:
        """Remove everything currently mounted in the results area."""
        await self.query_one(f"#{RESULTS_ID}", Container).remove_children()

    def _set_running(self, running: bool) -> None:
        """Enable or disable the Run button for the duration of a check."""
        self.query_one(f"#{RUN_BUTTON_ID}", Button).disabled = running


def run_tui() -> None:
    """Launch the keniran Textual application."""
    KeniranTui().run()
