"""Textual application for the ``keniran tui`` entry point.

The TUI is the second renderer of the renderer-agnostic
:class:`~keniran.core.models.Report` (plan/decisions.md §3 swap contract): it
collects a Steam app id, runs the same pipeline as the one-shot CLI, and
displays the resulting report with the inherited honesty semantics.

The pipeline runs in a Textual *thread* worker so the UI stays responsive
while Steam and the hardware audit are in flight. The report itself is mounted
from :func:`keniran.rendering.report_view.report_renderables`, the same ordered
renderables the CLI prints.

Results replace the home screen: as soon as anything is mounted in the results
area (the busy status line, an inline error, or a report), the hero steps
aside — hidden through a CSS class (``display: none``), never unmounted — and
the results occupy its space. The command box stays visible throughout.

Failure paths are honest and non-fatal, mirroring the CLI's ``_fail`` helper:
invalid app ids and worker errors (Steam adapter failures or unexpected
exceptions) are mounted as styled inline messages, and the next check can run
in the same session.

The app paints itself with the custom ``keniran`` theme
(:mod:`keniran.tui.theme`): a near-black gray monochrome with exactly one amber
role. The theme is registered and selected in ``__init__`` (register first,
then select through the ``theme`` reactive), so the built-ins — including
``tokyo-night`` — remain selectable from the command palette (F1). The
shell carries no Header chrome: the Footer with key hints stays docked under
the scrollable body.

The home screen is the branded entry point: a centered hero holding the
``keniran`` ASCII-art wordmark (:mod:`keniran.tui.branding`) and the subtitle,
above the App ID control grouped in one bordered command box that hugs its
controls (never a fixed wide span). A single blank row separates the panel from
the first results line. Enter in the input or the Check button submits the
check; Reset (the button in the command box, or Esc anywhere) restores the home
screen — the hero reappears and the App ID input and results area are cleared.
The wordmark is the full six-row art when
the terminal fits it and the compact four-row fallback otherwise, re-applied
on mount and on every resize. The branding is
presentation only; every id, handler and worker contract below is unchanged.

The home block and the results area share one vertically scrollable body, so
short terminal heights scroll long content into view instead of clipping it.
While the home screen is showing, that body vertically centers the whole home
block (wordmark, subtitle and command box) as one group in the space above the
docked Footer; the centering is dropped as soon as the hero is hidden, so the
results keep their usual top-aligned position. The scroll region is not
focusable, which keeps the App ID input as the first-focused widget on mount.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import ClassVar, Final

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.widgets import Button, Footer, Input, Rule, Static
from textual.worker import Worker, WorkerState

from keniran.adapters import steam
from keniran.core.models import Report, SystemSpec
from keniran.rendering.report_view import report_renderables
from keniran.services.check_game import BenchmarkDatabase, check_game
from keniran.tui import branding
from keniran.tui.theme import KENIRAN_THEME_NAME, register_keniran_theme

APP_ID_INPUT_ID: Final = "app-id-input"
CHECK_BUTTON_ID: Final = "check-button"
RESET_BUTTON_ID: Final = "reset-button"
STATUS_ID: Final = "check-status"
RESULTS_ID: Final = "results"
ERROR_ID: Final = "check-error"
ERROR_STYLE: Final = "bold red"

HERO_ID: Final = "hero"
HERO_HIDDEN_CLASS: Final = "hidden"
# Applied to the scrollable body while the home screen is showing, so the whole
# home block is centered in the space above the Footer (dropped once the hero
# is hidden so results stay top-aligned).
BODY_HOME_ACTIVE_CLASS: Final = "home-active"
WORDMARK_ID: Final = "keniran-wordmark"
SUBTITLE_ID: Final = "keniran-subtitle"
COMMAND_BOX_ID: Final = "command-box"
COMMAND_BOX_CENTER_ID: Final = "command-box-center"
RULE_CENTER_ID: Final = "keniran-rule-center"
BODY_ID: Final = "body"

SUBTITLE: Final = (
    "Can I run it? Enter the game's Steam App ID, then press Enter to check this PC "
    "against its minimum requirements."
)

# The full wordmark is 38 columns wide and 6 rows tall; it is only shown on
# terminals large enough to keep the whole home block visible without scrolling,
# and the compact four-row fallback (32 columns, R7) is shown otherwise.
WORDMARK_MIN_WIDTH: Final = 44
WORDMARK_MIN_HEIGHT: Final = 22


class KeniranTui(App[None]):
    """Minimal keniran TUI shell: app-id input, Check/Enter submission, Reset/Esc."""

    TITLE = "keniran"
    SUB_TITLE = "Can I run it?"

    # Esc is the keyboard twin of the Reset button (R12): both restore the
    # home screen, so the reset is always one keystroke away. F1 is the single
    # key that opens the command palette; because this "Menu" binding already
    # carries the ``command_palette`` action, the base App does not add a second
    # palette binding. Ctrl+Q still quits.
    COMMAND_PALETTE_BINDING: ClassVar[str] = "f1"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "reset", "Reset", show=True),
        Binding("f1", "command_palette", "Menu", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    CSS = """
    Screen {
        background: $background;
    }

    #body {
        width: 1fr;
        height: 1fr;
    }

    #body.home-active {
        align-vertical: middle;
    }

    /* While the home screen is centered, the empty results area collapses so
       the home block itself is what gets centered (results regain their own
       reserved height the moment the hero is hidden). */
    #body.home-active #results {
        min-height: 0;
    }

    #home {
        height: auto;
        width: 1fr;
        padding: 1 2 0 2;
    }

    #hero {
        height: auto;
        width: 1fr;
        content-align: center middle;
    }

    #keniran-rule {
        color: $text-muted;
        width: 40;
        height: 1;
        margin: 0;
    }

    #keniran-rule-center {
        width: 1fr;
    }

    #hero.hidden {
        display: none;
    }

    #keniran-wordmark {
        color: $primary;
        text-style: bold;
        height: auto;
        width: 1fr;
        text-align: center;
        padding: 0 0 1 0;
    }

    #keniran-subtitle {
        color: $text-muted;
        height: auto;
        width: 1fr;
        text-align: center;
    }

    #command-box-center {
        width: 1fr;
        height: auto;
    }

    #command-box {
        border: round $panel;
        background: $surface;
        height: auto;
        /* Hug the controls instead of spanning a fixed wide panel; the
           max-width keeps the box inside narrow terminals. */
        width: auto;
        max-width: 100%;
        margin-top: 1;
        /* A single blank row between the panel and the first results line. */
        margin-bottom: 1;
        padding: 0 1;
    }

    #app-id-row {
        width: auto;
        height: auto;
    }

    #app-id-input {
        width: 32;
    }

    #reset-button {
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

        The ``keniran`` theme is registered first and only then selected
        through the ``theme`` reactive: assigning an unregistered name would
        raise :class:`textual.app.InvalidThemeError` (register before select).
        """
        super().__init__()
        register_keniran_theme(self)
        self.theme = KENIRAN_THEME_NAME
        self._fetch_steam = fetch_steam
        self._load_spec = load_spec
        self._cpu_db = cpu_db
        self._gpu_db = gpu_db
        self._check_worker: Worker[Report] | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id=BODY_ID, can_focus=False, classes=BODY_HOME_ACTIVE_CLASS):
            with Vertical(id="home"):
                # The hero starts empty: on_mount applies the wordmark variant
                # (full art or the compact fallback) that fits the terminal.
                with Container(id=HERO_ID, classes="hero"):
                    yield Static("", id=WORDMARK_ID, classes="brand-wordmark")
                    with Center(id=RULE_CENTER_ID):
                        yield Rule(id="keniran-rule")
                    yield Static(SUBTITLE, id=SUBTITLE_ID, classes="brand-subtitle")
                with (
                    Center(id=COMMAND_BOX_CENTER_ID),
                    Container(id=COMMAND_BOX_ID, classes="command-box"),
                    Horizontal(id="app-id-row"),
                ):
                    yield Input(
                        placeholder="Steam App ID",
                        id=APP_ID_INPUT_ID,
                        restrict=r"[0-9]*",
                    )
                    yield Button("Check", id=CHECK_BUTTON_ID)
                    yield Button("Reset", id=RESET_BUTTON_ID)
            yield Container(id=RESULTS_ID)
        # ``show_command_palette=False`` drops the Footer's docked right-side
        # palette hint: the "f1 Menu" key above is the one menu entry shown.
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        """Fill the wordmark once the app and the terminal size are known."""
        self._apply_wordmark(self.size)

    def on_resize(self, event: events.Resize) -> None:
        """Re-apply the wordmark whenever the terminal is resized."""
        self._apply_wordmark(event.size)

    def _apply_wordmark(self, size: Size) -> None:
        """Show the full or compact wordmark variant that fits *size*.

        The full six-row art (38 columns) is shown only when the terminal is
        large enough to keep the whole home block visible without scrolling;
        every other size gets the compact four-row fallback (R7). Resize
        events can arrive before the widgets exist, so the update is skipped
        until the wordmark is mounted.
        """
        if not self.screen_stack or not self.query(f"#{WORDMARK_ID}"):
            return
        if size.width >= WORDMARK_MIN_WIDTH and size.height >= WORDMARK_MIN_HEIGHT:
            art = branding.wordmark_renderable(
                branding.WORDMARK_GRAY_START, branding.WORDMARK_GRAY_END
            )
        else:
            art = branding.wordmark_renderable_for(
                branding.WORDMARK_COMPACT,
                branding.WORDMARK_GRAY_START,
                branding.WORDMARK_GRAY_END,
            )
        self.query_one(f"#{WORDMARK_ID}", Static).update(art)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit the check when Enter is pressed in the App ID input."""
        if event.input.id != APP_ID_INPUT_ID:
            return
        await self._request_check()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit a check or restore home from the corresponding button."""
        if event.button.id == CHECK_BUTTON_ID:
            await self._request_check()
        elif event.button.id == RESET_BUTTON_ID:
            await self._reset()

    async def action_reset(self) -> None:
        """Run the reset for the Esc binding (the same reset as the button)."""
        await self._reset()

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
                await self._clear_results()
        elif event.state is WorkerState.ERROR:
            error = event.worker.error
            self._check_worker = None
            if isinstance(error, steam.SteamAdapterError):
                await self._show_error(str(error))
            else:
                await self._show_error(f"Unexpected error: {error}")
        elif event.state is WorkerState.CANCELLED:
            self._check_worker = None
            await self._clear_results()

    async def _request_check(self) -> None:
        """Start one pipeline run for the app id in the input.

        An invalid app id never starts a worker: the inline validation message
        (the TUI counterpart of the CLI's ``_fail``) replaces the results
        instead. A second request while a check is in flight is ignored: the
            worker guard drops duplicate submissions until the running check
            finishes.
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
        self._hide_hero()
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            Static(f"Checking Steam app {app_id}…", id=STATUS_ID)
        )

    async def _show_error(self, message: str) -> None:
        """Mount one styled inline error (the TUI's counterpart of ``_fail``)."""
        self._hide_hero()
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            Static(Text(f"Error: {message}", style=ERROR_STYLE), id=ERROR_ID)
        )

    async def _show_report(self, report: Report) -> None:
        """Replace the status line with the shared report renderables."""
        self._hide_hero()
        await self._clear_results()
        self.query_one(f"#{RESULTS_ID}", Container).mount(
            *(Static(renderable) for renderable in report_renderables(report))
        )

    async def _clear_results(self) -> None:
        """Remove everything currently mounted in the results area."""
        await self.query_one(f"#{RESULTS_ID}", Container).remove_children()

    def _hide_hero(self) -> None:
        """Hide the hero so the results occupy its space (it stays mounted).

        The body stops vertically centering the home block at the same time, so
        the command box and the results fall back to their top-aligned
        positions while the check runs.
        """
        self.query_one(f"#{BODY_ID}", VerticalScroll).remove_class(BODY_HOME_ACTIVE_CLASS)
        self.query_one(f"#{HERO_ID}", Container).add_class(HERO_HIDDEN_CLASS)

    async def _reset(self) -> None:
        """Restore the home screen: unhide the hero, clear input and results.

        Both the Reset button and the Esc binding land here, so the shell
        returns to its initial state without unmounting anything and the next
        check can run in the same session.
        """
        self.query_one(f"#{HERO_ID}", Container).remove_class(HERO_HIDDEN_CLASS)
        self.query_one(f"#{BODY_ID}", VerticalScroll).add_class(BODY_HOME_ACTIVE_CLASS)
        await self._clear_results()
        app_id_input = self.query_one(f"#{APP_ID_INPUT_ID}", Input)
        app_id_input.value = ""
        app_id_input.focus()


def run_tui() -> None:
    """Launch the keniran Textual application."""
    KeniranTui().run()
