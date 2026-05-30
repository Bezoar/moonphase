# Cell-times Peak Labels + Transition Arrows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the giant `--cell-times` heatmap, label each phase peak (bare, e.g. `Full 21:23`) in addition to the transition into that phase (arrow-prefixed, e.g. `→Full 14:25`), and allow `--cell-times` without `--transitions` (peaks only).

**Architecture:** A new pure layout helper `cell_events_by_day` merges both `center` and `transition` events per day into time-sorted `(is_transition, idx, local)` tuples. The heatmap renderer formats each tuple through a single `_cell_line` helper (`→`-prefixed for transitions, bare for peaks; `@` separator dropped). The CLI drops the `--transitions` requirement so peak-only mode falls out naturally — `build_events` always emits centers and only adds transitions under `--transitions`.

**Tech Stack:** Python 3.10+, matplotlib (lazy-imported in renderer), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-05-30-transition-peak-label-design.md`

---

## File Structure

- `src/moonphase/heatmap_layout.py` — add `cell_events_by_day` (Task 1); remove `transitions_by_day` (Task 2).
- `src/moonphase/renderers/heatmap.py` — `_cell_line` formatter, rewire `_draw_cell_times` + `_giant_figsize` + the render call to the new helper and format (Task 2).
- `src/moonphase/cli.py` — drop the `--transitions` requirement + update `--cell-times` help (Task 3).
- `samples/README.md` + `samples/heatmap-cell-times-2026-16div.png` — doc blurb + regenerated sample (Task 4).
- Tests: `tests/test_heatmap_layout.py`, `tests/test_renderers.py`, `tests/test_cli.py`.

---

### Task 1: `cell_events_by_day` layout helper

Adds the merged-events helper alongside the existing `transitions_by_day` (which Task 2 removes), so the suite stays green at this commit.

**Files:**
- Modify: `src/moonphase/heatmap_layout.py` (add function after `transitions_by_day`, ~line 85)
- Test: `tests/test_heatmap_layout.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_heatmap_layout.py`. First extend the import on line 6:

```python
from moonphase.heatmap_layout import (
    day_cells, principal_phase_days, lunations, transitions_by_day, cell_events_by_day,
)
```

Then append these tests:

```python
def test_cell_events_by_day_merges_centers_and_transitions_sorted():
    evs = [
        PhaseEvent(when=datetime(2026, 1, 1, 18, tzinfo=timezone.utc),
                   angle_deg=22.5, kind="transition", index=0, name=None),
        PhaseEvent(when=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
                   angle_deg=0.0, kind="center", index=0, name="New"),
        PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                   angle_deg=45.0, kind="center", index=1, name=None),
    ]
    m = cell_events_by_day(evs, UTC, 8)
    assert list(m) == ["2026-01-01", "2026-01-02"]
    # time-sorted within the day: center (06:00) before transition (18:00).
    # center index is the phase itself (no +1); transition entered = index+1.
    assert [(is_t, idx, t.hour) for is_t, idx, t in m["2026-01-01"]] == [
        (False, 0, 6), (True, 1, 18)]
    assert [(is_t, idx) for is_t, idx, _ in m["2026-01-02"]] == [(False, 1)]


def test_cell_events_by_day_centers_only_when_no_transitions():
    evs = [PhaseEvent(when=datetime(2026, 1, 3, 9, tzinfo=timezone.utc),
                      angle_deg=180.0, kind="center", index=4, name="Full")]
    m = cell_events_by_day(evs, UTC, 8)
    assert [(is_t, idx) for is_t, idx, _ in m["2026-01-03"]] == [(False, 4)]


def test_cell_events_by_day_uses_display_tz_day():
    z = DisplayZone("fixed", timedelta(hours=-8))
    # 2026-01-02 03:00 UTC == 2026-01-01 19:00 local -> previous local day
    evs = [PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                      angle_deg=11.25, kind="transition", index=0, name=None)]
    m = cell_events_by_day(evs, z, 8)
    assert list(m) == ["2026-01-01"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_heatmap_layout.py -k cell_events -v`
Expected: FAIL with `ImportError: cannot import name 'cell_events_by_day'`

- [ ] **Step 3: Implement `cell_events_by_day`**

Add to `src/moonphase/heatmap_layout.py` immediately after `transitions_by_day` (after line 84):

```python
def cell_events_by_day(events, tz, divisions):
    """Map ``date_iso -> time-sorted [(is_transition, idx, local), ...]`` over both
    phase-center and transition events.

    A ``center`` event's ``index`` is the phase at its peak (``is_transition`` False,
    rendered bare). A ``transition`` event's ``index`` is the microphase being *left*,
    so the entered phase is ``(index + 1) % divisions`` (``is_transition`` True,
    rendered with a leading arrow by the renderer). ``events`` may be ``None``."""
    out: dict[str, list[tuple[bool, int, object]]] = {}
    for e in events or []:
        if e.kind == "transition":
            is_transition, idx = True, (e.index + 1) % divisions
        elif e.kind == "center":
            is_transition, idx = False, e.index
        else:
            continue
        local = tz.to_display(e.when)
        day = local.date().isoformat()
        out.setdefault(day, []).append((is_transition, idx, local))
    for day in out:
        out[day].sort(key=lambda t: t[2])
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_heatmap_layout.py -v`
Expected: PASS (new `cell_events` tests + existing `transitions_by_day` tests)

- [ ] **Step 5: Lint**

Run: `ruff check src tests`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/heatmap_layout.py tests/test_heatmap_layout.py
git commit -m "feat(heatmap): cell_events_by_day merges peaks and transitions"
```

---

### Task 2: Renderer — `_cell_line` formatter, arrow/bare lines, drop `@`

Rewires the cell-times path to `cell_events_by_day` and the new line format, then removes the now-unused `transitions_by_day`.

**Files:**
- Modify: `src/moonphase/renderers/heatmap.py` (import line 9; `_giant_figsize` 91-112; `_draw_cell_times` 164-177; render call 231-232, 266-268; comment 260-262; add `_cell_line`)
- Modify: `src/moonphase/heatmap_layout.py` (remove `transitions_by_day`)
- Test: `tests/test_renderers.py`, `tests/test_heatmap_layout.py`

- [ ] **Step 1: Write the failing format test**

Add to `tests/test_renderers.py` (anywhere among the heatmap tests):

```python
def test_cell_line_format():
    from moonphase.renderers.heatmap import _cell_line
    assert _cell_line(True, "Full", "14:25") == "→Full 14:25"
    assert _cell_line(False, "Full", "21:23") == "Full 21:23"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_renderers.py::test_cell_line_format -v`
Expected: FAIL with `ImportError: cannot import name '_cell_line'`

- [ ] **Step 3: Add the `_cell_line` helper**

In `src/moonphase/renderers/heatmap.py`, add this helper just above `_draw_cell_times` (before line 164):

```python
def _cell_line(is_transition, label, hhmm):
    """One cell-times line: '→label HH:MM' for a transition *into* a phase,
    or bare 'label HH:MM' for a phase peak (center)."""
    return f"{'→' if is_transition else ''}{label} {hhmm}"
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_renderers.py::test_cell_line_format -v`
Expected: PASS

- [ ] **Step 5: Rewire `_draw_cell_times` to the new tuples and formatter**

Replace `_draw_cell_times` (lines 164-177) with:

```python
def _draw_cell_times(ax, x0, row, crossings, cell, scheme, tint, label_of):
    """Draw a day's phase-peak and transition times inside its cell as low-contrast
    text — transitions arrow-prefixed (entering a phase), peaks bare — collapsing to
    an 'N×' badge past the stack cap."""
    a, i = cell
    color = damped_text_color(_tint(a, i, scheme, tint))
    cx, cy = x0 + 0.47, row + 0.47
    if len(crossings) > _STACK_CAP:
        ax.text(cx, cy, f"{len(crossings)}×", ha="center", va="center",
                fontsize=9, color=color, zorder=8)
        return
    text = "\n".join(_cell_line(is_t, label_of(idx), local.strftime("%H:%M"))
                     for is_t, idx, local in crossings)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9, color=color,
            zorder=8)
```

- [ ] **Step 6: Rewire `_giant_figsize` to the new tuples and formatter**

Replace the line-building block at the top of `_giant_figsize` (lines 94-101) with:

```python
    lines, max_rows = [], 1
    for crossings in day_trans.values():
        max_rows = max(max_rows, min(len(crossings), _STACK_CAP))
        for is_t, idx, local in crossings:
            lines.append(_cell_line(is_t, label_of(idx), local.strftime("%H:%M")))
    # char-count proxy for pixel width; the arrow-prefixed transition lines are the
    # widest case. The true extent of this pick is measured by _measure_line_inches.
    longest = max(lines, key=len) if lines else "→0 00:00"
```

(The docstring on line 92-93 mentioning `'label @ HH:MM'` should read `'label HH:MM'` — update it.)

- [ ] **Step 7: Swap the import and render call to `cell_events_by_day`**

In `src/moonphase/renderers/heatmap.py` line 9, change the import:

```python
from ..heatmap_layout import day_cells, lunations, principal_phase_days, cell_events_by_day
```

At lines 231-232 replace `transitions_by_day` with `cell_events_by_day` (keep the `day_trans` variable name so downstream references at 234, 266-267 are unchanged):

```python
    day_trans = (cell_events_by_day(report.events, report.tz, scheme.divisions)
                 if cell_times else {})
```

Update the comment at lines 260-262 to drop the stale `@`:

```python
                    # In cell-times mode the principal phases show as plain
                    # "label HH:MM" text like any other phase, so the
                    # moon-disk markers are suppressed.
```

- [ ] **Step 8: Remove the now-unused `transitions_by_day`**

Delete the entire `transitions_by_day` function (lines 69-84) from `src/moonphase/heatmap_layout.py`. Then in `tests/test_heatmap_layout.py` remove `transitions_by_day` from the import on line 6 and delete the two tests `test_transitions_by_day_skips_centers_sorts_and_enters_next_index` and `test_transitions_by_day_uses_display_tz_day`.

- [ ] **Step 9: Add a peak-only renderer smoke test**

Add to `tests/test_renderers.py`, just after `_giant_transitions` (line 269):

```python
def _giant_centers():
    from datetime import timedelta
    return [
        PhaseEvent(when=T0 + timedelta(days=3, hours=5), angle_deg=0.0,
                   kind="center", index=0, name="New"),
        PhaseEvent(when=T0 + timedelta(days=10, hours=12), angle_deg=90.0,
                   kind="center", index=2, name="1Q"),
    ]


def test_heatmap_cell_times_peaks_only_writes_png(tmp_path):
    r = _heatmap_report(
        options={"tint": "index", "calendar": "gregorian", "cell_times": True},
        events=_giant_centers())
    out = tmp_path / "peaks.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 10: Run the full renderer + layout suites**

Run: `pytest tests/test_renderers.py tests/test_heatmap_layout.py -v`
Expected: PASS, including `test_cell_line_format`, `test_heatmap_cell_times_writes_png`, `test_heatmap_cell_times_peaks_only_writes_png`. No remaining reference to `transitions_by_day`.

- [ ] **Step 11: Lint**

Run: `ruff check src tests`
Expected: no errors

- [ ] **Step 12: Commit**

```bash
git add src/moonphase/renderers/heatmap.py src/moonphase/heatmap_layout.py tests/test_renderers.py tests/test_heatmap_layout.py
git commit -m "feat(heatmap): peak labels + transition arrows in cell-times text"
```

---

### Task 3: CLI — allow `--cell-times` without `--transitions`

**Files:**
- Modify: `src/moonphase/cli.py` (validation 148-149; `--cell-times` help 124-126)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Rewrite the requires-transitions test as peak-only success**

In `tests/test_cli.py`, replace `test_cell_times_requires_transitions` (lines 215-223) with:

```python
def test_cell_times_without_transitions_renders_peaks(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "h.png"
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-31", "--divisions", "8",
        "--format", "heatmap", "--cell-times", "--out", str(out),
    ])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_cli.py::test_cell_times_without_transitions_renders_peaks -v`
Expected: FAIL — `rc == 2` (current validation still rejects missing `--transitions`)

- [ ] **Step 3: Drop the `--transitions` requirement**

In `src/moonphase/cli.py`, delete the `elif` branch at lines 148-149 so the block reads:

```python
    if args.cell_times:
        problem = None
        if args.format != "heatmap":
            problem = "--cell-times applies only to --format heatmap"
        elif args.calendar != "gregorian":
            problem = "--cell-times requires --calendar gregorian"
        if problem:
            print(f"error: {problem}", file=sys.stderr)
            return 2
```

- [ ] **Step 4: Update the `--cell-times` help text**

Replace the `--cell-times` argument (lines 124-126) with:

```python
    p.add_argument("--cell-times", action="store_true",
                   help="print phase-peak times inside heatmap day cells; with "
                        "--transitions, also the transition-into-phase times "
                        "(--calendar gregorian only)")
```

- [ ] **Step 5: Run the CLI cell-times tests**

Run: `pytest tests/test_cli.py -k cell_times -v`
Expected: PASS — `test_cell_times_without_transitions_renders_peaks`, `test_cell_times_rejects_lunar`, `test_cell_times_rejects_non_heatmap_format`

- [ ] **Step 6: Full suite + lint**

Run: `pytest -q && ruff check src tests`
Expected: all pass, no lint errors

- [ ] **Step 7: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat(cli): --cell-times no longer requires --transitions (peaks only)"
```

---

### Task 4: Regenerate sample + update samples/README

Requires the DE421 kernel (~17 MB; downloads to `./data/` on first real ephemeris use — network needed). Run from the repo root in the project venv.

**Files:**
- Modify: `samples/README.md` (lines 91-109 blurb)
- Replace: `samples/heatmap-cell-times-2026-16div.png`

- [ ] **Step 1: Regenerate the sample PNG**

Run:

```bash
moonphase --start 2026-01-01T00:00Z --end 2026-12-31T23:00Z --divisions 16 \
          --transitions --format heatmap --calendar gregorian --tint index --cell-times \
          --labels @samples/labels-16-compact.txt \
          --out samples/heatmap-cell-times-2026-16div.png
```

Expected: the file is rewritten; open it and confirm cells show bare peaks (`Full 21:23`) and arrow-prefixed transitions (`→Full 14:25`), no `@`.

- [ ] **Step 2: Update the README blurb**

In `samples/README.md`, replace the descriptive paragraph under `### Giant heatmap with in-cell transition times — \`--cell-times\`` (lines 92-100) with:

```markdown
With `--cell-times` (gregorian), each day cell prints two kinds of moment in
low-contrast text: a **phase peak** as a bare `label HH:MM` (e.g. `Full 21:23`),
and — when `--transitions` is also given — the **transition into** a phase as
`→label HH:MM` (e.g. `→Full 14:25`). `label` is the `--labels` value (here the
compact codes from [`labels-16-compact.txt`](labels-16-compact.txt)) or the bare
microphase number. Without `--transitions` the cells show peaks only. The
principal phases (New, 1Q, Full, 3Q) appear as plain text like any other phase —
no moon-disk markers. The figure is auto-sized from the labels so 9 pt text stays
legible, which makes it large — **tap the image to open it full-size in a new
tab**.
```

- [ ] **Step 3: Commit**

```bash
git add samples/README.md samples/heatmap-cell-times-2026-16div.png
git commit -m "docs(samples): regenerate cell-times sample with peak + transition labels"
```

---

## Self-Review

- **Spec coverage:** arrow/bare format (Task 2 `_cell_line` + test), `@` dropped (Task 2), `cell_events_by_day` merging both kinds with center-index vs entered-index (Task 1 + tests), peak-only via dropped `--transitions` requirement (Task 3 + test), sample + README (Task 4). All spec sections covered.
- **Type consistency:** `cell_events_by_day` returns `(is_transition, idx, local)` everywhere; `_draw_cell_times` and `_giant_figsize` both unpack the same 3-tuple and call `_cell_line(is_t, label_of(idx), local.strftime("%H:%M"))`; the render call keeps the `day_trans` variable name to avoid touching lines 234/266-267.
- **Green at every commit:** Task 1 keeps `transitions_by_day` alive; Task 2 removes it only after rewiring the renderer and its tests in the same commit.
- **No placeholders:** every code/edit step shows full content and exact line targets.
