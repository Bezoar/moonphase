# Giant heatmap with in-cell transition times — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--cell-times` mode to the `heatmap` renderer that prints each day's microphase-transition times *inside* the gregorian day cells, sized large enough ("giant") to stay legible, plus a general `--size` pixel override and a `--font` family/file override.

**Architecture:** The data already exists — in series mode the `Report` carries `report.events` built with `transitions=args.transitions`. A new pure helper maps transition events to display-tz days; the gregorian heatmap draws them with a luminance-damped low-contrast text color; the figure is sized from the actual labels at a 9 pt floor so text always fits (a too-small explicit `--size` is the one error path). Lunar layout, centres, and other renderers are untouched.

**Tech Stack:** Python 3.10, argparse, matplotlib (Agg), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-29-giant-heatmap-cell-times-design.md`

---

## File structure

- **Create** `src/moonphase/renderers/celltext.py` — luminance-damped text-color helper (pure, no matplotlib).
- **Modify** `src/moonphase/heatmap_layout.py` — add pure `transitions_by_day(events, tz, divisions)`.
- **Modify** `src/moonphase/renderers/heatmap.py` — content-driven sizing, `--size`/`--font` handling, in-cell text drawing in `_render_gregorian`.
- **Modify** `src/moonphase/cli.py` — `_parse_size`, the three new args, `--cell-times` validation, options wiring.
- **Modify** `tests/test_heatmap_layout.py` — tests for `transitions_by_day`.
- **Create** `tests/test_celltext.py` — tests for `damped_text_color`.
- **Modify** `tests/test_cli.py` — `_parse_size` + `--cell-times` validation tests.
- **Modify** `tests/test_renderers.py` — giant render / too-small-size / size-override smoke tests.
- **Modify** `README.md` and `docs/specs/primary.md` — document the three flags.
- **Create** `samples/labels-8-short.txt` and **Modify** `samples/README.md` — a giant sample with a tap-to-open full-size image.

---

## Task 1: Pure helper — `transitions_by_day`

**Files:**
- Modify: `src/moonphase/heatmap_layout.py`
- Test: `tests/test_heatmap_layout.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_heatmap_layout.py` (extend the existing import line to include `transitions_by_day`, and add `from datetime import datetime, timezone` is already present; add `from moonphase.events import PhaseEvent`):

```python
from moonphase.events import PhaseEvent
from moonphase.heatmap_layout import transitions_by_day


def test_transitions_by_day_skips_centers_sorts_and_enters_next_index():
    evs = [
        PhaseEvent(when=datetime(2026, 1, 1, 18, tzinfo=timezone.utc),
                   angle_deg=22.5, kind="transition", index=0, name=None),
        PhaseEvent(when=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
                   angle_deg=11.25, kind="transition", index=7, name=None),
        PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                   angle_deg=0.0, kind="center", index=0, name="New"),
    ]
    m = transitions_by_day(evs, UTC, 8)
    assert list(m) == ["2026-01-01"]                       # center is skipped
    assert [t.hour for _, t in m["2026-01-01"]] == [6, 18]  # time-sorted
    # entered index = (event.index + 1) % divisions, in time order
    assert [idx for idx, _ in m["2026-01-01"]] == [0, 1]


def test_transitions_by_day_uses_display_tz_day():
    z = DisplayZone("fixed", timedelta(hours=-8))
    # 2026-01-02 03:00 UTC == 2026-01-01 19:00 local -> previous local day
    evs = [PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                      angle_deg=11.25, kind="transition", index=0, name=None)]
    m = transitions_by_day(evs, z, 8)
    assert list(m) == ["2026-01-01"]
```

(Note: `DisplayZone` and `timedelta` are already imported at the top of this test file via the existing imports; if not, add `from datetime import timedelta`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_heatmap_layout.py -k transitions_by_day -v`
Expected: FAIL — `ImportError: cannot import name 'transitions_by_day'`.

- [ ] **Step 3: Implement the helper**

Append to `src/moonphase/heatmap_layout.py`:

```python
def transitions_by_day(events, tz, divisions):
    """Map ``date_iso -> time-sorted [(entered_index, local_datetime), ...]`` for
    each ``kind == "transition"`` event. A transition event's ``index`` is the
    microphase being *left*; the phase that takes effect is the one *entered*,
    ``(index + 1) % divisions``. ``events`` may be ``None``."""
    out: dict[str, list[tuple[int, object]]] = {}
    for e in events or []:
        if e.kind != "transition":
            continue
        local = tz.to_display(e.when)
        day = local.date().isoformat()
        entered = (e.index + 1) % divisions
        out.setdefault(day, []).append((entered, local))
    for day in out:
        out[day].sort(key=lambda pair: pair[1])
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_heatmap_layout.py -k transitions_by_day -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/heatmap_layout.py tests/test_heatmap_layout.py
git commit -m "feat: transitions_by_day layout helper (entered-index, tz-day map)"
```

---

## Task 2: Pure helper — `damped_text_color`

**Files:**
- Create: `src/moonphase/renderers/celltext.py`
- Test: `tests/test_celltext.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_celltext.py`:

```python
from moonphase.renderers.celltext import damped_text_color


def test_bright_cell_gets_darker_text_but_not_pure_black():
    c = damped_text_color((0.9, 0.9, 0.9), contrast=0.55)
    assert all(0.0 < ch < 0.9 for ch in c)       # darker than cell, not black


def test_dark_cell_gets_lighter_text_but_not_pure_white():
    c = damped_text_color((0.1, 0.1, 0.1), contrast=0.55)
    assert all(0.1 < ch < 1.0 for ch in c)       # lighter than cell, not white


def test_contrast_zero_returns_cell_and_one_returns_target():
    cell = (0.2, 0.4, 0.6)
    assert damped_text_color(cell, contrast=0.0) == cell      # invisible end
    # luminance(cell) < 0.5 -> target white
    assert damped_text_color(cell, contrast=1.0) == (1.0, 1.0, 1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_celltext.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonphase.renderers.celltext'`.

- [ ] **Step 3: Implement the helper**

Create `src/moonphase/renderers/celltext.py`:

```python
"""Helpers for drawing low-contrast text inside heatmap cells."""

from __future__ import annotations


def _luminance(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def damped_text_color(cell_rgb, contrast: float = 0.55):
    """Return an RGB tuple for text drawn on ``cell_rgb`` that stays in a
    low-to-medium contrast band: pick black-or-white from the cell's luminance,
    then blend that target toward the cell color by ``contrast`` (0.0 = the cell
    color itself / invisible, 1.0 = full black/white)."""
    target = 0.0 if _luminance(cell_rgb) > 0.5 else 1.0
    return tuple(c + (target - c) * contrast for c in cell_rgb[:3])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_celltext.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/celltext.py tests/test_celltext.py
git commit -m "feat: damped_text_color for low-contrast in-cell text"
```

---

## Task 3: CLI `_parse_size`

**Files:**
- Modify: `src/moonphase/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_parse_size_ok():
    assert cli_mod._parse_size("5000x3000") == (5000, 3000)
    assert cli_mod._parse_size(" 800X600 ") == (800, 600)


def test_parse_size_bad():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        cli_mod._parse_size("wide")
    with pytest.raises(argparse.ArgumentTypeError):
        cli_mod._parse_size("0x100")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k parse_size -v`
Expected: FAIL — `AttributeError: module 'moonphase.cli' has no attribute '_parse_size'`.

- [ ] **Step 3: Implement `_parse_size`**

In `src/moonphase/cli.py`, add after `_parse_sample` (around line 79):

```python
_SIZE_RE = re.compile(r"^\s*([0-9]+)\s*[xX]\s*([0-9]+)\s*$")


def _parse_size(s: str) -> tuple[int, int]:
    """Parse pixel dimensions ``WIDTHxHEIGHT``, e.g. '5000x3000'."""
    m = _SIZE_RE.match(s)
    if not m:
        raise argparse.ArgumentTypeError(
            f"bad --size {s!r}; expected e.g. '5000x3000' (WIDTHxHEIGHT)")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("--size dimensions must be positive")
    return (w, h)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -k parse_size -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat: --size WIDTHxHEIGHT parser"
```

---

## Task 4: CLI flags + `--cell-times` validation + options wiring

**Files:**
- Modify: `src/moonphase/cli.py:97-138` (args block and `main` options/validation)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (the `_LinearEph` fake and `cli_mod` import already exist):

```python
def test_cell_times_requires_transitions(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-31", "--divisions", "8",
        "--format", "heatmap", "--cell-times", "--out", str(tmp_path / "h.png"),
    ])
    assert rc == 2


def test_cell_times_rejects_lunar(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-31", "--divisions", "8",
        "--transitions", "--format", "heatmap", "--calendar", "lunar",
        "--cell-times", "--out", str(tmp_path / "h.png"),
    ])
    assert rc == 2


def test_cell_times_rejects_non_heatmap_format(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-31", "--divisions", "8",
        "--transitions", "--format", "chart", "--cell-times",
        "--out", str(tmp_path / "c.png"),
    ])
    assert rc == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k cell_times -v`
Expected: FAIL — argparse exits with code 2 only because `--cell-times` is *unrecognized* (SystemExit), not our validation. After implementation these must pass via the validation path returning `2`. (If the run shows `SystemExit`, that still surfaces as a failure/erroring test until Step 3 adds the argument.)

- [ ] **Step 3: Add the flags and validation**

In `build_parser()`, after the `--lunar-anchor` argument (around line 106), add:

```python
    p.add_argument("--size", type=_parse_size, default=None,
                   help="output image size in pixels, WIDTHxHEIGHT (e.g. 5000x3000)")
    p.add_argument("--cell-times", action="store_true",
                   help="print transition times inside heatmap day cells "
                        "(requires --transitions; --calendar gregorian only)")
    p.add_argument("--font", default=None,
                   help="font family name, or path to a .ttf/.otf, for chart text")
```

In `main()`, immediately after `args = build_parser().parse_args(argv)` (line 120), add the validation:

```python
    if args.cell_times:
        problem = None
        if args.format != "heatmap":
            problem = "--cell-times applies only to --format heatmap"
        elif not args.transitions:
            problem = "--cell-times requires --transitions"
        elif args.calendar != "gregorian":
            problem = "--cell-times requires --calendar gregorian"
        if problem:
            print(f"error: {problem}", file=sys.stderr)
            return 2
```

Then extend the `options` dict (around line 137) to carry the new flags:

```python
    options = {"theme": args.theme, "tint": args.tint, "calendar": args.calendar,
               "lunar_anchor": args.lunar_anchor, "size": args.size,
               "cell_times": args.cell_times, "font": args.font}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -k cell_times -v`
Expected: PASS (all three return code `2`).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat: --size/--cell-times/--font flags + cell-times validation"
```

---

## Task 5: Heatmap rendering — sizing, font, in-cell text

**Files:**
- Modify: `src/moonphase/renderers/heatmap.py`
- Test: `tests/test_renderers.py`

This task wires the helpers into `_render_gregorian`. `_render_lunar` is untouched. The sizing/measurement uses font metrics, so it lives here (matplotlib-side, smoke-tested).

- [ ] **Step 1: Add module constants, imports, and helper functions**

At the top of `src/moonphase/renderers/heatmap.py`, extend the imports:

```python
from contextlib import nullcontext
from datetime import date

from ..heatmap_layout import day_cells, lunations, principal_phase_days, transitions_by_day
from ..moondisk import illuminated_fraction, lit_polygon
from ..theme import theme_of
from . import register
from .celltext import damped_text_color
```

(Keep the existing `_MON` list. `nullcontext` and `transitions_by_day`/`damped_text_color` are the additions.)

Add these module-level constants and helpers (place them above `render`, e.g. after `_opts`):

```python
_DPI = 150          # px <-> inch conversion for --size and giant sizing
_STACK_CAP = 4      # max stacked time lines before a cell collapses to a "N×" badge


def _giant_params(report):
    o = report.options or {}
    return o.get("size"), o.get("cell_times", False), o.get("font")


def _label_of(report):
    """Return f(entered_index) -> short text: the custom label when --labels was
    given and non-empty for that slot, else the bare index number."""
    labels = report.labels

    def label(idx):
        if labels and idx < len(labels) and labels[idx]:
            return labels[idx]
        return str(idx)

    return label


def _resolve_font(family):
    """Resolve ``--font`` to a usable family name. A filesystem path is
    registered with matplotlib; an unknown family name raises ValueError."""
    if not family:
        return None
    import os
    from matplotlib import font_manager
    if os.path.exists(family):
        font_manager.fontManager.addfont(family)
        return font_manager.FontProperties(fname=family).get_name()
    available = {f.name for f in font_manager.fontManager.ttflist}
    if family not in available:
        raise ValueError(
            f"font {family!r} not found; install it or pass a .ttf/.otf path")
    return family


def _measure_line_inches(plt, text, family):
    """True width/height in inches of ``text`` rendered at 9 pt in ``family``."""
    fig = plt.figure(dpi=_DPI)
    try:
        t = fig.text(0.0, 0.0, text, fontsize=9, family=family)
        fig.canvas.draw()
        bb = t.get_window_extent()
        return bb.width / _DPI, bb.height / _DPI
    finally:
        plt.close(fig)


def _giant_figsize(plt, day_trans, label_of, n_rows, has_legend, family):
    """Figure size (inches) that fits the widest 'label @ HH:MM' line and the
    tallest stacked cell at the 9 pt floor."""
    lines, max_rows = [], 1
    for crossings in day_trans.values():
        max_rows = max(max_rows, min(len(crossings), _STACK_CAP))
        for idx, local in crossings:
            lines.append(f"{label_of(idx)} @ {local.strftime('%H:%M')}")
    longest = max(lines, key=len) if lines else "0 @ 00:00"
    w_in, h_in = _measure_line_inches(plt, longest, family)
    cell_w = w_in + 0.12
    cell_h = max_rows * (h_in * 1.30) + 0.06
    gutter, title = 1.1, 0.6
    legend = 0.7 if has_legend else 0.2
    return gutter + 31 * cell_w, title + n_rows * cell_h + legend


def _resolve_figsize(plt, size, cell_times, day_trans, label_of, n_rows,
                     has_legend, family):
    """Pick the figure size (inches) or None to keep the default auto-size.
    Raises ValueError when an explicit --size is below the giant floor."""
    if cell_times:
        need_w, need_h = _giant_figsize(plt, day_trans, label_of, n_rows,
                                        has_legend, family)
        if size is not None:
            need_px = (need_w * _DPI, need_h * _DPI)
            if size[0] < need_px[0] or size[1] < need_px[1]:
                raise ValueError(
                    f"--size {size[0]}x{size[1]} is too small for --cell-times "
                    f"labels at the 9pt minimum; need at least "
                    f"{round(need_px[0])}x{round(need_px[1])}")
            return (size[0] / _DPI, size[1] / _DPI)
        return (need_w, need_h)
    if size is not None:
        return (size[0] / _DPI, size[1] / _DPI)
    return None
```

- [ ] **Step 2: Add the in-cell text drawing helper**

Add (near `_draw_marker`):

```python
def _draw_cell_times(ax, x0, row, crossings, cell, scheme, tint, label_of):
    """Draw a day's transition times inside its cell as low-contrast text,
    collapsing to a 'N×' badge past the stack cap."""
    a, i = cell
    color = damped_text_color(_tint(a, i, scheme, tint))
    cx, cy = x0 + 0.47, row + 0.47
    if len(crossings) > _STACK_CAP:
        ax.text(cx, cy, f"{len(crossings)}×", ha="center", va="center",
                fontsize=9, color=color, zorder=8)
        return
    text = "\n".join(f"{label_of(idx)} @ {local.strftime('%H:%M')}"
                     for idx, local in crossings)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9, color=color,
            zorder=8)
```

- [ ] **Step 3: Rewrite `_render_gregorian` to use them**

Replace the entire `_render_gregorian` function with:

```python
def _render_gregorian(plt, report, samples, tint, caption, theme, out):
    import matplotlib
    scheme = report.scheme
    size, cell_times, font = _giant_params(report)
    cells = {d: (a, i) for d, a, i in day_cells(samples, report.tz)}
    marks = principal_phase_days(samples, report.tz)
    months = sorted({d[:7] for d in cells})
    legend = tint == "index"
    nrows = len(months)

    family = _resolve_font(font)
    day_trans = (transitions_by_day(report.events, report.tz, scheme.divisions)
                 if cell_times else {})
    label_of = _label_of(report)
    figsize = _resolve_figsize(plt, size, cell_times, day_trans, label_of,
                               nrows, legend, family)
    if figsize is None:
        figsize = (11, 0.9 + 0.42 * nrows)

    ctx = (matplotlib.rc_context({"font.family": family}) if family
           else nullcontext())
    with ctx:
        fig, ax = plt.subplots(figsize=figsize)
        try:
            for row, ym in enumerate(months):
                y, m = ym[:4], int(ym[5:7])
                ax.text(-0.6, row + 0.5, f"{_MON[m - 1]} {y}", ha="right",
                        va="center", fontsize=7, color=theme.fg)
                ndays = (date(int(y) + (m // 12), (m % 12) + 1, 1)
                         - date(int(y), m, 1)).days
                for dd in range(1, ndays + 1):
                    key = f"{y}-{m:02d}-{dd:02d}"
                    if key not in cells:
                        continue
                    a, i = cells[key]
                    ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                                 facecolor=_tint(a, i, scheme, tint),
                                 edgecolor="none"))
                    if key in marks:
                        if cell_times:
                            _draw_marker(ax, dd - 0.85, row + 0.18, 0.13,
                                         marks[key], theme)
                        else:
                            _draw_marker(ax, dd - 0.53, row + 0.47, 0.30,
                                         marks[key], theme)
                    if cell_times and key in day_trans:
                        _draw_cell_times(ax, dd - 1, row, day_trans[key],
                                         cells[key], scheme, tint, label_of)
            if legend:
                _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 0.9, 0.6)
            ax.set_xlim(-0.5, 31)
            ax.set_ylim(nrows + (2.0 if legend else 0.2), -0.5)
            ax.set_xticks([0.5, 9.5, 19.5, 29.5])
            ax.set_xticklabels(["1", "10", "20", "30"], fontsize=7)
            ax.set_yticks([])
            years = sorted({d[:4] for d in cells})
            _finish(plt, fig, ax, theme,
                    f"{', '.join(years)} — {scheme.divisions} microphases · "
                    f"tint: {tint} · times in {caption}")
            fig.tight_layout()
            _save(plt, fig, out)
        finally:
            plt.close(fig)
```

(The only changes vs. the original: the `size/cell_times/font` resolution and `figsize` up top, the `rc_context` wrapper, the corner-vs-center marker choice under `cell_times`, and the `_draw_cell_times` call.)

- [ ] **Step 4: Write the smoke tests**

In `tests/test_renderers.py`, update the `_heatmap_report` helper to accept events, and add three tests. Replace the existing `_heatmap_report` definition with:

```python
def _heatmap_report(days=70, options=None, events=None):
    from datetime import timedelta
    samples = []
    for i in range(days * 24):
        when = T0 + timedelta(hours=i)
        ang = (12.19 * (when - T0).total_seconds() / 86400.0) % 360.0
        samples.append(PhaseSample(when=when, angle_deg=ang,
                                   microphase=int(ang / 22.5 + 0.5) % 16))
    return Report(scheme=MicrophaseScheme.from_divisions(16), mode="series",
                  samples=samples, options=options, events=events)
```

Then add:

```python
def _giant_transitions():
    from datetime import timedelta
    return [
        PhaseEvent(when=T0 + timedelta(days=2, hours=4), angle_deg=11.25,
                   kind="transition", index=0, name=None),
        PhaseEvent(when=T0 + timedelta(days=2, hours=20), angle_deg=33.75,
                   kind="transition", index=1, name=None),
        PhaseEvent(when=T0 + timedelta(days=6, hours=9), angle_deg=56.25,
                   kind="transition", index=2, name=None),
    ]


def test_heatmap_cell_times_writes_png(tmp_path):
    r = _heatmap_report(
        options={"tint": "illumination", "calendar": "gregorian",
                 "cell_times": True},
        events=_giant_transitions())
    out = tmp_path / "giant.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_cell_times_too_small_size_raises(tmp_path):
    r = _heatmap_report(
        options={"tint": "illumination", "calendar": "gregorian",
                 "cell_times": True, "size": (200, 200)},
        events=_giant_transitions())
    with pytest.raises(ValueError):
        renderers.get("heatmap")(r, str(tmp_path / "x.png"))


def test_heatmap_size_override_writes_png(tmp_path):
    r = _heatmap_report(options={"tint": "illumination", "calendar": "gregorian",
                                 "size": (1600, 1200)})
    out = tmp_path / "sz.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 5: Run the renderer suite**

Run: `pytest tests/test_renderers.py -k heatmap -v`
Expected: PASS — existing heatmap tests still green; the three new ones pass (giant render writes a file, too-small `--size` raises `ValueError`, plain `--size` override writes a file).

- [ ] **Step 6: Full suite + lint**

Run: `pytest -q && ruff check src tests`
Expected: all pass, no lint errors.

- [ ] **Step 7: Commit**

```bash
git add src/moonphase/renderers/heatmap.py tests/test_renderers.py
git commit -m "feat: giant heatmap with in-cell transition times (--cell-times/--size/--font)"
```

---

## Task 6: Documentation — README + spec

**Files:**
- Modify: `README.md:135-149` (CLI synopsis) and `README.md:162` (heatmap row)
- Modify: `docs/specs/primary.md`

- [ ] **Step 1: Update the README CLI synopsis**

In `README.md`, inside the ``` block at lines 135-149, add these three lines after the `--lunar-anchor` line:

```
          [--size WxH]               # output image size in px (e.g. 5000x3000)
          [--cell-times]             # heatmap: print transition times in cells (needs --transitions, gregorian)
          [--font NAME|PATH]         # font family name or .ttf/.otf path for chart text
```

- [ ] **Step 2: Update the README heatmap renderer row**

In `README.md`, append to the `heatmap` table row (line 162), before the closing `|`:

```
 With `--cell-times` (gregorian + `--transitions` only), each day cell also prints the time(s) a microphase transition took effect, in low-contrast text; the figure is auto-sized so 9 pt text fits (override or enlarge with `--size`, restyle with `--font`).
```

- [ ] **Step 3: Update the formal spec**

In `docs/specs/primary.md`, locate the CLI flags / heatmap section (grep for `--tint` or `--calendar`) and add documentation for `--size`, `--cell-times`, and `--font` consistent with the surrounding style. Include: `--size` is `WIDTHxHEIGHT` pixels; `--cell-times` requires `--transitions` and `--calendar gregorian`, prints the entered-microphase time(s) per day cell, auto-sizes the figure from the labels at a 9 pt floor, collapses dense cells to an `N×` badge past 4 lines, and errors if an explicit `--size` is below the computed floor; `--font` takes a family name or a `.ttf`/`.otf` path.

Run to find the anchor: `grep -n "tint\|calendar\|heatmap" docs/specs/primary.md`

- [ ] **Step 4: Verify doc/code consistency**

Run: `grep -n "cell-times\|--size\|--font" README.md docs/specs/primary.md src/moonphase/cli.py`
Expected: the flag names appear in all three, spelled identically (`--cell-times`, `--size`, `--font`).

- [ ] **Step 5: Commit**

```bash
git add README.md docs/specs/primary.md
git commit -m "docs: document --size, --cell-times, --font"
```

---

## Task 7: Sample — giant chart with tap-to-open full-size image

**Files:**
- Create: `samples/labels-8-short.txt`
- Create (generated): `samples/heatmap-cell-times-2026-q1-8div.png`
- Modify: `samples/README.md`

- [ ] **Step 1: Create the short-label file**

Create `samples/labels-8-short.txt` (one terse code per line — shows the `code @ HH:MM` use case):

```
New
WxC
1Q
WxG
Full
WnG
3Q
WnC
```

- [ ] **Step 2: Generate the sample PNG**

Run from the repo root (downloads DE421 on first use):

```bash
moonphase --start 2026-01-01T00:00Z --end 2026-03-31T23:00Z --divisions 8 \
          --transitions --format heatmap --calendar gregorian --cell-times \
          --labels @samples/labels-8-short.txt \
          --out samples/heatmap-cell-times-2026-q1-8div.png
```

Expected: writes `samples/heatmap-cell-times-2026-q1-8div.png` (a wide, giant image) with no error.

- [ ] **Step 3: Add a sample section with a tap-to-open image**

In `samples/README.md`, after the Gregorian heatmap `--tint index` subsection and before the lunar section, add:

```markdown
### Giant heatmap with in-cell transition times — `--cell-times`

With `--cell-times` (gregorian + `--transitions`), each day cell prints the
time(s) a microphase transition took effect, in low-contrast text — `code @ HH:MM`,
where `code` is the `--labels` value (here terse codes from
[`labels-8-short.txt`](labels-8-short.txt)) or the bare microphase number. The
figure is auto-sized from the labels so 9 pt text stays legible, which makes it
large — **tap the image to open it full-size in a new tab**.

[![Giant cell-times heatmap, 8 divisions, 2026 Q1](heatmap-cell-times-2026-q1-8div.png)](heatmap-cell-times-2026-q1-8div.png)

```bash
moonphase --start 2026-01-01T00:00Z --end 2026-03-31T23:00Z --divisions 8 \
          --transitions --format heatmap --calendar gregorian --cell-times \
          --labels @samples/labels-8-short.txt \
          --out samples/heatmap-cell-times-2026-q1-8div.png
```
```

(The `[![alt](img)](img)` idiom wraps the inline thumbnail in a link to the same file, so tapping opens the full-resolution PNG.)

- [ ] **Step 4: Verify the image link resolves**

Run: `test -f samples/heatmap-cell-times-2026-q1-8div.png && grep -c "heatmap-cell-times-2026-q1-8div.png" samples/README.md`
Expected: file exists; the filename appears twice in `samples/README.md` (the linked image + the `--out` in the command), i.e. count ≥ 2.

- [ ] **Step 5: Commit**

```bash
git add samples/labels-8-short.txt samples/heatmap-cell-times-2026-q1-8div.png samples/README.md
git commit -m "samples: giant --cell-times heatmap with tap-to-open full-size image"
```

---

## Final verification

- [ ] **Run the full suite and lint**

Run: `pytest -q && ruff check src tests`
Expected: all tests pass; no lint errors.

- [ ] **Manual end-to-end sanity (optional, needs ephemeris)**

Run a small high-divisions render to exercise the badge path:

```bash
moonphase --start 2026-01-01T00:00Z --end 2026-01-31T23:00Z --divisions 64 \
          --transitions --format heatmap --cell-times \
          --out /tmp/giant64.png && echo OK
```

Expected: writes `/tmp/giant64.png`; dense days show an `N×` badge rather than overflowing.

- [ ] **Too-small size error path**

```bash
moonphase --start 2026-01-01T00:00Z --end 2026-03-31T23:00Z --divisions 8 \
          --transitions --format heatmap --cell-times --size 100x100 \
          --out /tmp/x.png; echo "exit=$?"
```

Expected: prints an `error: --size ... too small ...` message and a non-zero exit.

---

## Notes / tunable knobs

- `_STACK_CAP` (4), the `0.12`/`0.06` cell paddings, the `1.30` line-spacing, the `gutter`/`title`/`legend` inch allowances, and `_DPI` (150) are all tunable after viewing real output — the 9 pt floor is the legibility guarantee, the rest is fit margin.
- `--size`/`--font` only affect the `heatmap` renderer in this change; the same `options` keys can be adopted by `chart`/`almanac` later without CLI changes.
- Lunar layout, phase *centres*, and the non-giant heatmap path are intentionally unchanged.
