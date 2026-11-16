# Brief — TUIX-002: Keep the home and results usable at short terminal heights

seam: After TUIX-001 (commit cb4ce93) `src/keniran/tui/app.py` composes `Header()` → `Vertical(id="home")`
(brand title/wordmark/tagline + bordered `#command-box` holding `#app-id-row` with the `Input`/`Button`) →
`Container(id="results")` → `Footer()`, with `#home { height: auto }` and `#results { height: 1fr }`.
The defect TUIX-002 owns is **vertical clipping, not branding**: a plain `Container` has Textual's default
`overflow: hidden hidden` (`.venv/Lib/site-packages/textual/containers.py:22-28`), so when the report
renderables mounted into `#results` are taller than the `1fr` results box they are drawn outside it and are
**unreachable** — nothing scrolls them into view. The only vertical scrolling that exists today is the
*Screen's* implicit `overflow-y: auto` (`.venv/Lib/site-packages/textual/screen.py:174-178`), an invisible
side effect of the library default that never covers the clipped `#results` children. The seam is therefore
purely a **layout/scroll-region change**: make the app body an explicit vertically scrollable region (or give
`#results` `overflow-y: auto`) so that home content *and* long results stay reachable at short terminal heights
(80x16), while every id, class, handler, worker, report-rendering and CLI contract from TUIX-001 stays
byte-for-byte intact. No new commands or controls, no report-rendering change, no theme persistence, no new
dependencies.

## Files in play

- `src/keniran/tui/app.py` — the only production file to change (`compose()` + `CSS`).
- `tests/test_tui.py` — the only test file to change (new pilot tests for the three terminal sizes).
- `src/keniran/rendering/report_view.py` — context only; **must not change** (`report_renderables` output is
  pinned by `tests/test_tui.py:429-472`).
- `.spec/units/v1.0.1/tui-redesign/spec.md`, `.spec/units/v1.0.1/tui-redesign/active-context.md`,
  `.spec/units/v1.0.1/tui-redesign/tasks.md`, `.spec/conventions.md` — binding context (read-only).
- `.venv/Lib/site-packages/textual/**` — Textual **8.2.8** sources, read-only reference (citations below).

### Tree-state constraint (do not violate)

The working tree holds **uncommitted sibling-task work** (blocked task ALT-001) in
`src/keniran/core/requirements_parser.py` and `tests/test_requirements_parser.py`, plus untracked
`.spec/units/v1.0.1/**` ledger/brief files. **Do not read-modify, stage, revert, or "clean up" those two
files.** Touch only `src/keniran/tui/app.py` and `tests/test_tui.py`. `ruff format .` may reformat the sibling
files if they are not already formatted — if that happens, leave the reformat in place (do not revert) and
mention it in the task report.

### Out of scope (explicit)

New commands or controls, report rendering changes (`keniran.rendering.report_view`), a custom persistent
theme, new dependencies, `keniran.services.check_game`, `keniran.core.scoring`, `keniran.cli.app`, matching /
scoring behaviour, search/history features.

## 1. CURRENT post-TUIX-001 shape of `src/keniran/tui/app.py` (265 lines)

### 1.1 Module header

| lines | content |
|---|---|
| 1-22 | module docstring (TUI as second renderer, thread worker, inline failure paths, branded home) |
| 24-39 | imports — note `from textual.containers import Container, Horizontal, Vertical` (line 32) |
| 41-46 | `APP_ID_INPUT_ID`, `RUN_BUTTON_ID`, `STATUS_ID`, `RESULTS_ID`, `ERROR_ID`, `ERROR_STYLE` — **do not rename** |
| 48-51 | `TITLE_ID="keniran-title"`, `WORDMARK_ID="keniran-wordmark"`, `TAGLINE_ID="keniran-tagline"`, `COMMAND_BOX_ID="command-box"` |
| 53 | `TAGLINE = "Check whether your PC can run a Steam game."` |
| 56-61 | `class KeniranTui(App[None])`, `TITLE="keniran"`, `SUB_TITLE="Can I run it?"`, `theme="tokyo-night"` |
| 63-117 | `CSS` block |
| 119-138 | `__init__` (injection seams) — do not touch |
| 140-157 | `compose()` |
| 159-260 | handlers/worker plumbing — behaviour that must not change |
| 263-265 | `run_tui()` (monkeypatched by `tests/test_tui.py:678-686`) — name must stay |

### 1.2 `compose()` — the exact seam (140-157)

```
140:    def compose(self) -> ComposeResult:
141:        yield Header()
142:        with Vertical(id="home"):
143:            yield Static("Keniran", id=TITLE_ID, classes="brand-title")
144:            yield Static("keniran", id=WORDMARK_ID, classes="brand-wordmark")
145:            yield Static(TAGLINE, id=TAGLINE_ID, classes="brand-tagline")
146:            with (
147:                Container(id=COMMAND_BOX_ID, classes="command-box"),
148:                Horizontal(id="app-id-row"),
149:            ):
150:                yield Input(
151:                    placeholder="Steam App ID",
152:                    id=APP_ID_INPUT_ID,
153:                    restrict=r"[0-9]*",
154:                )
155:                yield Button("Run", id=RUN_BUTTON_ID, variant="primary")
156:        yield Container(id=RESULTS_ID)
157:        yield Footer()
```

Widget tree (ids/classes that must survive):

| order | widget | id | classes | parent | TUIX-001 test that pins it |
|---|---|---|---|---|---|
| 1 | `Header` | — | — | Screen (docked top) | `tests/test_tui.py:198` |
| 2 | `Vertical` | `home` | — | Screen | *(no test queries `#home` — only the test name mentions "home")* |
| 3 | `Static` | `keniran-title` | `brand-title` | `#home` | `tests/test_tui.py:213-214` |
| 4 | `Static` | `keniran-wordmark` | `brand-wordmark` | `#home` | `tests/test_tui.py:216-218` |
| 5 | `Static` | `keniran-tagline` | `brand-tagline` | `#home` | `tests/test_tui.py:220-222` |
| 6 | `Container` | `command-box` | `command-box` | `#home` | `tests/test_tui.py:226, 237-238` |
| 7 | `Horizontal` | `app-id-row` | — | `#command-box` | (CSS selector only) |
| 8 | `Input` | `app-id-input` | — | `#app-id-row` | `tests/test_tui.py:200-201, 240-242` |
| 9 | `Button` | `run-button` | — | `#app-id-row` | `tests/test_tui.py:202, 241-243` |
| 10 | `Container` | `results` | — | Screen (top level) | `tests/test_tui.py:203-204, 446, 498, 603` |
| 11 | `Footer` | — | — | Screen (docked bottom) | `tests/test_tui.py:199` |

### 1.3 `CSS` block (63-117) — the second seam

```
63:    CSS = """
64:    Screen {
65:        background: $background;
66:    }
67:
68:    #home {
69:        height: auto;
70:        width: 1fr;
71:        padding: 1 2 0 2;
72:    }
73:
74:    #keniran-title {
75:        color: $text-muted;
76:        text-style: bold;
77:        height: auto;
78:    }
79:
80:    #keniran-wordmark {
81:        color: $primary;
82:        text-style: bold;
83:        height: auto;
84:        padding: 0 0 1 0;
85:    }
86:
87:    #keniran-tagline {
88:        color: $text-muted;
89:        height: auto;
90:    }
91:
92:    #command-box {
93:        border: round $panel;
94:        background: $surface;
95:        height: auto;
96:        width: 1fr;
97:        padding: 0 1;
98:    }
99:
100:   #app-id-row {
101:       height: auto;
102:   }
103:
104:   #app-id-input {
105:       width: 32;
106:   }
107:
108:   #run-button {
109:       margin-left: 2;
110:       border: tall $accent;
111:   }
112:
113:   #results {
114:       height: 1fr;
115:       padding: 0 2;
116:   }
117:   """
```

### 1.4 Height analysis — where the clipping happens

| region | declared height | effective | scrollable? |
|---|---|---|---|
| `Screen` | library default `layout: vertical; overflow-y: auto` (`screen.py:174-178`) | fills the terminal | **yes**, but only for content that overflows the Screen's own box |
| `Header` | docked top, height 1 | 1 row, **never scrolls** (docked) | n/a |
| `#home` (`Vertical`) | `height: auto` (`app.py:69`) | ≈ 10 rows (1 pad + 1 title + 1 wordmark + 1 wordmark pad + 1 tagline + 5 command box) | **no** — `Vertical` DEFAULT_CSS is `overflow: hidden hidden` (`containers.py:124-131`) |
| `#command-box` | `height: auto` | 5 rows (2 border + 3 input/button) | no |
| `#results` (`Container`) | `height: 1fr` (`app.py:114`) | leftover rows (e.g. 4 at 80x16, 14 at 100x30) | **NO** — `Container` DEFAULT_CSS is `width: 1fr; height: 1fr; layout: vertical; overflow: hidden hidden` (`containers.py:22-28`) |
| `Footer` | docked bottom, height 1 | 1 row, **never scrolls** | n/a |

**The defect:** report renderables mounted into `#results` (4 `Static`s per report, several rows tall) overflow
the `1fr` box and are **clipped and unreachable** — `Container` has `overflow: hidden hidden`, and `#results`
declares no `overflow-y`, so `styles.overflow_y` stays `"hidden"` (the library default,
`.venv/Lib/site-packages/textual/css/styles.py:384-390`). A widget is only scrollable when its
`styles.overflow_y` is `auto`/`scroll` **and** `virtual_size` exceeds the box
(`.venv/Lib/site-packages/textual/widget.py:2080-2137`).

**The fr-collapse rule to remember:** in a vertical layout, `1fr` children receive
`remaining_space = max(0, size.height - <auto children> - margins)`
(`.venv/Lib/site-packages/textual/_resolve.py:309-335`) — so an `auto` sibling that overflows the parent
**collapses the `1fr` sibling to 0 rows** and pushes the overflow up to the Screen (whose `overflow-y: auto`
then scrolls it). This is why "make `#results` `1fr` *and* scroll it" cannot work while `#home` is `auto` and
tall: the results box becomes 0 rows and its content is unreachable.

## 2. Pilot size control and assertion APIs (Textual 8.2.8, verified in `.venv`)

### 2.1 Controlling the terminal size

- `App.run_test(*, headless: bool = True, size: tuple[int, int] | None = (80, 24), tooltips=False, notifications=False, message_hook=None)`
  — `.venv/Lib/site-packages/textual/app.py:2133-2141`. **`size` is `(WIDTH, HEIGHT)`** and it is the
  headless terminal size; `size=None` auto-detects. Use `async with tui.run_test(size=(100, 30)) as pilot:`.
  The default is `(80, 24)`, so "the default size" test = `async with tui.run_test() as pilot:`.
- `Pilot.resize_terminal(width, height)` — `.venv/Lib/site-packages/textual/pilot.py:86-98` — posts a `Resize`
  and awaits one `pause()`. Use it when a test must start at one size and shrink afterwards; **always
  `await pilot.pause()` again after it** so the layout is recomputed before asserting regions.
- `Pilot.press(*keys)` — `pilot.py:76-84` (awaits `_wait_for_screen()` internally).
- `Pilot.click(selector)` — `pilot.py:192`.
- `Pilot.pause(delay=None)` — `pilot.py:535` — yields to the event loop; call it after any mount/resize/
  scroll before asserting geometry.
- Terminal size readback: `App.size` → `Size` (`.venv/Lib/site-packages/textual/app.py:1654-1669`);
  `App.viewport_size` → the screen size (`app.py:1671-1674`).

### 2.2 Geometry / clipping assertions

- `Widget.region` → `Region` in **screen** coordinates — `.venv/Lib/site-packages/textual/widget.py:2285-2294`.
  The compositor maps children with the parent's scroll offset applied
  (`.venv/Lib/site-packages/textual/_compositor.py:670-676`), so `region` tracks the *current* scroll position;
  the `full_map` is built with `visible_only=False` (`_compositor.py:480-493`) so off-screen children still have
  a real (off-screen) region rather than a null one.
- `Region.right` / `Region.bottom` — `.venv/Lib/site-packages/textual/geometry.py:489, 494`.
  Use these for "within the screen width" checks: `region.right <= tui.size.width`.
- `Widget.container_size` (`widget.py:2226-2232`), `Widget.virtual_size` (`widget.py:357`, a
  `Reactive[Size]`), `Widget.scrollable_content_region` (`widget.py:2245-2254`),
  `Widget.content_region` (`widget.py:2235-2242`).

### 2.3 Vertical-scroll assertions

- `Widget.scroll_end(*, animate=True, speed=None, duration=None, easing=None, force=False, on_complete=None, level="basic", immediate=False, x_axis=True, y_axis=True)`
  — `.venv/Lib/site-packages/textual/widget.py:3012-3078`. **Use `animate=False`** (the default animates for
  1 s) and then `await pilot.pause()`. `immediate=True` skips the `call_after_refresh` deferral
  (`widget.py:3075-3078`).
- `Widget.scroll_to(x=None, y=None, *, animate=True, ..., immediate=False)` — `widget.py:2859-2918`.
- `Widget.max_scroll_y` → `int` — `widget.py:1989-1995` = `virtual_size.height - (container_size.height - scrollbar_size_horizontal)`, floored at 0.
- `Widget.is_vertical_scroll_end` → `bool` — `widget.py:1997-2000` (`scroll_offset.y == max_scroll_y`).
- `Widget.scroll_offset` → `Offset` — `widget.py:2384-2391`.
- `Widget.show_vertical_scrollbar` → `Reactive[bool]` — `widget.py:378`; the scrollbar is shown when
  `overflow_y == "auto"` and `virtual_size.height > height` (`widget.py:2097-2103`).
- `Widget.scrollbar_size_vertical` / `scrollbar_gutter` — `widget.py:2156-2187` — a visible vertical
  scrollbar **steals one column** of the content width.

### 2.4 Focus / keyboard assertions

- `App.focused` → `Widget | None` — `.venv/Lib/site-packages/textual/app.py:1290-1302`.
- `Widget.focus(scroll_visible=True)` — `.venv/Lib/site-packages/textual/widget.py:4579`.
- `Screen.focus_chain` → focusable widgets **in DOM order, container before its children**
  — `.venv/Lib/site-packages/textual/screen.py:772-826` (the container is appended after its children are
  pushed onto the traversal stack, so it precedes them in the chain).
- `Screen._binding_chain` = `focused.ancestors_with_self` — `.venv/Lib/site-packages/textual/screen.py:408-446`:
  **an ancestor's bindings fire while a descendant is focused.** `ScrollableContainer` ships
  `up / down / left / right / home / end / pageup / pagedown / ctrl+pageup / ctrl+pagedown`
  (`.venv/Lib/site-packages/textual/containers.py:48-74`).
- `Input.check_consume_key` returns `True` only for **printable** characters
  (`.venv/Lib/site-packages/textual/widgets/_input.py:498-510`), so `tab`, `up`, `down`, `end` are *not*
  swallowed by the Input. The Input binds `home,ctrl+a` and `end,ctrl+e` itself
  (`_input.py:75-142`), so those two stay with the Input (the focused widget's own bindings are checked first).
- The Screen binds `tab` → `app.focus_next` and `shift+tab` → `app.focus_previous`
  (`.venv/Lib/site-packages/textual/screen.py:270-271`).
- `App.AUTO_FOCUS = "*"` (`.venv/Lib/site-packages/textual/app.py:396`) and
  `Screen._update_auto_focus` focuses the **first focusable widget in DOM order** on mount
  (`.venv/Lib/site-packages/textual/screen.py:1489-1500`). Today that is the `Input` — **any new focusable
  ancestor inserted before it would steal the auto-focus.**

### 2.5 Containers available in 8.2.8

`.venv/Lib/site-packages/textual/containers.py`:

| class | line | DEFAULT_CSS |
|---|---|---|
| `Container` | 19-28 | `width: 1fr; height: 1fr; layout: vertical; overflow: hidden hidden` |
| `ScrollableContainer` | 32-118 | `width: 1fr; height: 1fr; layout: vertical; overflow: auto auto`; `can_focus=True`; scroll BINDINGS at 48-59; `__init__(..., can_focus=None, can_focus_children=None, ...)` at 76-112 |
| `Vertical` | 121-131 | `width: 1fr; height: 1fr; layout: vertical; overflow: hidden hidden` (no scrollbars) |
| `VerticalGroup` | 134-144 | `height: auto`, `overflow: hidden hidden` |
| `VerticalScroll` | 147-156 | `layout: vertical; overflow-x: hidden; overflow-y: auto` (inherits `ScrollableContainer`'s `width/height: 1fr`) |

`VerticalScroll` is **not** a subclass of `Container` (it derives from `ScrollableContainer` → `Widget`), so
it can never be used for `#results` (see §4.1).

## 3. Concrete test plan (three sizes)

New tests go in `tests/test_tui.py` in the "Textual shell" section, **after**
`test_branded_styles_use_textual_theme_tokens` (ends line 289) and before
`test_app_id_input_rejects_non_digits` (line 292). Use the house shape
`def test_x() -> None:` → `async def scenario() -> None:` → `_run(scenario())` (`tests/test_tui.py:64-66`).
Do **not** modify any existing test.

### 3.1 `test_home_hierarchy_fits_at_the_normal_terminal_size` — 100x30

```python
async with tui.run_test(size=(100, 30)) as pilot:
    assert tui.size.width == 100 and tui.size.height == 30
    title = tui.query_one(f"#{TITLE_ID}", Static)
    wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
    tagline = tui.query_one(f"#{TAGLINE_ID}", Static)
    box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
    results = tui.query_one(f"#{RESULTS_ID}", Container)
    # hierarchy order survives the layout change
    assert title.region.y < wordmark.region.y < tagline.region.y < box.region.y
    assert results.region.y >= box.region.y  # results live below the command box
    # everything is inside the visible screen
    assert box.region.bottom <= tui.size.height
    assert results.region.bottom <= tui.size.height
    # the results region is a real, non-empty region at the normal size
    assert results.region.height > 0
    assert len(results.children) == 0  # still empty on mount
```

### 3.2 `test_app_id_and_run_controls_are_not_horizontally_clipped` — 100x30 **and** 80x16

Parametrise by looping over the two sizes in one test, or write two tests; both must pass.

```python
for size in ((100, 30), (80, 16)):
    tui = KeniranTui()
    async with tui.run_test(size=size) as pilot:
        app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
        run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)
        for widget in (app_id_input, run_button):
            region = widget.region
            assert region.width > 0 and region.height > 0
            assert region.x >= 0
            assert region.right <= tui.size.width  # no horizontal clipping
        # the controls are on screen (not pushed off the bottom / hidden)
        assert run_button.region.bottom <= tui.size.height
        assert app_id_input.region.bottom <= tui.size.height
```

Note: `Input` is `width: 32` (`app.py:104-106`) and the command box adds 2 border + 2 padding columns, so at
80 columns the controls fit with room to spare — the assertion is about *geometry*, not about a specific width.

### 3.3 `test_controls_remain_keyboard_reachable_at_a_compact_size` — 80x16

```python
async with tui.run_test(size=(80, 16)) as pilot:
    app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
    run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)

    app_id_input.focus()
    await pilot.pause()
    assert tui.focused is app_id_input  # the input is focusable and focused

    await pilot.press("7", "2", "8")  # typing still reaches the input
    assert app_id_input.value == "728"

    await pilot.press("tab")  # Screen binding -> app.focus_next
    await pilot.pause()
    assert tui.focused is run_button  # Tab reaches the Run control
```

If the implementation introduces a **focusable** scroll container, `tab` may land on that container first
(`Screen.focus_chain` puts a container before its children, `screen.py:772-826`). Then either press `tab`
twice, or assert `run_button in tui.screen.focus_chain` instead of the exact `tab` landing spot. Preferred:
make the scroll container **non-focusable** so the Input keeps auto-focus and the chain stays
`[input, button]`.

### 3.4 `test_long_results_scroll_to_their_end_at_a_compact_size` — 80x16 (the core test)

Populate `#results` with long content. Two interchangeable ways:

- **Deterministic (recommended):** mount tall `Static`s directly into the results container —
  `await results.mount(*[Static(f"result line {i}") for i in range(40)])`; then `await pilot.pause()`.
- **Realistic:** monkeypatch `keniran.tui.app.check_game` with a fake returning the `full_report` fixture
  (`tests/test_tui.py:156-185`) exactly like `test_completed_check_mounts_the_shared_report_renderables`
  (429-472) does, then click Run. The shared report is ~12 rows — long enough at 80x16 — but the row count is
  implementation-dependent, so the deterministic mount is safer for a *scroll* assertion.

Assertions (adapt the container name to whatever the implementation calls the scroll region; in the
recommended design that is the new `VerticalScroll` body, e.g. `#body`):

```python
body = tui.query_one("#body")  # the scrollable region
assert body.max_scroll_y > 0  # content is longer than the viewport -> scrollable, not clipped
assert body.show_vertical_scrollbar  # a scrollbar exists (overflow-y: auto took effect)
last = results.children[-1]  # the final mounted Static

# BEFORE scrolling the tail is outside the visible box (it would be clipped if overflow were hidden)
assert last.region.bottom > body.region.bottom

body.scroll_end(animate=False)  # Widget.scroll_end -> widget.py:3012
await pilot.pause()

assert body.scroll_offset.y == body.max_scroll_y
assert body.is_vertical_scroll_end  # widget.py:1997-2000
# the tail is now inside the visible box
assert last.region.y >= body.region.y
assert last.region.bottom <= body.region.bottom
```

If the implementation keeps the *lighter* design (no new wrapper; `#results` itself scrolls), then `body` is
`tui.query_one(f"#{RESULTS_ID}", Container)` and the same assertions apply to it.

### 3.5 `test_home_and_results_scroll_to_their_end_at_a_very_short_height` — 80x16 (or 80x10)

Proves the **home** block is reachable too, not only the results:

```python
async with tui.run_test(size=(80, 16)) as pilot:
    home = tui.query_one("#home")
    await home.mount(*[Static(f"home filler {i}") for i in range(30)])
    await pilot.pause()
    body = tui.query_one("#body")
    assert body.max_scroll_y > 0
    body.scroll_end(animate=False)
    await pilot.pause()
    assert body.is_vertical_scroll_end
    last = home.children[-1]
    assert last.region.y >= body.region.y
    assert last.region.bottom <= body.region.bottom
```

Alternative to stuffing the home: shrink the terminal with `await pilot.resize_terminal(80, 10)`
(`pilot.py:86-98`) and then `await pilot.pause()` — the home block (~10 rows) no longer fits the ~8-row
viewport, so the body must scroll.

### 3.6 `test_header_and_footer_stay_usable_while_the_body_scrolls` — 80x16

```python
async with tui.run_test(size=(80, 16)) as pilot:
    header = tui.query_one(Header)
    footer = tui.query_one(Footer)
    header_top, footer_bottom = header.region.y, footer.region.bottom
    body = tui.query_one("#body")
    body.scroll_end(animate=False)
    await pilot.pause()
    assert header.region.y == header_top  # docked widgets do not scroll
    assert footer.region.bottom == footer_bottom
    assert header.region.height > 0 and footer.region.height > 0
```

### 3.7 Default size (80x24)

`async with tui.run_test() as pilot:` — assert the same hierarchy as §3.1 (`title < wordmark < tagline < box`,
`results` below the box, `len(results.children) == 0`). This covers "the default size" without changing the
existing `test_app_mounts_shell_with_tokyo_night_theme` (191-206).

## 4. Recommended minimal `app.py` change (and the lighter alternative)

### 4.1 Hard constraints (derived from the current code)

1. **`#results` must stay a `Container`.** Four handlers do
   `self.query_one(f"#{RESULTS_ID}", Container)` (`src/keniran/tui/app.py:235, 242, 249, 256`) and four tests do
   the same (`tests/test_tui.py:203, 446, 498, 603`). `query_one(..., Container)` raises `TypeError` for a
   non-`Container`, and `VerticalScroll`/`ScrollableContainer` are **not** `Container` subclasses
   (`containers.py:19, 32, 147`). → never swap `#results` for a `VerticalScroll`.
2. All ids, classes, `Input.restrict`, `Button(variant="primary")`, the handlers, the worker, `run_tui()`,
   `theme = "tokyo-night"`, `TITLE`/`SUB_TITLE`, and the `CSS` theme tokens must survive unchanged.
3. The CSS must keep parsing: an unknown property or an undefined `$variable` raises during stylesheet
   parsing and the app never mounts → every pilot test fails.

### 4.2 RECOMMENDED: one explicit `VerticalScroll` body (home + results inside it)

`compose()` (140-157) becomes:

```python
def compose(self) -> ComposeResult:
    yield Header()
    with VerticalScroll(id=BODY_ID, can_focus=False):     # can_focus=False keeps the Input auto-focused
        with Vertical(id="home"):
            ... unchanged brand block + command box ...
        yield Container(id=RESULTS_ID)
    yield Footer()
```

CSS changes (only these three rules):

```
#body {                       /* new: the scrollable body */
    width: 1fr;
    height: 1fr;              /* bounded -> its virtual size may exceed the viewport */
}

#home {                       /* unchanged: auto */
    height: auto;
    width: 1fr;
    padding: 1 2 0 2;
}

#results {                   /* CHANGED: 1fr -> auto, so the results can grow past the viewport */
    height: auto;
    width: 1fr;
    padding: 0 2;
    min-height: 3;           /* keeps a visible "initial result region" at the normal size */
}
```

Why this works:

- `VerticalScroll` is `overflow-y: auto` (`containers.py:147-156`), so the body's `virtual_size` may exceed its
  box and the whole body (home **and** results) scrolls to its end (`scroll_end`, `max_scroll_y`).
- `#results` must be `height: auto` **inside** the scroll region: a `1fr` child of a scroll container resolves
  against the viewport (`_resolve.py:309-335`) and pins the virtual size to the viewport → nothing would scroll.
- `#results` keeps `Container` + `overflow: hidden hidden`, but that no longer matters: it is *inside* a
  scrolling ancestor, so the compositor maps it with the parent's scroll offset
  (`_compositor.py:670-676`) and its children are painted as the body scrolls.
- `can_focus=False` keeps the `Input` as the first focusable widget, so `App.AUTO_FOCUS = "*"`
  (`app.py:396`) still focuses the Input on mount (`screen.py:1489-1500`), and `Screen.focus_chain` stays
  `[input, button]` (`screen.py:772-826`). The scroll region's `up/down/pageup/pagedown/end` bindings still
  fire while the Input is focused, because `Screen._binding_chain` is `focused.ancestors_with_self`
  (`screen.py:408-446`) and the Input only consumes printable characters (`_input.py:498-510`).
  *Alternative to `can_focus=False`:* leave the container focusable and set
  `AUTO_FOCUS = f"#{APP_ID_INPUT_ID}"` on `KeniranTui` — but then `tab` lands on the container first
  (see §2.4), so the tab assertion in §3.3 must account for it.

Risk analysis against the TUIX-001 pilot assertions:

| TUIX-001 assertion | Effect of the recommended change |
|---|---|
| `tui.query_one(Header)` / `query_one(Footer)` (`tests/test_tui.py:198-199`) | unaffected — Header/Footer stay top-level and docked |
| `tui.query_one(f"#{RESULTS_ID}", Container)` + `len(children) == 0` (203-204) | unaffected — `#results` is still a `Container`; only its parent changes |
| `title.region.y < wordmark.region.y < tagline.region.y < box.region.y` (227) | unaffected — the brand block keeps its internal order; only its absolute y shifts (still inside the screen) |
| `box.has_class("command-box")`; `app_id_input in list(box.query(Input))`; `run_button in list(box.query(Button))` (238-243) | unaffected — the command box subtree is untouched |
| `box.styles.border_top == ("round", panel)`; `box.styles.background.hex == surface` (246-249) | unaffected — no CSS change to `#command-box` |
| `app_id_input.region.width > 0`, `run_button.region.width > 0` (252-253) | unaffected — widths are unchanged; a vertical scrollbar costs 1 column of the **body**, not of the widgets |
| `$background/$surface/$panel/$primary/$accent/$text-muted in KeniranTui.CSS`; `variables["primary"] == "#BB9AF7"`, `variables["accent"] == "#FE9E64"` (262-277) | unaffected — no token is removed |
| `wordmark.styles.color.hex == variables["primary"]`; `wordmark.styles.text_style.bold` (281-282) | unaffected |
| `tagline.styles.color.a >= 0.5`; `tagline.styles.color.hex != variables["accent"]` (286-287) | unaffected |
| `Input.restrict == r"[0-9]*"` (201) | unaffected |
| worker/status/error/report tests (373-654) | unaffected — same handlers, same `report_renderables`; the report simply mounts inside a scrollable body |

New risks introduced by the recommended change:

- **R1 — the results region loses its "fills the leftover space" look.** With `height: auto` the empty
  `#results` is 0 rows tall; `min-height: 3` restores a visible initial region. If the implementer prefers a
  taller empty state, `min-height: 6` is fine — but every extra row eats viewport space at 80x16.
- **R2 — the body's vertical scrollbar steals one column** (`widget.py:2156-2176`), shrinking the body width
  from 80 to 79. The controls still fit (Input 32 + Button + margins ≈ 42 columns), but the §3.2 assertion must
  compare against `tui.size.width` (the terminal), not against the body's inner width.
- **R3 — `1fr` collapse.** If `#home` is `auto` and `#results` were left at `1fr`, the results box collapses to
  0 rows when the home overflows (`_resolve.py:309-335`) → results unreachable. Hence `height: auto` on
  `#results` is mandatory in this design.
- **R4 — the report table may be wider than the body.** `VerticalScroll` is `overflow-x: hidden`
  (`containers.py:147-156`), so a wide Rich `Table` is clipped horizontally exactly as it is today
  (`Container` is `overflow: hidden hidden`) → no regression, and the acceptance only asks about the
  App ID/Run controls.
- **R5 — auto-focus theft** if the scroll container is left focusable (see §4.2).

### 4.3 LIGHTER ALTERNATIVE (no new wrapper): scroll `#results` itself

Keep the tree exactly as it is and change only the `#results` rule:

```
#results {
    height: 1fr;
    min-height: 3;
    overflow-y: auto;     /* NEW: results scroll internally instead of clipping */
}
```

- The **results** become internally scrollable (`overflow-y: auto` + `virtual_size > box` →
  `widget.py:2097-2103`), reachable with `scroll_end()`.
- The **home** block stays reachable through the *Screen's* implicit `overflow-y: auto`
  (`screen.py:174-178`) when it overflows the Screen box.
- Pros: one CSS line, zero DOM change, zero auto-focus risk, no `1fr`/`auto` retuning, all TUIX-001
  assertions trivially intact.
- Cons: (i) it relies on an *implicit library default* for the home's reachability — a reviewer may not see it;
  (ii) `Container` has **no scroll BINDINGS** (only `ScrollableContainer`/`VerticalScroll` do,
  `containers.py:48-59`), so the results region cannot be scrolled with the keyboard — only by mouse wheel or
  programmatically; (iii) when the home overflows, the `1fr` results box collapses to 0 rows
  (`_resolve.py:309-335`) and the results become unreachable *at that moment* unless `min-height` is set.

### 4.4 Recommendation

**Take §4.2 (explicit `VerticalScroll` body) as the primary implementation**: it satisfies the unit contract
("all home content and long results must remain reachable through VERTICAL SCROLLING") with an explicit,
nameable, assertable scroll region, it gives real keyboard scrolling (up/down/pagedown/end via the ancestor
binding chain), and it does not depend on the Screen's implicit `overflow-y: auto`.
Keep §4.3 in mind as the fallback if the reviewer objects to the extra wrapper — but if you take it, add
`min-height` to `#results` so the results never collapse to zero rows, and note the missing keyboard scroll
bindings in the task report.

## 5. Gotchas

1. **CSS is parsed at startup.** A malformed selector, an unknown property, or an undefined `$variable` raises
   during stylesheet parsing → the app never mounts → *every* pilot test fails with a confusing error. Only use
   properties from `textual/css/styles.py:96-215` (`overflow-x/y` included) and theme variables that exist
   (`$background`, `$surface`, `$panel`, `$primary`, `$accent`, `$text-muted`, …).
2. **`overflow-y: auto` vs `scroll`.** `auto` shows the scrollbar only when `virtual_size` exceeds the box
   (`widget.py:2097-2103`); `scroll` always shows it. Use `auto`.
3. **`overflow` shorthand.** `Container`/`Vertical` DEFAULT_CSS use `overflow: hidden hidden` — that sets
   **both** axes. Setting only `overflow-y: auto` on a rule that also matches a `hidden` shorthand is fine
   (the longhand wins by order), but keep the selectors unambiguous.
4. **Scrollbars take width.** A visible vertical scrollbar removes one column from the container's content
   (`widget.py:2156-2187`); a horizontal scrollbar removes one row. The body's width shrinks from 80 to 79 at
   80x16 — always compare widget regions against `tui.size.width` (the terminal), not against the body width.
5. **Docked `Header`/`Footer` never scroll.** They are `dock: top` / `dock: bottom`
   (`textual/widgets/_header.py`, `textual/widgets/_footer.py`) and are excluded from the scrollable area via
   `dock_gutter` (`widget.py:2296-2306`). Assert their regions are unchanged before/after scrolling.
6. **`1fr` collapses to 0 under overflow.** `remaining_space = max(0, size.height - auto_children - margins)`
   (`_resolve.py:309-335`). Never rely on a `1fr` box to stay visible when its `auto` siblings overflow.
7. **`1fr` inside a scroll container pins the virtual size.** A `1fr` child resolves against the scroll
   viewport, so the container never overflows and never scrolls — use `height: auto` for scrollable content.
8. **Pilot timing.** After `pilot.resize_terminal(...)` (`pilot.py:86-98`) or after `mount(...)`, call
   `await pilot.pause()` before asserting geometry; `scroll_end(animate=False)` defers to
   `call_after_refresh` (`widget.py:3075-3078`), so `await pilot.pause()` after it as well.
9. **Do not use the animated scroll in a test.** `scroll_end()` defaults to `animate=True` with a 1-second
   duration (`widget.py:3012-3044`) → use `animate=False` (or `immediate=True`).
10. **Auto-focus is first-focusable-wins.** `App.AUTO_FOCUS = "*"` (`app.py:396`) +
    `Screen._update_auto_focus` (`screen.py:1489-1500`) focus the **first** focusable widget in DOM order. A
    focusable `VerticalScroll` placed before the `Input` would steal the auto-focus (the user would have to Tab
    before typing). Use `can_focus=False` or `AUTO_FOCUS = f"#{APP_ID_INPUT_ID}"`.
11. **Tab order changes with a focusable container.** `Screen.focus_chain` puts a container before its children
    (`screen.py:772-826`), so `tab` from the Input may land on the container. Assert
    `run_button in tui.screen.focus_chain` if the container stays focusable.
12. **The `Input` consumes only printable keys** (`_input.py:498-510`), so `tab`/`up`/`down` reach the Screen
    and the ancestors' bindings; `home`/`end` stay with the Input (`_input.py:75-142`).
13. **`Static` content typing.** `Static.content` returns the original object: a `rich.text.Text` has
    `.plain`/`.style`, a plain `str` does **not**. The brand Statics use plain `str` — assert with
    `str(widget.content).strip()` (as the TUIX-001 tests do). `Static` renders console markup by default, so
    avoid `[` in mounted text.
14. **Rich renderables inside a scroll container.** The report's `Table` is mounted as a `Static`; inside a
    scroll region its width is bounded by the body (`overflow-x: hidden`) — the same clipping as today, no
    regression, but do not assert on the table's pixel width.
15. **Ruff:** line-length 100, `target-version = "py311"`, lint `E,F,W,I,UP,B,SIM,RUF`, format
    `quote-style = "double"` (`pyproject.toml`). Tests are linted too. Keep the new tests ≤ 100 columns.
16. **Mypy:** `[tool.mypy] files = ["src"]`; `src/keniran/tui/app.py` is checked in moderate mode (strict only
    for `keniran.core.*`). `tests/` is not type-checked. Annotate any new helper functions anyway and keep
    `from __future__ import annotations` at the top of both files.
17. **`ruff format .` may touch the ALT-001 sibling files.** If it reformats
    `src/keniran/core/requirements_parser.py` or `tests/test_requirements_parser.py`, **leave the reformat in
    place** (do not revert) and report it. If you prefer to guarantee the diff stays inside the two allowed
    files, run `python -m ruff format src tests` instead of `ruff format .` — but then re-run
    `python -m ruff check .` so the untouched files are still linted. The acceptance command is the literal
    `python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q`.
18. **Commit convention** (`.spec/conventions.md:26-28`): one task = one commit, message
    `TUIX-002: Keep the home and results usable at short terminal heights`, with the task's tests in the same
    commit.

## Reference patterns to imitate

- `src/keniran/tui/app.py:41-53` — module-level id constants (`Final` + UPPER_CASE); add a new
  `BODY_ID: Final = "body"` here so the test imports it instead of hard-coding the string.
- `src/keniran/tui/app.py:63-117` — the `CSS` block shape (id selectors, 4-space indent inside the triple-quoted
  string).
- `src/keniran/tui/app.py:140-157` — the `compose()` shape (`yield` + `with ...` context managers).
- `src/keniran/tui/app.py:235, 242, 249, 256` — `self.query_one(f"#{RESULTS_ID}", Container)` — the reason
  `#results` must stay a `Container`.
- `tests/test_tui.py:64-107` — the pilot helpers (`_run`, `_wait_until`, `_wait_for_check`, `_error_texts`,
  `_click_run`).
- `tests/test_tui.py:143-150` — `_offline_tui(...)` for the offline fakes.
- `tests/test_tui.py:156-185` — the `full_report` fixture.
- `tests/test_tui.py:191-206` — the shell pilot test (`run_test()` + `query_one` idioms).
- `tests/test_tui.py:209-230` — the brand-block test (region-order assertion idiom to copy).
- `tests/test_tui.py:233-255` — the command-box test (`styles.border_top`, `styles.background.hex`, `region.width`).
- `tests/test_tui.py:429-472` — the fake-`check_game` monkeypatch idiom for producing a real report.
- `.venv/Lib/site-packages/textual/containers.py:19-28, 32-59, 121-131, 147-156` — the container DEFAULT_CSS
  and the scroll BINDINGS.
- `.venv/Lib/site-packages/textual/app.py:2133-2141` — `run_test(size=...)`.
- `.venv/Lib/site-packages/textual/widget.py:1989-2000, 2285-2294, 2384-2391, 2859-2918, 3012-3078` — the
  scroll/region API.

## Contracts & types touched

- `KeniranTui.compose()` in `src/keniran/tui/app.py:140` — signature unchanged (`-> ComposeResult`). The
  yielded tree may gain **one** wrapper container around `#home` + `#results` (recommended design); every
  existing id, class, order-inside-`#home`, and the top-level `Header()`/`Footer()` are preserved.
- `KeniranTui.CSS` in `src/keniran/tui/app.py:63` — still a plain `str` class attribute; only the
  `#home`/`#results` rules (and one new rule) change. It must parse under Textual 8.2.8.
- `APP_ID_INPUT_ID`, `RUN_BUTTON_ID`, `STATUS_ID`, `RESULTS_ID`, `ERROR_ID`, `ERROR_STYLE`, `TITLE_ID`,
  `WORDMARK_ID`, `TAGLINE_ID`, `COMMAND_BOX_ID`, `TAGLINE` — **values unchanged**; imported by
  `tests/test_tui.py:46-59`.
- `Input.restrict` — still `r"[0-9]*"` (pinned at `tests/test_tui.py:201`).
- `Button("Run", id=RUN_BUTTON_ID, variant="primary")` — unchanged.
- `KeniranTui.theme` / `TITLE` / `SUB_TITLE` (`app.py:59-61`) — unchanged (`theme == "tokyo-night"` is pinned
  by `tests/test_tui.py:196-197`).
- `run_tui()` in `src/keniran/tui/app.py:263` — unchanged (monkeypatched at `tests/test_tui.py:681`).
- `#results` widget class — **must remain `textual.containers.Container`** (see §4.1).
- New (optional): `BODY_ID: Final = "body"` module constant for the scroll region.
- New (optional): `KeniranTui.AUTO_FOCUS` override — only if the scroll region stays focusable.

## Required reading

- `src/keniran/tui/app.py` (whole file — 265 lines; especially 41-53, 56-117, 140-157, 159-260).
- `tests/test_tui.py` (whole file — 727 lines; especially 46-107, 191-289, 373-472, 509-654).
- `.spec/units/v1.0.1/tui-redesign/spec.md` (the binding "Changed Contracts": vertical scrolling at short
  heights, keyboard accessibility, no report redesign).
- `.spec/units/v1.0.1/tui-redesign/active-context.md` (TUIX-001 is done; TUIX-002 owns short-height scrolling).
- `.spec/units/v1.0.1/tui-redesign/tasks.md` (the TUIX-001/TUIX-002 split).
- `.spec/conventions.md` (acceptance commands, code style, commit convention).
- `.spec/units/v1.0.1/tui-redesign/briefs/TUIX-001.md` (the TUIX-001 map of the same two files — reuse its
  facts; its line numbers for `app.py` are pre-TUIX-001 and were re-verified above).
- Textual 8.2.8 sources (read-only, `.venv/Lib/site-packages/textual/`):
  `app.py:2133-2141` (`run_test`), `app.py:396` (`AUTO_FOCUS`), `app.py:1654-1669` (`App.size`),
  `pilot.py:76-98, 192, 535`, `containers.py:19-28, 32-118, 121-131, 147-156`,
  `widget.py:2080-2137, 2156-2187, 2226-2254, 2285-2294, 2384-2391, 2859-2918, 3012-3078, 1989-2000, 357, 378`,
  `screen.py:174-178, 270-271, 408-446, 772-826, 1489-1500`, `_input.py:75-142, 498-510`,
  `_resolve.py:309-335`, `_compositor.py:480-493, 670-676`, `css/styles.py:384-390`, `geometry.py:489, 494`.

## Acceptance

```
python -m pytest tests/test_tui.py -q
python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
```

### Acceptance checklist → concrete pilot assertion

| # | Acceptance criterion | Concrete pilot assertion | Test (§3) |
|---|---|---|---|
| 1 | Pilot coverage at 100x30 | `async with tui.run_test(size=(100, 30))` and `assert tui.size.width == 100 and tui.size.height == 30` | 3.1 |
| 2 | Pilot coverage at a compact 80x16 | `async with tui.run_test(size=(80, 16))` (or `pilot.resize_terminal(80, 16)` + `await pilot.pause()`) | 3.2-3.6 |
| 3 | No horizontal clipping of the App ID/Run controls | for the Input and the Button: `region.width > 0`, `region.x >= 0`, `region.right <= tui.size.width` at **both** 100x30 and 80x16 | 3.2 |
| 4 | The controls remain keyboard-reachable | `app_id_input.focus()` → `assert tui.focused is app_id_input`; `await pilot.press("7","2","8")` → `assert app_id_input.value == "728"`; `await pilot.press("tab")` → `assert tui.focused is run_button` (or `assert run_button in tui.screen.focus_chain` if the scroll region is focusable) | 3.3 |
| 5 | Long results are vertically scrollable to the end, not clipped | `assert body.max_scroll_y > 0`; `assert body.show_vertical_scrollbar`; before scrolling `assert last.region.bottom > body.region.bottom`; after `body.scroll_end(animate=False)` + `await pilot.pause()`: `assert body.scroll_offset.y == body.max_scroll_y`, `assert body.is_vertical_scroll_end`, `assert last.region.y >= body.region.y`, `assert last.region.bottom <= body.region.bottom` | 3.4 |
| 6 | Long **home** content is reachable too | mount tall `Static`s into `#home` (or `pilot.resize_terminal(80, 10)`), then `assert body.max_scroll_y > 0` and after `scroll_end` `assert body.is_vertical_scroll_end` and the last home child's region is inside `body.region` | 3.5 |
| 7 | At the normal size, title, tagline, command box and initial result region fit in the expected hierarchy | `title.region.y < wordmark.region.y < tagline.region.y < box.region.y`; `results.region.y >= box.region.y`; `results.region.height > 0`; `len(results.children) == 0`; `box.region.bottom <= tui.size.height` | 3.1 (and 3.7 for the default 80x24) |
| 8 | Header/Footer stay usable | `isinstance(tui.query_one(Header), Header)`; `header.region.height > 0`; `footer.region.height > 0`; `header.region.y` and `footer.region.bottom` unchanged after the body scrolls (docked ⇒ do not scroll) | 3.6 |
| 9 | Existing worker / error-recovery / shared-renderable pilot tests not regressed | unchanged tests at `tests/test_tui.py:373-654` keep passing; `#results` is still a `Container` so `query_one(f"#{RESULTS_ID}", Container)` keeps working | full file |
| 10 | Shared report renderables unchanged | `tests/test_tui.py:429-472` still asserts the exact `report_renderables` sequence — do **not** touch `keniran.rendering.report_view` | full file |
| 11 | TUIX-001 brand/command-box assertions not regressed | `tests/test_tui.py:209-289` unchanged and passing (ids, classes, border/background colours, region order, `$primary`/`$accent` values) | full file |
| 12 | Full gate green | `python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q` | Acceptance |
| 13 | Out-of-scope respected | diff limited to `src/keniran/tui/app.py` + `tests/test_tui.py` (plus possible `ruff format` reflow of the ALT-001 files, left in place and reported); no new command/control, no report-rendering change, no theme persistence, no new dependency | — |

## Open uncertainties

- **Which design the reviewer expects.** §4.2 (explicit `VerticalScroll` body) vs §4.3 (`overflow-y: auto` on
  `#results` + the Screen's implicit scroll). Both satisfy the wording; §4.2 is recommended because it is
  explicit, keyboard-scrollable and assertable. If the reviewer expects the *lighter* diff, §4.3 is a one-line
  CSS change — but it leaves the results region without keyboard scroll bindings and still relies on the
  Screen's default `overflow-y: auto` for the home.
- **"Initial result region" wording.** It may mean "the results region exists and sits below the command box"
  (structural) or "the results area has a visible, non-zero height at the normal size" (pixel). The
  recommended design keeps `min-height: 3` on `#results` so both readings hold; if the structural reading is
  the intended one, `min-height` may be dropped.
- **The exact new id for the scroll region.** `#home` is not referenced by any test (only the TUIX-001 *test
  name* mentions "home"), so the wrapper may be named freely; export it as a `Final` constant
  (`BODY_ID = "body"`) and import it in the test rather than hard-coding the string.
- **Whether `#home` should keep the id `home`.** No test queries it, but keeping it costs nothing and keeps the
  TUIX-001 mental model.
- **Whether the body's scrollbar should be visible.** `overflow-y: auto` shows it only when needed
  (`widget.py:2097-2103`); `overflow-y: scroll` would always show it and permanently cost one column at
  80 columns. `auto` is recommended.
- **The exact height of the home block** (~10 rows) is an estimate from the CSS; the implementer should
  measure `tui.query_one("#home").region.height` in the pilot rather than trusting this number.
- **Whether the acceptance wants a *keyboard* scroll of the results** ("vertically scrollable to its end").
  §4.2 gives real key bindings for it; §4.3 does not. If keyboard scrolling is required, §4.2 is the only one
  of the two that delivers it.
