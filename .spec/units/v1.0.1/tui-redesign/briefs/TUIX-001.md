# Brief — TUIX-001: Add the Keniran branded home hierarchy and reference-inspired styling

seam: This task is a **visual/layout-only** change inside `src/keniran/tui/app.py` plus the matching pilot
assertions in `tests/test_tui.py`. The `KeniranTui` app currently mounts a bare `Header()`, a single
`Horizontal(id="app-id-row")` holding the App ID `Input` and the `Run` `Button`, an empty
`Container(id="results")`, and a `Footer()`, styled by a 4-rule `CSS` block. The change adds a *branded home
hierarchy* above the command box — a `Keniran` title/header, a large `keniran` wordmark, the tagline
`Check whether your PC can run a Steam game.`, and a bordered, visually grouped App ID/Run **command box** — and
restyles the app with the agreed dark slate/navy, muted-lavender, restrained warm-accent palette using Textual
theme tokens where practical (the installed `tokyo-night` theme already *is* that palette: primary `#BB9AF7`,
accent `#FF9E64`, background `#1A1B26`, panel `#414868`). The seam is deliberately **behaviour-preserving**:
`APP_ID_INPUT_ID`, `RUN_BUTTON_ID`, `STATUS_ID`, `RESULTS_ID`, `ERROR_ID`, `ERROR_STYLE`, the `Input`'s
`restrict=r"[0-9]*"`, the `on_button_pressed` / `on_worker_state_changed` handlers, the thread worker
(`thread=True`, `exclusive=True`, `exit_on_error=False`), the status/error/report mounting, and the shared
`report_renderables` output must all behave exactly as today, so every existing pilot test keeps passing
unchanged. Out of scope: `keniran.rendering.report_view`, `check_game`, scoring/matching, CLI dispatch,
dependencies, history/search, and theme persistence.

## Files in play

- `src/keniran/tui/app.py` — the only production file to change (compose hierarchy + `CSS`).
- `tests/test_tui.py` — the only test file to change (add pilot assertions for the branded widgets/command box).
- `src/keniran/rendering/report_view.py` — context only; **must not change** (the report renderables mounted by
  `_show_report` are pinned by `test_completed_check_mounts_the_shared_report_renderables`).
- `.spec/units/v1.0.1/tui-redesign/spec.md`, `.spec/decisions.md` (lines 230-235 and 252-255) — binding design
  contract and the approved tagline copy.

### Tree-state constraint (do not violate)

The working tree holds **uncommitted sibling-task work** (blocked task ALT-001) in
`src/keniran/core/requirements_parser.py` and `tests/test_requirements_parser.py`, plus untracked
`.spec/units/v1.0.1/**` ledger/brief files. **Do not read-modify, stage, revert, or "clean up" those two files.**
Touch only `src/keniran/tui/app.py` and `tests/test_tui.py`. `ruff format .` may reformat the sibling files if
they are not already formatted — if that happens, leave the reformat in place (do not revert) and mention it.

### Out of scope (explicit)

`src/keniran/rendering/report_view.py`, `src/keniran/services/check_game.py`, `src/keniran/core/scoring.py`,
`src/keniran/cli/app.py` (CLI dispatch), `src/keniran/adapters/**`, `pyproject.toml` dependencies, matching/scoring
behaviour, search/history features, and theme persistence.

## 1. Exact current shape of `src/keniran/tui/app.py` (210 lines)

**Module docstring (1-17)** — explains that the TUI is the second renderer of `keniran.core.models.Report`, that
the pipeline runs in a Textual *thread worker*, that the report is mounted from
`keniran.rendering.report_view.report_renderables`, and that failure paths are inline and non-fatal. Keep this
contract statement true; extend it with one or two sentences about the branded home if you like.

**Imports (19-34)** — note `Container, Horizontal` are the only containers imported today; `Vertical` /
`ScrollableContainer` are available in the same module (`textual.containers`) if the plan needs them.

```
19: from __future__ import annotations
20:
21: from collections.abc import Callable
22: from functools import partial
23: from typing import Final
24:
25: from rich.text import Text
26: from textual.app import App, ComposeResult
27: from textual.containers import Container, Horizontal
28: from textual.widgets import Button, Footer, Header, Input, Static
29: from textual.worker import Worker, WorkerState
30:
31: from keniran.adapters import steam
32: from keniran.core.models import Report, SystemSpec
33: from keniran.rendering.report_view import report_renderables
34: from keniran.services.check_game import BenchmarkDatabase, check_game
```

**Module-level id/style constants (36-41)** — these are imported by `tests/test_tui.py` (lines 46-54). **Do not
rename or remove any of them.**

```
36: APP_ID_INPUT_ID: Final = "app-id-input"
37: RUN_BUTTON_ID: Final = "run-button"
38: STATUS_ID: Final = "check-status"
39: RESULTS_ID: Final = "results"
40: ERROR_ID: Final = "check-error"
41: ERROR_STYLE: Final = "bold red"
```

**Class header (44-49)** — `TITLE`/`SUB_TITLE` feed the `Header` widget's title line
(`textual/app.py:1039` `format_title` renders `"keniran — Can I run it?"`).

```
44: class KeniranTui(App[None]):
45:     """Minimal keniran TUI shell: app-id input, Run button, results area."""
46:
47:     TITLE = "keniran"
48:     SUB_TITLE = "Can I run it?"
49:     theme = "tokyo-night"
```

**The `CSS` block (51-69)** — the entire current stylesheet. There is **no `SCROLL` class attribute** in this app;
`SCROLL` is a Textual `Widget`/`ScrollBar` class in the library, not an app-level hook — do not invent one.

```
51:     CSS = """
52:     #app-id-row {
53:         height: auto;
54:         padding: 1 2;
55:     }
56:
57:     #app-id-input {
58:         width: 32;
59:     }
60:
61:     #run-button {
62:         margin-left: 2;
63:     }
64:
65:     #results {
66:         height: 1fr;
67:         padding: 0 2;
68:     }
69:     """
```

**Constructor (71-90)** — unchanged injection seams (`fetch_steam`, `load_spec`, `cpu_db`, `gpu_db`) and the
worker handle. Do not touch.

```
71:     def __init__(
72:         self,
73:         *,
74:         fetch_steam: Callable[[int], steam.SteamRequirements] | None = None,
75:         load_spec: Callable[..., SystemSpec] | None = None,
76:         cpu_db: BenchmarkDatabase | None = None,
77:         gpu_db: BenchmarkDatabase | None = None,
78:     ) -> None:
...
85:         super().__init__()
86:         self._fetch_steam = fetch_steam
87:         self._load_spec = load_spec
88:         self._cpu_db = cpu_db
89:         self._gpu_db = gpu_db
90:         self._check_worker: Worker[Report] | None = None
```

**`compose()` (92-102) — the exact seam to redesign.** Current widget tree (ids/classes):

| order | widget | id | classes | notes |
|---|---|---|---|---|
| 1 | `Header()` | — | — | docked top, shows `TITLE`/`SUB_TITLE`; pinned by test line 193 |
| 2 | `Horizontal` | `app-id-row` | — | `height: auto; padding: 1 2` |
| 3 | `Input` | `app-id-input` | — | `placeholder="Steam App ID"`, `restrict=r"[0-9]*"`, `width: 32` |
| 4 | `Button` | `run-button` | — | label `"Run"`, `variant="primary"` |
| 5 | `Container` | `results` | — | `height: 1fr; padding: 0 2`; the mount target for status/report/error |
| 6 | `Footer()` | — | — | docked bottom; pinned by test line 194 |

```
92:     def compose(self) -> ComposeResult:
93:         yield Header()
94:         with Horizontal(id="app-id-row"):
95:             yield Input(
96:                 placeholder="Steam App ID",
97:                 id=APP_ID_INPUT_ID,
98:                 restrict=r"[0-9]*",
99:             )
100:             yield Button("Run", id=RUN_BUTTON_ID, variant="primary")
101:         yield Container(id=RESULTS_ID)
102:         yield Footer()
```

**Handlers / worker plumbing (104-205) — behaviour that must not change.**

```
104:     async def on_button_pressed(self, event: Button.Pressed) -> None:
105:         """Handle the Run button."""
106:         if event.button.id != RUN_BUTTON_ID:
107:             return
108:         await self._request_check()
109:
110:     async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
111:         """Replace the status line with the report or a styled inline error."""
112:         if event.worker is not self._check_worker:
113:             return
114:         if event.state is WorkerState.SUCCESS:
115:             report = event.worker.result
116:             self._check_worker = None
117:             if report is not None:
118:                 await self._show_report(report)
119:             else:
120:                 self._set_running(False)
121:                 await self._clear_results()
122:         elif event.state is WorkerState.ERROR:
123:             error = event.worker.error
124:             self._check_worker = None
125:             self._set_running(False)
126:             if isinstance(error, steam.SteamAdapterError):
127:                 await self._show_error(str(error))
128:             else:
129:                 await self._show_error(f"Unexpected error: {error}")
130:         elif event.state is WorkerState.CANCELLED:
131:             self._check_worker = None
132:             self._set_running(False)
133:             await self._clear_results()
```

`_request_check` (135-165) validates the input (`int(raw)`, `raw.isdigit()`, `app_id <= 0` → inline
`Invalid APP_ID ...` error, no worker), guards against a second in-flight run, shows the status line, and starts
the worker:

```
144:         entered = self.query_one(f"#{APP_ID_INPUT_ID}", Input).value
145:         raw = entered.strip()
146:         try:
147:             app_id = int(raw)
148:         except ValueError:
149:             app_id = 0
150:         if not raw.isdigit() or app_id <= 0:
151:             await self._show_error(f"Invalid APP_ID {entered!r}: expected a numeric Steam app id.")
152:             return
153:         if self._check_worker is not None and not self._check_worker.is_finished:
154:             return
155:
156:         await self._show_status(app_id)
157:         self._set_running(True)
158:         self._check_worker = self.run_worker(
159:             partial(self._run_check, app_id),
160:             name=f"check-{app_id}",
161:             description=f"Checking Steam app {app_id}",
162:             thread=True,
163:             exclusive=True,
164:             exit_on_error=False,
165:         )
```

`_run_check` (167-175) forwards the injected seams to `check_game`. `_show_status` (177-182), `_show_error`
(184-189), `_show_report` (191-197), `_clear_results` (199-201), `_set_running` (203-205):

```
177:     async def _show_status(self, app_id: int) -> None:
179:         await self._clear_results()
180:         self.query_one(f"#{RESULTS_ID}", Container).mount(
181:             Static(f"Checking Steam app {app_id}…", id=STATUS_ID)
182:         )
183:
184:     async def _show_error(self, message: str) -> None:
186:         await self._clear_results()
187:         self.query_one(f"#{RESULTS_ID}", Container).mount(
188:             Static(Text(f"Error: {message}", style=ERROR_STYLE), id=ERROR_ID)
189:         )
190:
191:     async def _show_report(self, report: Report) -> None:
193:         await self._clear_results()
194:         self.query_one(f"#{RESULTS_ID}", Container).mount(
195:             *(Static(renderable) for renderable in report_renderables(report))
196:         )
197:         self._set_running(False)
198:
199:     async def _clear_results(self) -> None:
201:         await self.query_one(f"#{RESULTS_ID}", Container).remove_children()
202:
203:     def _set_running(self, running: bool) -> None:
205:         self.query_one(f"#{RUN_BUTTON_ID}", Button).disabled = running
```

`run_tui()` (208-210) — `KeniranTui().run()`; the CLI dispatch test monkeypatches
`keniran.tui.app.run_tui` (`tests/test_tui.py:593`), so the function name must stay.

## 2. Current `tests/test_tui.py` structure (639 lines)

**Pilot construction.** Every TUI test uses Textual's headless pilot: `async with tui.run_test() as pilot:`.
No explicit size is passed today (the pilot default size applies). The scenarios are driven through a module
helper:

```
59: def _run(scenario: Coroutine[Any, Any, None]) -> None:
60:     """Run one async pilot scenario on a fresh event loop."""
61:     asyncio.run(scenario)
```

**Shared helpers (all reusable as-is):**

- `_wait_until(predicate, pilot, timeout=5.0)` (64-75) — polls with `await pilot.pause(0.01)`.
- `_wait_for_check(tui, pilot)` (78-86) — `await tui.workers.wait_for_complete()` inside
  `contextlib.suppress(WorkerFailed)`, then `await pilot.pause()`.
- `_error_texts(tui)` (89-95) — `child.content.plain` for every `Static` under `#check-error` whose content is a
  `rich.text.Text`.
- `_click_run(tui, pilot)` (98-102) — waits until `not button.has_class("-active")` then `await pilot.click(...)`.
- `_offline_tui(fetch_steam)` (138-145) — `KeniranTui(fetch_steam=..., load_spec=_fake_load_spec, cpu_db={"data": []}, gpu_db={"data": []})`.
- Fixture `full_report` (151-180) — canned `Report` with CPU/GPU/RAM component rows.

**Existing tests and what they pin:**

| line | test | pins |
|---|---|---|
| 186 | `test_app_mounts_shell_with_tokyo_night_theme` | `isinstance(tui, App)`, `tui.theme == "tokyo-night"`, `tui.current_theme.name == "tokyo-night"`, `Header` present, `Footer` present, `Input.restrict == r"[0-9]*"`, `Button` present, `#results` exists with `len(children) == 0` |
| 204 | `test_app_id_input_rejects_non_digits` | typing `a/b/c` yields `""`; digits yield the value |
| 223 | `test_run_executes_check_game_with_injection_kwargs_in_a_worker` | one `check_game` call with the injected kwargs; `thread != main_thread` |
| 285 | `test_status_and_disabled_run_stay_visible_while_checking` | `#check-status` mounted and contains the app id; Run disabled during the run; second click starts no worker; status removed after completion |
| 341 | `test_completed_check_mounts_the_shared_report_renderables` | `#results` children are the exact `report_renderables(report)` sequence (tables/texts compared) |
| 387 | `test_message_only_report_replaces_the_status_line` | `#results` children == `[Text(message)]`, no `#check-error` |
| 421 | `test_invalid_app_id_shows_inline_validation_and_starts_no_worker` | inline error text + `content.style == ERROR_STYLE`; Run re-enabled; no worker started |
| 481 | `test_steam_app_not_found_is_inline_and_a_later_check_recovers` | inline Steam error; a later valid check recovers in the same session |
| 526 | `test_generic_steam_adapter_error_is_shown_inline` | `content.plain == "Error: Steam is unreachable"` |
| 547 | `test_unexpected_exception_surfaces_inline_instead_of_killing_the_app` | `Unexpected error: boom` inline, app still running |
| 572 | `test_cli_app_id_still_runs_the_one_shot_check` | CLI one-shot unchanged |
| 590 | `test_cli_tui_launches_the_tui_app` | `keniran tui` still calls `keniran.tui.app.run_tui` |
| 626 | `test_cli_bare_invocation_prints_help_on_the_real_console` | bare `keniran` prints help |

**Assertion idioms to imitate** (all read-only, no snapshots):

- `tui.query_one(f"#{APP_ID_INPUT_ID}", Input)` / `tui.query_one(Header)` / `tui.query_one(f"#{RESULTS_ID}", Container)`.
- `tui.query(f"#{ERROR_ID}")` returning a list; `list(tui.query(f"#{STATUS_ID}")) == []` for "not mounted".
- `child.content.plain` / `child.content.style` on `Static`s whose content is a `rich.text.Text`.
- `isinstance(child, Static)`, `isinstance(item, Table)`, `isinstance(item, Text)` filters.
- `button.has_class("-active")`, `button.disabled is True/False`, `tui.is_running`.
- `pilot.click(f"#{RUN_BUTTON_ID}")`, `pilot.press("a", "b", "c")`, `input.focus()`.

**Where the new assertions go.** Insert them in the "Textual shell" section, **immediately after
`test_app_mounts_shell_with_tokyo_night_theme` (which ends at line 201, before
`test_app_id_input_rejects_non_digits` at line 204)**. Use the same
`def test_...() -> None:` + nested `async def scenario() -> None:` + `_run(scenario())` shape. New tests must not
modify any existing test.

**Note on `Static` content typing.** `Static.content` returns the *original* object
(`textual/widgets/_static.py:65-68`): a `rich.text.Text` keeps `.plain`/`.style`; a plain `str` has **no**
`.plain` attribute. If a branded widget is created with a `str`, assert with `str(widget.content)` or
`"keniran" in str(widget.content)`; if you want `.plain`, construct it with `Text(...)`.

## 3. Textual version and available APIs (verified in the installed venv)

- **Version: `textual==8.2.8`** — pinned in `pyproject.toml:19`; installed at
  `.venv/Lib/site-packages/textual-8.2.8.dist-info`. `rich==15.0.0`, `pytest==9.2.0`, `ruff==0.17.4`,
  `mypy==2.4.1` (dev extras, `pyproject.toml:22-27`).

**Theme / CSS variables available in 8.2.8** (generated by `textual/design.py:106-508`,
`ColorSystem.COLOR_NAMES` at `design.py:32-45`):

- Base: `$primary`, `$secondary`, `$background`, `$foreground`, `$surface`, `$panel`, `$boost`, `$warning`,
  `$error`, `$success`, `$accent`.
- Text: `$text`, `$text-muted`, `$text-disabled`, `$text-primary`, `$text-secondary`, `$text-warning`,
  `$text-error`, `$text-success`, `$text-accent`, `$foreground-muted`, `$foreground-disabled`.
- Muted variants: `$primary-muted`, `$secondary-muted`, `$accent-muted`, `$warning-muted`, `$error-muted`,
  `$success-muted`, `$background-muted`.
- Widget tokens: `$border`, `$border-blurred`, `$surface-active`, `$scrollbar`, `$scrollbar-hover`,
  `$scrollbar-active`, `$scrollbar-background`, `$scrollbar-corner-color`, `$footer-foreground`,
  `$footer-background`, `$footer-key-foreground`, `$footer-key-background`, `$input-cursor-background`,
  `$input-cursor-foreground`, `$input-selection-background`, `$input-selection-foreground`,
  `$link-color`, `$link-style`, `$markdown-h1-color`, …
- **Shades**: every base colour also exists as `<name>-lighten-1..3` and `<name>-darken-1..3`
  (`design.py:90-100`, `design.py:343-360`) — e.g. `$primary-darken-1`, `$background-lighten-1`,
  `$panel-lighten-2`.
- A CSS variable that is referenced but defined nowhere **fails CSS parsing at startup**
  (`textual/app.py:1400-1417` `get_theme_variable_defaults`). Only use variables listed above.

**`tokyo-night` theme values** (`textual/theme.py:177-192`) — these *are* the agreed palette:

| token | value | role |
|---|---|---|
| `primary` | `#BB9AF7` | muted lavender highlight (wordmark / focus / primary button) |
| `secondary` | `#7AA2F7` | blue |
| `accent` | `#FF9E64` | restrained warm accent |
| `warning` | `#E0AF68` | warm yellow |
| `error` | `#F7768E` | red |
| `success` | `#9ECE6A` | green |
| `foreground` | `#a9b1d6` | body text |
| `background` | `#1A1B26` | dark slate/navy base |
| `surface` | `#24283B` | surface |
| `panel` | `#414868` | pane/border-ish |

**Widget / container API available in 8.2.8:**

- `textual.widgets`: `Button`, `Checkbox`, `Collapsible`, `ContentSwitcher`, `DataTable`, `Digits`,
  `DirectoryTree`, `Footer`, `Header`, `HelpPanel`, `Input`, `KeyPanel`, `Label`, `Link`, `ListItem`,
  `ListView`, `LoadingIndicator`, `Log`, `Markdown`, `MarkdownViewer`, `MaskedInput`, `OptionList`,
  `Placeholder`, `Pretty`, `ProgressBar`, `RadioButton`, `RadioSet`, `RichLog`, `Rule`, `Select`,
  `SelectionList`, `Sparkline`, `Static`, `Switch`, `Tab`, `TabbedContent`, `TabPane`, `Tabs`, `TextArea`,
  `Tooltip`, `Tree`, `Welcome` (`textual/widgets/__init__.py:53-96`).
- `textual.containers`: `Container`, `ScrollableContainer`, `Vertical`, `VerticalGroup`, `VerticalScroll`,
  `Horizontal`, `HorizontalGroup`, `HorizontalScroll`, `Center`, `Right`, `Middle`, `CenterMiddle`, `Grid`,
  `ItemGrid` (`textual/containers.py:19-261`).
- `Button` variants: `Literal["default", "primary", "success", "warning", "error"]`
  (`textual/widgets/_button.py:26`) — `variant="primary"` is already used.
- `Input.__init__(value, placeholder, password, *, name, id, classes, disabled, compact, restrict, ...)`
  (`textual/widgets/_input.py:354-406`) — `restrict` is a `var["str | None"]` (`_input.py:275`); `compact=True`
  drops the built-in border if you want the command box border to be the only frame.
- `Static.__init__(content, *, expand, shrink, markup, name, id, classes, disabled)`
  (`textual/widgets/_static.py:32-50`); `Static` has `height: auto` by default (`_static.py:26-30`).
- `Header` is `dock: top`, `height: 1` (or 3 with `tall`) and shows `TITLE — SUB_TITLE`
  (`textual/widgets/_header.py:116-228`, `textual/app.py:1039-1058`); `Footer` is `dock: bottom`.
- `App.CSS` is the app-level stylesheet (`textual/app.py:299`); `App.SCOPED_CSS` exists but is screen-scoped —
  use plain `CSS`.
- `App.theme` is a `Reactive[str]` (`textual/app.py:560`); `App.current_theme` resolves it
  (`textual/app.py:1486-1492`).

**CSS properties available** (verified in `textual/css/styles.py:96-215`): `display`, `visibility`, `layout`,
`color`, `background`, `text-style`, `text-opacity`, `opacity`, `padding`, `margin`, `offset`, `position`,
`border` (+ `border-top/right/bottom/left`), `border-title-align`, `border-subtitle-align`,
`border-title-color/background/style`, `border-subtitle-*`, `outline`, `keyline`, `box-sizing`, `width`,
`height`, `min-*`, `max-*`, `dock`, `split`, `overflow-x/y`, `layers`/`layer`, `align`, `content-align`,
`text-align`, `link-*`, `hatch`, `scrollbar-*`, `text-wrap`, `text-overflow`, `expand`, `line-pad`.
**Border styles** (`textual/css/types.py:11-30`): `ascii`, `none`, `blank`, `round`, `solid`, `double`,
`dashed`, `heavy`, `hkey`, `vkey`, `tall`, `outer`, `panel`.

## 4. Concrete composition plan

### 4.1 New widget hierarchy (ids/classes to add)

Keep `Header()`, `Footer()`, and every existing id untouched. Add a **brand block** above the command box and
wrap the existing controls in a **command box**. Recommended ids/classes (any equivalent naming is fine as long
as the pilot asserts the same names it introduces — ids must be stable and exported as module `Final`
constants so the tests can import them):

```
36: APP_ID_INPUT_ID: Final = "app-id-input"        # unchanged
37: RUN_BUTTON_ID: Final = "run-button"            # unchanged
38: STATUS_ID: Final = "check-status"              # unchanged
39: RESULTS_ID: Final = "results"                  # unchanged
40: ERROR_ID: Final = "check-error"                # unchanged
41: ERROR_STYLE: Final = "bold red"                # unchanged
+   TITLE_ID: Final = "keniran-title"              # new: "Keniran" header/title
+   WORDMARK_ID: Final = "keniran-wordmark"        # new: large "keniran" wordmark
+   TAGLINE_ID: Final = "keniran-tagline"          # new: tagline Static
+   COMMAND_BOX_ID: Final = "command-box"          # new: bordered App ID/Run group
```

Suggested `compose()` (behaviour identical to today):

```python
def compose(self) -> ComposeResult:
    yield Header()
    with Vertical(id="home"):
        yield Static("Keniran", id=TITLE_ID, classes="brand-title")
        yield Static("keniran", id=WORDMARK_ID, classes="brand-wordmark")
        yield Static(TAGLINE, id=TAGLINE_ID, classes="brand-tagline")
        with Container(id=COMMAND_BOX_ID, classes="command-box"):
            with Horizontal(id="app-id-row"):
                yield Input(
                    placeholder="Steam App ID",
                    id=APP_ID_INPUT_ID,
                    restrict=r"[0-9]*",
                )
                yield Button("Run", id=RUN_BUTTON_ID, variant="primary")
    yield Container(id=RESULTS_ID)
    yield Footer()
```

- `TAGLINE` should be a module-level `Final` string equal to **exactly**
  `Check whether your PC can run a Steam game.` (approved copy, `.spec/decisions.md:252-255`).
- The `Keniran` title can be a `Static` (and/or `App.TITLE`); the wordmark is a separate, *large* `Static` whose
  text is exactly `keniran` (lowercase, per the task text "large `keniran` wordmark"). Keep `App.TITLE`/`SUB_TITLE`
  as they are (`keniran` / `Can I run it?`) so the `Header` keeps working and the existing theme/title behaviour
  is unchanged; the *brand title* is the new `#keniran-title` Static with the text `Keniran`.
- `#app-id-row` may stay inside the command box (keeping the existing id means the existing CSS selector
  `#app-id-row` keeps matching) — the only structural change is the extra wrapper container.
- `#results` must remain a `Container` mounted as a direct child of the screen, because
  `_show_status` / `_show_error` / `_show_report` / `_clear_results` do
  `self.query_one(f"#{RESULTS_ID}", Container)` (works at any depth) and the pilot asserts
  `tui.query_one(f"#{RESULTS_ID}", Container)`. Keeping it top-level also keeps the results area full-width.

### 4.2 CSS plan (theme tokens first, hex fallback)

Use Textual theme tokens so a runtime theme switch keeps working; the *fallback* hex values below are exactly
the `tokyo-night` values, so the two coincide under the default theme.

```python
CSS = """
Screen {
    background: $background;
}

/* --- brand block --- */
#keniran-title {
    color: $text-muted;
    text-style: bold;
    height: auto;
}

#keniran-wordmark {
    color: $primary;
    text-style: bold;
    height: auto;
    /* large wordmark: bigger via padding/margin + a distinct font treatment */
}

#keniran-tagline {
    color: $text-muted;
    height: auto;
}

/* --- primary command box --- */
#command-box {
    border: round $panel;
    background: $surface;
    padding: 1 2;
    height: auto;
}

#app-id-row {
    height: auto;
}

#app-id-input {
    width: 32;
}

#run-button {
    margin-left: 2;
}

/* --- results --- */
#results {
    height: 1fr;
    padding: 0 2;
}
"""
```

Palette mapping (design contract → token → tokyo-night hex):

| intent | token | hex under `tokyo-night` |
|---|---|---|
| dark slate/navy base | `$background` | `#1A1B26` |
| pane / grouping surface | `$panel` / `$surface` | `#414868` / `#24283B` |
| muted lavender primary highlight | `$primary` | `#BB9AF7` |
| restrained warm accent | `$accent` | `#FF9E64` |
| body text | `$text` / `$foreground` | `#a9b1d6` |
| secondary/muted text | `$text-muted` | derived |

Use the warm accent **restrainedly** — e.g. only on the `Run` button's `border`/accent detail or a thin rule, not
on body text. Keep body text on `$text`/`$foreground` so contrast stays legible (the acceptance asks for legible
contrast; do not put `$accent` on long text).

Textual has no CSS `font-size`; "large" wordmark = bold + `$primary` + surrounding whitespace (`padding`/`margin`)
+ maybe a `border-top`/rule. If you want a genuinely bigger glyph, the accepted trick is a `Static` with
`text-style: bold` inside a larger container, or a Rich renderable with a big `Text` style — keep it simple and
legible.

### 4.3 How to keep the existing pilot tests green

- Do **not** change `APP_ID_INPUT_ID`, `RUN_BUTTON_ID`, `STATUS_ID`, `RESULTS_ID`, `ERROR_ID`, `ERROR_STYLE`.
- Keep `Input(restrict=r"[0-9]*")` and `Button("Run", variant="primary")` exactly as they are.
- Keep `#results` a `Container` and keep it empty on mount (`len(results.children) == 0` at line 199).
- Keep `Header()` and `Footer()` mounted (lines 193-194) — do **not** replace `Header()` with a custom title bar.
- Keep `theme = "tokyo-night"` and `tui.current_theme.name == "tokyo-night"`.
- Keep `compose()` yielding the widgets in an order where the `Input` and `Button` are focusable/reachable and
  the `Input` is not clipped (see gotchas on `height: auto` / explicit heights).
- New brand widgets must **not** be mounted inside `#results` (it must stay empty on mount) and must not steal
  focus from the `Input`.

## Reference patterns to imitate

- `src/keniran/tui/app.py:36-41` — how module-level id constants are declared (`Final` + uppercase name).
- `src/keniran/tui/app.py:51-69` — the existing `CSS` block shape (id selectors, 4-space indentation inside the
  triple-quoted string).
- `src/keniran/tui/app.py:92-102` — the `compose()` shape (`yield` + `with Horizontal(...)` context managers).
- `src/keniran/tui/app.py:177-182` / `184-189` — how a `Static` with an id is mounted and how a `rich.text.Text`
  is used for styled content (the `Static(Text(..., style=...))` idiom).
- `tests/test_tui.py:186-201` — the shell pilot test to imitate for the new brand assertions (same
  `async with tui.run_test():` + `query_one` shape).
- `tests/test_tui.py:98-102` — the `_click_run` helper (waits out the button's `-active` press animation).
- `tests/test_tui.py:89-95` — the `_error_texts` helper (reads `child.content.plain`).
- `tests/test_tui.py:46-54` — the import block of app constants (add the new ids here).
- `.spec/units/v1.0.1/requirement-alternatives/briefs/ALT-001.md` — house style for a spec brief (not needed for
  the code, but it is the ledger's expected format).

## Contracts & types touched

- `KeniranTui.compose()` in `src/keniran/tui/app.py:92` — **signature unchanged** (`-> ComposeResult`); the
  yielded widget tree gains the brand block and the command-box wrapper; all pre-existing widgets and ids are
  preserved.
- `KeniranTui.CSS` in `src/keniran/tui/app.py:51` — still a plain `str` class attribute; only selectors/properties
  change. It must parse under Textual 8.2.8 (unknown property or undefined `$variable` → CSS parse error at
  startup → the app fails to mount → every pilot test fails).
- `KeniranTui.theme` / `TITLE` / `SUB_TITLE` in `src/keniran/tui/app.py:47-49` — **unchanged**
  (`theme == "tokyo-night"` is pinned by `tests/test_tui.py:191-192`).
- `APP_ID_INPUT_ID`, `RUN_BUTTON_ID`, `STATUS_ID`, `RESULTS_ID`, `ERROR_ID`, `ERROR_STYLE` — **unchanged values**;
  they are imported by `tests/test_tui.py:46-54`.
- `Input.restrict` — still `r"[0-9]*"` (pinned at `tests/test_tui.py:196`).
- `run_tui()` in `src/keniran/tui/app.py:208` — **unchanged name/signature** (monkeypatched at
  `tests/test_tui.py:593`).
- New module constants (e.g. `TITLE_ID`, `WORDMARK_ID`, `TAGLINE_ID`, `COMMAND_BOX_ID`, `TAGLINE`) — new `Final`
  strings; exported for the pilot to import.

## Gotchas

1. **CSS is parsed at startup.** A malformed selector, an unknown property, or a `$variable` that is not defined
   raises during stylesheet parsing and the app never mounts → *every* pilot test fails with a confusing error.
   Only use properties/variables listed in section 3.
2. **`Static` has `height: auto` by default** (`textual/widgets/_static.py:26-30`), but a `Static` inside a
   `Horizontal`/`Vertical` with `height: auto` on the parent works only if the parent has a real height. Give
   brand blocks explicit `height: auto` and the command box `height: auto`; give the results container
   `height: 1fr` so it still fills the leftover space.
3. **`height: 1fr` on a wrapper that also holds `1fr` siblings** can starve the content. Keep exactly one `1fr`
   region (`#results`) and let the brand/command regions be `auto`.
4. **`dock` removes a widget from the flow.** `Header`/`Footer` are docked by default (`_header.py:120-126`);
   do not add `dock` to your new widgets unless you intend it to float over content.
5. **Input inside a bordered container can be clipped.** A `Container` with `border: round $panel` adds 2 rows of
   border; if the container's height is fixed, the `Input` may be cut off in the headless pilot (the default
   pilot size is ~80x24). Prefer `height: auto` + `padding`, and verify the `Input`'s `region` is non-zero in the
   pilot if you see oddities. `Input` also has `compact=True` (`textual/widgets/_input.py:374`) if you want the
   command box border to be the only frame.
6. **`Static.content` typing.** A `str` content has no `.plain`; a `rich.text.Text` does. Choose deliberately:
   `Text("keniran")` if the test should read `.plain`, plain `str` if it should read `str(content)`.
7. **`Static` renders console markup by default** (`markup: True`, `_static.py:38`). A tagline containing `[` would
   be parsed as markup — avoid square brackets in the copy, or pass `markup=False`.
8. **`Static` with `Text(...)` content and a `style=`** — `ERROR_STYLE` ("bold red") is asserted as
   `content.style == ERROR_STYLE` (`tests/test_tui.py:447`). Do not restyle the error `Static`; leave
   `_show_error` alone.
9. **`theme` is a Reactive on `App` (`textual/app.py:560`) but the subclass assigns a plain class attribute**
   (`theme = "tokyo-night"`, `src/keniran/tui/app.py:49`). The class attribute shadows the descriptor, so
   `self.theme = "..."` at runtime creates an *instance* attribute and the `_watch_theme` watcher
   (`textual/app.py:1503-1521`) may not fire — i.e. the theme name changes but the CSS variables can stay at the
   initially computed theme. **Recommendation: do not "fix" this in TUIX-001** (out of scope, and it would change
   the `theme == "tokyo-night"` contract). Keep the class attribute exactly as-is so `tui.theme ==
   "tokyo-night"` and `tui.current_theme.name == "tokyo-night"` keep holding. Because theme-token CSS values are
   resolved from the theme at stylesheet build time, `$primary` will render as tokyo-night lavender
   (`#BB9AF7`) — which is exactly the wanted palette.
10. **Mypy scope:** `[tool.mypy] files = ["src"]` (`pyproject.toml:47-50`) — `src/keniran/tui/app.py` **is** checked,
    but only in the moderate mode; `strict = true` applies to `keniran.core.*` only (`pyproject.toml:56-58`).
    Still: annotate new functions, keep `from __future__ import annotations`, no implicit `Optional`.
11. **Ruff:** line-length 100, `target-version = "py311"`, lint `E,F,W,I,UP,B,SIM,RUF`, format `quote-style =
    "double"` (`pyproject.toml:36-45`). Tests are linted too (`src = ["src", "tests"]`).
12. **Don't touch the worker/error path.** `_request_check` validates via `int(raw)` + `raw.isdigit()`; `_show_error`
    formats `f"Error: {message}"`; both are asserted verbatim by the pilot. Visual work must not alter them.
13. **The `Header` shows `TITLE — SUB_TITLE`** ("keniran — Can I run it?"), which is *not* the new brand title.
    The acceptance's "clear `Keniran` header/title" is satisfied by the new `#keniran-title` Static (text
    `Keniran`) — do not repurpose `App.TITLE` unless you also keep the header rendering sane; changing
    `App.TITLE` is harmless to the current tests but is unnecessary churn.
14. **The results area must stay empty on mount** (`tests/test_tui.py:199`) — do not mount a placeholder
    ("Ready." / empty-state hint) inside `#results`.
15. **Pilot default size.** Tests do not pass `size=` to `run_test()`; the default terminal is roughly 80x24. Keep
    the brand block compact (a handful of rows) so the `Input`/`Button` remain visible in the default pilot.
    TUIX-002 (a separate task) owns short-height/scrolling behaviour — do not build a `VerticalScroll` layout here
    beyond what TUIX-001 needs.
16. **Commit convention** (`.spec/conventions.md:26-28`): one task = one commit, message
    `TUIX-001: Add the Keniran branded home hierarchy and reference-inspired styling`, with the task's tests in
    the same commit.

## Required reading

- `src/keniran/tui/app.py` (whole file — 210 lines; especially 36-41, 44-69, 92-102, 104-205)
- `tests/test_tui.py` (whole file — 639 lines; especially 46-54, 59-102, 186-217, 285-338)
- `src/keniran/rendering/report_view.py:72-102` (`report_renderables` — the mounted renderables; **must not change**)
- `.spec/units/v1.0.1/tui-redesign/spec.md` (unit spec: "Changed Contracts", "Open Questions" — exact hex/spacing
  are intentionally flexible)
- `.spec/units/v1.0.1/tui-redesign/tasks.md` (TUIX-001 vs TUIX-002 split; TUIX-002 owns scrolling/short heights)
- `.spec/units/v1.0.1/tui-redesign/active-context.md` (design contract summary, preserve list)
- `.spec/decisions.md:230-235` (TUI visual direction) and `.spec/decisions.md:252-255` (approved tagline copy)
- `.spec/units/v1.0.0/tui/spec.md` (theme decision: `tokyo-night` default, runtime-swappable, non-binding)
- `.spec/conventions.md` (acceptance commands, code style, commit convention)
- Textual 8.2.8 sources (read-only reference, in `.venv/Lib/site-packages/textual/`):
  `design.py:106-508` (theme variables), `theme.py:177-192` (tokyo-night palette),
  `widgets/_header.py:116-228` (Header), `widgets/_static.py` (Static), `widgets/_input.py:354-406` (Input),
  `containers.py:19-261` (containers), `css/styles.py:96-215` (CSS properties), `css/types.py:11-30` (border styles)

## Acceptance

```
python -m pytest tests/test_tui.py -q
python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
```

### Acceptance checklist → concrete pilot assertion

| # | Acceptance criterion | Concrete pilot assertion to add (in `tests/test_tui.py`, right after `test_app_mounts_shell_with_tokyo_night_theme`, line 201) |
|---|---|---|
| 1 | Clear `Keniran` header/title on mount | `title = tui.query_one(f"#{TITLE_ID}", Static)` → `assert "Keniran" in str(title.content)` (e.g. `str(title.content).strip() == "Keniran"`) |
| 2 | Large `keniran` wordmark | `wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)` → `assert "keniran" in str(wordmark.content)` and `assert wordmark.has_class("brand-wordmark")` (class assertion pins the "large" role) |
| 3 | Tagline `Check whether your PC can run a Steam game.` | `tagline = tui.query_one(f"#{TAGLINE_ID}", Static)` → `assert "Check whether your PC can run a Steam game." in str(tagline.content)` (or `== str(TAGLINE)` if a `TAGLINE` constant is exported) |
| 4 | Visually grouped primary App ID/Run command box | `box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)` → `assert box.has_class("command-box")`; `assert tui.query_one(f"#{APP_ID_INPUT_ID}", Input) in box.query(Input)` (or `box.query_one(Input)`) and `assert tui.query_one(f"#{RUN_BUTTON_ID}", Button) in box.query(Button)` — proves the two controls are inside the group |
| 5 | Grouping is *visual* (bordered pane) | `assert box.styles.border_top is not None` / `assert box.styles.border_top` (Textual `Styles.border_top` is a `(style, color)` tuple) — or, more robustly, assert the CSS rule exists: `assert "command-box" in KeniranTui.CSS and "border" in KeniranTui.CSS` |
| 6 | Dark slate/navy base, muted lavender primary, restrained warm accent, theme tokens used | assert the stylesheet references theme tokens: `assert "$primary" in KeniranTui.CSS`, `assert "$accent" in KeniranTui.CSS`, `assert "$panel" in KeniranTui.CSS` (or `$background`/`$surface`); optionally assert the wordmark's computed colour resolves to the lavender `#BB9AF7` via `wordmark.styles.color` / `tui.get_css_variables()["primary"]` |
| 7 | Legible text contrast | `assert tui.get_css_variables()["text"] != tui.get_css_variables()["background"]` (theme sanity) and the tagline/widget colours use `$text`/`$text-muted`, not the accent — assert `"$text" in KeniranTui.CSS` |
| 8 | `theme == "tokyo-night"` retained | already pinned by `tests/test_tui.py:191-192`; **do not modify** that test (optionally add `assert tui.current_theme.name == "tokyo-night"` in the new test too) |
| 9 | Input digit restriction unchanged | already pinned by `tests/test_tui.py:196` and `test_app_id_input_rejects_non_digits` (204) — unchanged |
| 10 | Run control unchanged | already pinned by `tests/test_tui.py:197` + the worker/status tests (223, 285) — unchanged |
| 11 | Worker / status / result / error behaviour unchanged | already pinned by tests 285, 341, 387, 421, 481, 526, 547 — unchanged |
| 12 | CLI contracts unchanged | already pinned by tests 572, 590, 626 — unchanged |
| 13 | New pilot assertions exist for branded widgets + command-box structure | the new test(s) added in step 1-4 above |

Suggested new test names (one focused test per concern, matching repo style):
`test_home_screen_shows_the_keniran_brand_block`, `test_app_id_and_run_controls_are_grouped_in_the_command_box`,
`test_branded_styles_use_textual_theme_tokens`.

## Open uncertainties

- **Exact ids/classes.** The unit spec leaves "exact CSS hex values, borders, and spacing … intentionally
  flexible" (`.spec/units/v1.0.1/tui-redesign/spec.md:48-50`). The ids proposed above
  (`#keniran-title`, `#keniran-wordmark`, `#keniran-tagline`, `#command-box`) are a **recommendation**; any
  stable naming works as long as the pilot asserts the same names the app uses. Keep them as module-level
  `Final` constants so the test imports them rather than hard-coding strings.
- **"Large" wordmark without a font-size.** Textual has no `font-size` CSS property. Acceptable readings:
  bold + `$primary` + extra vertical whitespace, or a Rich `Text` with a larger style. The implementer should pick
  one and pin it with a class/structure assertion (not a pixel assertion).
- **Where the `Keniran` title lives.** Options: (a) a new `Static` (`#keniran-title`), or (b) changing
  `App.TITLE`/`SUB_TITLE`. The existing header test only checks that a `Header` exists, so (b) is *possible* — but
  (a) is recommended because it keeps the header semantics and the task's "Keniran header/title" requirement
  independently satisfied. Do both only if it stays legible.
- **Runtime theme switching and CSS variables.** The `theme` class attribute shadows the `App.theme` Reactive
  (gotcha 9), so a runtime switch may not refresh the CSS variables. TUIX-001 is not the place to fix that
  (out of scope), but if the reviewer expects `$primary` to follow a runtime theme switch, flag it rather than
  silently re-plumbing the theme machinery.
- **Vertical scrolling / short heights** belong to **TUIX-002** (it depends on TUIX-001). Do not add a
  `VerticalScroll` layout here beyond what keeps the default pilot size healthy.
- **Command-box border style.** `round` is suggested; `panel`/`tall`/`heavy`/`solid` are all valid
  (`textual/css/types.py:11-30`). The mood reference is a *reference*, not a target — do not clone a
  finance-dashboard pane arrangement.
- **Whether `ruff format .` will touch the sibling ALT-001 files** (`src/keniran/core/requirements_parser.py`,
  `tests/test_requirements_parser.py`). If it does, leave the reformat in place and report it; do not revert or
  edit those files.
