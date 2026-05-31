# Phase 3: New Renderers & Layouts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `almanac` (moon-disk ribbon, events mode) and `heatmap` (calendar grid, series mode) renderers, with `--tint {illumination,index}` and a `--calendar lunar` / `--lunar-anchor {new,full}` layout, matching the approved mockups (`docs/archive/mockups-2026-05-29.png`).

**Architecture:** A pure `moondisk.py` gives the illuminated fraction and lit-limb polygon (new→empty, full→solid). A pure `heatmap_layout.py` derives day tints, principal-phase days, and lunation segments **from the dense series** (`report.samples`) so renderers need no ephemeris. Renderer-specific flags travel on a new `Report.options` dict; the `render(report, out)` signature is unchanged. The two renderers are matplotlib leaves consuming a `Report`.

**Tech Stack:** Python ≥3.10, numpy, matplotlib (lazy import inside renderers), pytest, ruff.

---

## Scope

Implements spec §5.6 F6.3 (`heatmap`, `almanac`), §5.5 F5.3 (`--tint`, `--calendar`, `--lunar-anchor`). Mockup reference: `docs/archive/mockups-2026-05-29.png` (A=strip-chart already shipped; **B=heatmap**, **C=almanac** are this phase). **Phase 4 (`--labels`) remains out of scope** — `Report.labels` stays unused here.

Matplotlib output is verified with **smoke/structural tests** (file written, non-empty; for SVG, expected text present) plus thorough unit tests of the pure helpers. Visual fidelity is confirmed by rendering sample PNGs at the end.

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/moonphase/moondisk.py` | create | `illuminated_fraction`, `lit_polygon` (pure geometry) |
| `src/moonphase/heatmap_layout.py` | create | `day_cells`, `principal_phase_days`, `lunations` (pure, from samples) |
| `src/moonphase/report.py` | modify | add `options: dict \| None` field |
| `src/moonphase/cli.py` | modify | `--tint`, `--calendar`, `--lunar-anchor`; pass `options` to `Report` |
| `src/moonphase/renderers/almanac.py` | create | events-mode moon-disk ribbon |
| `src/moonphase/renderers/heatmap.py` | create | series-mode calendar grid (gregorian + lunar) |
| `src/moonphase/renderers/__init__.py` | modify | import the two new renderer modules |
| `src/moonphase/naming.py` | (read only) | principal names reused for markers |
| `tests/test_moondisk.py` | create | geometry |
| `tests/test_heatmap_layout.py` | create | layout helpers |
| `tests/test_report.py` | modify | `options` default |
| `tests/test_cli.py` | modify | new flags reach `report.options` |
| `tests/test_renderers.py` | modify | almanac/heatmap smoke + registry/modes |

---

## Task 1: Moon-disk geometry (`moondisk.py`)

**Files:** Create `src/moonphase/moondisk.py`, `tests/test_moondisk.py`.

- [ ] **Step 1: Write the failing test** — create `tests/test_moondisk.py`:

```python
import math

from moonphase.moondisk import illuminated_fraction, lit_polygon


def test_illuminated_fraction():
    assert illuminated_fraction(0) == 0.0
    assert abs(illuminated_fraction(90) - 0.5) < 1e-9
    assert abs(illuminated_fraction(180) - 1.0) < 1e-9
    assert abs(illuminated_fraction(270) - 0.5) < 1e-9


def test_new_moon_has_no_polygon():
    assert lit_polygon(0, 0, 1.0, 0.0) is None
    assert lit_polygon(0, 0, 1.0, 360.0) is None


def _xrange(poly):
    xs = [x for x, _ in poly]
    return min(xs), max(xs)


def test_full_moon_spans_whole_disk():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 180.0))
    assert lo < -0.98 and hi > 0.98


def test_first_quarter_is_right_half():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 90.0))
    assert abs(lo) < 0.02 and hi > 0.98          # lit from center to right limb


def test_last_quarter_is_left_half():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 270.0))
    assert lo < -0.98 and abs(hi) < 0.02         # lit from left limb to center


def test_waxing_crescent_lit_on_right():
    # thin crescent: lit region hugs the right limb (mean x > 0)
    poly = lit_polygon(0, 0, 1.0, 45.0)
    mean_x = sum(x for x, _ in poly) / len(poly)
    assert mean_x > 0.3


def test_waning_crescent_lit_on_left():
    poly = lit_polygon(0, 0, 1.0, 315.0)
    mean_x = sum(x for x, _ in poly) / len(poly)
    assert mean_x < -0.3
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_moondisk.py -v`** — FAIL (no module).

- [ ] **Step 3: Implement `src/moonphase/moondisk.py`:**

```python
"""Moon-disk geometry: illuminated fraction and the lit-limb polygon.

Phase angle 0° = new (dark), 180° = full (lit). A renderer draws a dark disk
and fills the polygon returned here. New returns ``None`` (nothing lit); full
returns the whole disk. Coordinates are plain Cartesian; the lit region is
symmetric top-to-bottom, so callers may use either y-orientation.
"""

from __future__ import annotations

import math


def illuminated_fraction(theta_deg: float) -> float:
    """Fraction of the disk lit: 0 at new, 0.5 at the quarters, 1 at full."""
    return (1.0 - math.cos(math.radians(theta_deg))) / 2.0


def lit_polygon(cx: float, cy: float, r: float, theta_deg: float, n: int = 48):
    """Vertices of the illuminated region of a moon at phase ``theta_deg`` on a
    disk of radius ``r`` centered at ``(cx, cy)``. Returns ``None`` for new.

    The bright limb is the right semicircle for waxing phases; waning phases are
    the mirror image. The terminator is a half-ellipse whose signed x-radius is
    ``r·cos(folded angle)`` — at the quarter it collapses to the vertical
    diameter (exact half disk); at full it reaches the opposite limb.
    """
    th = theta_deg % 360.0
    if illuminated_fraction(th) < 0.005:
        return None
    waning = th > 180.0
    tp = 360.0 - th if waning else th
    rxt = r * math.cos(math.radians(tp))
    pts = []
    for i in range(n + 1):                       # bright limb: right semicircle
        phi = -math.pi / 2 + math.pi * i / n
        pts.append((cx + r * math.cos(phi), cy - r * math.sin(phi)))
    for i in range(n + 1):                       # terminator: back to start
        phi = math.pi / 2 - math.pi * i / n
        pts.append((cx + rxt * math.cos(phi), cy - r * math.sin(phi)))
    if waning:
        pts = [(2 * cx - x, y) for (x, y) in pts]
    return pts
```

- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_moondisk.py -v`** — PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/moondisk.py tests/test_moondisk.py
git commit -m "feat: moon-disk geometry (illuminated fraction + lit-limb polygon)"
```

---

## Task 2: `Report.options` + CLI flags

**Files:** Modify `src/moonphase/report.py`, `src/moonphase/cli.py`, `tests/test_report.py`, `tests/test_cli.py`.

- [ ] **Step 1: Update tests.** In `tests/test_report.py`, add to `test_report_defaults` (keep existing asserts): `assert r.options is None`.
In `tests/test_cli.py`, append:

```python
def test_main_passes_options_to_report(monkeypatch):
    captured = {}

    def fake_render(report, out):
        captured["opts"] = report.options

    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get", lambda name: fake_render)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "8",
        "--format", "json", "--tint", "index", "--calendar", "lunar",
        "--lunar-anchor", "full",
    ])
    assert rc == 0
    assert captured["opts"] == {"tint": "index", "calendar": "lunar", "lunar_anchor": "full"}
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_report.py tests/test_cli.py -v`** — FAIL (no `options`; flags unknown).

- [ ] **Step 3: Add the `options` field.** In `src/moonphase/report.py`, add one field after `labels` (or before — order only matters for positional construction; put it last):

```python
    options: dict | None = None                # renderer-specific flags (tint/calendar/...)
```

- [ ] **Step 4: Add CLI flags + wiring.** In `src/moonphase/cli.py` `build_parser()`, add after `--transitions`:

```python
    p.add_argument("--tint", choices=["illumination", "index"], default="illumination",
                   help="heatmap cell tint (heatmap only)")
    p.add_argument("--calendar", choices=["gregorian", "lunar"], default="gregorian",
                   help="heatmap/terminal layout: civil months or lunar months")
    p.add_argument("--lunar-anchor", choices=["new", "full"], default="new",
                   help="lunar-month boundary (with --calendar lunar)")
```

In `main()`, build an options dict and pass it to BOTH `Report(...)` constructions (add `options=options`):

```python
    options = {"tint": args.tint, "calendar": args.calendar,
               "lunar_anchor": args.lunar_anchor}
```
(place this line right after `report`-mode resolution / before constructing the reports, and add `options=options` to each `Report(...)` call.)

- [ ] **Step 5: Run `.venv/bin/python -m pytest -q`** — full suite green (incl. the two new tests). `.venv/bin/ruff check src tests` — clean.

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/report.py src/moonphase/cli.py tests/test_report.py tests/test_cli.py
git commit -m "feat: Report.options + --tint/--calendar/--lunar-anchor CLI flags"
```

---

## Task 3: `almanac` renderer (events mode)

**Files:** Create `src/moonphase/renderers/almanac.py`; modify `src/moonphase/renderers/__init__.py`, `tests/test_renderers.py`.

- [ ] **Step 1: Add tests** to `tests/test_renderers.py` (helpers `S4`, `T0`, `renderers`, `Report`, `PhaseEvent`, `matplotlib` already present):

```python
def _almanac_report():
    from datetime import timedelta
    evs = []
    names = ["New", "First Quarter", "Full", "Last Quarter"]
    for k, (ang, nm) in enumerate(zip((0, 90, 180, 270), names)):
        evs.append(PhaseEvent(when=T0 + timedelta(days=7.4 * k), angle_deg=float(ang),
                              kind="center", index=k, name=nm))
    return Report(scheme=S4, mode="events", events=evs)


def test_almanac_registered_events_only():
    assert "almanac" in renderers.available("events")
    assert "almanac" not in renderers.available("series")


def test_almanac_writes_png(tmp_path):
    out = tmp_path / "a.png"
    renderers.get("almanac")(_almanac_report(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_almanac_empty_events_raises(tmp_path):
    r = Report(scheme=S4, mode="events", events=[])
    import pytest
    with pytest.raises(ValueError):
        renderers.get("almanac")(r, str(tmp_path / "x.png"))
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_renderers.py -k almanac -v` — FAIL (no almanac).

- [ ] **Step 3: Implement `src/moonphase/renderers/almanac.py`:**

```python
"""Almanac moon-disk ribbon: rendered moon disks at each phase-center event,
with transition points marked between them."""

from __future__ import annotations

from ..moondisk import lit_polygon
from . import register

_DARK = "#15171f"
_LIT = "#f4f1e6"
_OUT = "#717a90"
_TRANS = "#d98324"


def _interp_x(when, centers):
    """X position for a transition time, interpolated between bounding centers
    (centers are drawn at integer x = their list index)."""
    for i in range(len(centers) - 1):
        a, b = centers[i].when, centers[i + 1].when
        if a <= when <= b and b > a:
            return i + (when - a) / (b - a)
    return None


@register("almanac", modes={"events"})
def render(report, out):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon

    centers = [e for e in (report.events or []) if e.kind == "center"]
    transitions = [e for e in (report.events or []) if e.kind == "transition"]
    if not centers:
        raise ValueError("no phase-center events to render")

    tz = report.tz
    n = len(centers)
    fig, ax = plt.subplots(figsize=(min(2.0 + 1.7 * n, 26), 3.2))
    try:
        r = 0.34
        for i, e in enumerate(centers):
            ax.add_patch(Circle((i, 0), r, facecolor=_DARK, edgecolor=_OUT, lw=1, zorder=2))
            poly = lit_polygon(i, 0, r, e.angle_deg)
            if poly:
                ax.add_patch(Polygon(poly, closed=True, facecolor=_LIT,
                                     edgecolor="none", zorder=3))
            ax.add_patch(Circle((i, 0), r, fill=False, edgecolor=_OUT, lw=1, zorder=4))
            local = tz.to_display(e.when)
            ax.text(i, -0.60, e.name or f"#{e.index}", ha="center", va="top",
                    fontsize=9, fontweight="bold")
            ax.text(i, -0.78, local.strftime("%b %d %H:%M"), ha="center", va="top",
                    fontsize=7.5, color="#888")
        for tr in transitions:
            x = _interp_x(tr.when, centers)
            if x is not None:
                ax.plot([x, x], [-0.42, 0.42], color=_TRANS, ls="--", lw=1.2, zorder=1)

        ax.set_xlim(-0.7, n - 0.3)
        ax.set_ylim(-1.0, 0.7)
        ax.axis("off")
        start_utc, end_utc = report.span()
        ax.set_title(f"Lunar almanac — {report.scheme.divisions} divisions · "
                     f"times in {tz.caption(start_utc, end_utc)}", fontsize=10)
        fig.tight_layout()
        if out:
            fig.savefig(out, dpi=150)
        else:
            plt.show()
    finally:
        plt.close(fig)
```

- [ ] **Step 4: Register it.** In `src/moonphase/renderers/__init__.py`, change the import-side-effect line to include almanac:

```python
from . import chart, data, terminal, almanac  # noqa: E402,F401
```

- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_renderers.py -k almanac -v` (3 pass), then `.venv/bin/python -m pytest -q` (full suite green), then `.venv/bin/ruff check src tests` (clean).

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/renderers/almanac.py src/moonphase/renderers/__init__.py tests/test_renderers.py
git commit -m "feat: almanac moon-disk ribbon renderer (events mode)"
```

---

## Task 4: Heatmap layout helpers (`heatmap_layout.py`)

**Files:** Create `src/moonphase/heatmap_layout.py`, `tests/test_heatmap_layout.py`.

These pure helpers derive everything the heatmap needs from the time-ordered series samples. A helper builds synthetic samples for tests.

- [ ] **Step 1: Write the failing test** — create `tests/test_heatmap_layout.py`:

```python
from datetime import datetime, timedelta, timezone

from moonphase.calendar import PhaseSample
from moonphase.displaytz import DisplayZone
from moonphase.heatmap_layout import day_cells, principal_phase_days, lunations

UTC = DisplayZone.utc()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _series(days, per_day=24, rate_deg_per_day=12.19, phase0=0.0):
    """Synthetic hourly samples with a linearly advancing phase angle."""
    out = []
    step_h = 24 // per_day
    n = days * per_day
    for i in range(n):
        when = T0 + timedelta(hours=i * step_h)
        ang = (phase0 + rate_deg_per_day * (when - T0).total_seconds() / 86400.0) % 360.0
        out.append(PhaseSample(when=when, angle_deg=ang, microphase=int(ang / 45 + 0.5) % 8))
    return out


def test_day_cells_one_per_local_day():
    cells = day_cells(_series(3), UTC)
    dates = [c[0] for c in cells]
    assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert all(0.0 <= c[1] < 360.0 for c in cells)   # angle present


def test_principal_phase_days_marks_quarters():
    # ~12.19 deg/day -> Full (180) near day 14-15, New (~360) near day 29-30
    marks = principal_phase_days(_series(31), UTC)
    # there must be a Full (index 2) and a First Quarter (index 1) marked
    assert 2 in marks.values()
    assert 1 in marks.values()
    # the marked dates are valid ISO days
    assert all(len(d) == 10 for d in marks)


def test_lunations_new_anchor_segments_a_cycle():
    segs = lunations(_series(70), UTC, "new")   # ~2.4 synodic months
    assert len(segs) >= 1
    s = segs[0]
    assert set(s) >= {"start", "end", "mid", "days"}
    assert 28 <= s["days"] <= 31
    # mid (full) falls between start and end
    assert s["start"] < s["mid"] < s["end"]


def test_lunations_full_anchor_uses_180_crossings():
    segs = lunations(_series(70), UTC, "full")
    assert segs and 28 <= segs[0]["days"] <= 31
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_heatmap_layout.py -v`** — FAIL (no module).

- [ ] **Step 3: Implement `src/moonphase/heatmap_layout.py`:**

```python
"""Pure layout helpers for the heatmap renderer, derived entirely from the
time-ordered series samples (no ephemeris needed). Boundaries are accurate to
the sampling cadence, which is plenty for a day-resolution calendar.
"""

from __future__ import annotations


def day_cells(samples, tz):
    """One representative ``(date_iso, angle_deg, microphase)`` per display-tz
    day — the first sample falling in that local day."""
    seen: dict[str, tuple] = {}
    for p in samples:
        d = tz.to_display(p.when).date().isoformat()
        if d not in seen:
            seen[d] = (p.angle_deg, p.microphase)
    return [(d, a, i) for d, (a, i) in sorted(seen.items())]


def principal_phase_days(samples, tz):
    """Map ``date_iso -> principal index`` (0=New, 1=First Qtr, 2=Full,
    3=Last Qtr) for each day a principal phase (a multiple of 90°) is crossed.
    Detected from forward-advancing angle between consecutive samples."""
    out: dict[str, int] = {}
    prev = None
    for p in samples:
        a = p.angle_deg
        if prev is not None:
            pa, pwhen = prev
            day = tz.to_display(p.when).date().isoformat()
            if a < pa:                       # wrapped through 360 -> New
                out[day] = 0
            for k, target in ((1, 90.0), (2, 180.0), (3, 270.0)):
                if pa < target <= a:
                    out[day] = k
        prev = (a, p.when)
    return out


def lunations(samples, tz, anchor):
    """Segment the series into lunations bounded by ``anchor`` crossings
    ('new' -> 0° wrap, 'full' -> 180°). Each segment is a dict with display-tz
    ``start``/``end``/``mid`` ISO dates and a ``days`` count. ``mid`` is the
    opposite anchor's date (full for new-anchored, new for full-anchored)."""
    boundaries = []
    prev = None
    for p in samples:
        a = p.angle_deg
        if prev is not None:
            pa, _ = prev
            crossed = (a < pa) if anchor == "new" else (pa < 180.0 <= a)
            if crossed:
                boundaries.append(tz.to_display(p.when))
        prev = (a, p.when)

    segs = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        mid = s + (e - s) / 2
        segs.append({
            "start": s.date().isoformat(),
            "end": e.date().isoformat(),
            "mid": mid.date().isoformat(),
            "days": (e.date() - s.date()).days,
        })
    return segs
```

- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_heatmap_layout.py -v`** — PASS (5 tests). If `principal_phase_days` misses a quarter due to the synthetic rate, that is a real detection bug — fix the crossing logic, do not weaken the test.

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/heatmap_layout.py tests/test_heatmap_layout.py
git commit -m "feat: pure heatmap layout helpers (day cells, principal phases, lunations)"
```

---

## Task 5: `heatmap` renderer (gregorian + lunar)

**Files:** Create `src/moonphase/renderers/heatmap.py`; modify `src/moonphase/renderers/__init__.py`, `tests/test_renderers.py`.

- [ ] **Step 1: Add tests** to `tests/test_renderers.py`:

```python
def _heatmap_report(days=70, options=None):
    from datetime import timedelta
    samples = []
    for i in range(days * 24):
        when = T0 + timedelta(hours=i)
        ang = (12.19 * (when - T0).total_seconds() / 86400.0) % 360.0
        samples.append(PhaseSample(when=when, angle_deg=ang,
                                   microphase=int(ang / 22.5 + 0.5) % 16))
    return Report(scheme=MicrophaseScheme.from_divisions(16), mode="series",
                  samples=samples, options=options)


def test_heatmap_registered_series_only():
    assert "heatmap" in renderers.available("series")
    assert "heatmap" not in renderers.available("events")


def test_heatmap_gregorian_illumination_png(tmp_path):
    out = tmp_path / "h.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "illumination",
                             "calendar": "gregorian"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_index_tint_png(tmp_path):
    out = tmp_path / "h2.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "index",
                             "calendar": "gregorian"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_lunar_layout_png(tmp_path):
    out = tmp_path / "h3.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "illumination",
                             "calendar": "lunar", "lunar_anchor": "new"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_empty_samples_raises(tmp_path):
    import pytest
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[])
    with pytest.raises(ValueError):
        renderers.get("heatmap")(r, str(tmp_path / "x.png"))
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_renderers.py -k heatmap -v` — FAIL.

- [ ] **Step 3: Implement `src/moonphase/renderers/heatmap.py`:**

```python
"""Calendar heatmap. Gregorian (months × days) or lunar (one phase-aligned
strip per lunation). Tinted by illuminated fraction or by microphase index."""

from __future__ import annotations

from datetime import date

from ..heatmap_layout import day_cells, lunations, principal_phase_days
from ..moondisk import illuminated_fraction, lit_polygon
from . import register

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_GLYPH_NAMES = ["New", "First Qtr", "Full", "Last Qtr"]


def _tint(angle, microphase, scheme, mode):
    if mode == "index":
        import matplotlib.colors as mc
        return mc.hsv_to_rgb((microphase / scheme.divisions, 0.55, 0.72))
    f = illuminated_fraction(angle)
    v = 0.08 + 0.88 * f
    return (v, v, min(1.0, v + 0.05))


def _opts(report):
    o = report.options or {}
    return (o.get("tint", "illumination"), o.get("calendar", "gregorian"),
            o.get("lunar_anchor", "new"))


def _draw_marker(ax, cx, cy, rr, principal_index):
    from matplotlib.patches import Circle, Polygon
    # dark chip so the marker shows on any cell tint
    ax.add_patch(Circle((cx, cy), rr * 1.35, facecolor="#0c0e14",
                        edgecolor="#aab2c4", lw=0.6, zorder=4))
    ang = principal_index * 90.0
    ax.add_patch(Circle((cx, cy), rr, facecolor="#15171f", edgecolor="none", zorder=5))
    poly = lit_polygon(cx, cy, rr, ang)
    if poly:
        ax.add_patch(Polygon(poly, closed=True, facecolor="#f4f1e6",
                            edgecolor="none", zorder=6))
    ax.add_patch(Circle((cx, cy), rr, fill=False, edgecolor="#cdd4e4", lw=0.8, zorder=7))


@register("heatmap", modes={"series"})
def render(report, out):
    import matplotlib.pyplot as plt

    samples = report.samples or []
    if not samples:
        raise ValueError("no samples to render")
    tint, calendar, anchor = _opts(report)
    scheme = report.scheme
    tz = report.tz
    caption = tz.caption(*report.span())

    if calendar == "lunar":
        _render_lunar(plt, report, samples, tint, anchor, caption, out)
    else:
        _render_gregorian(plt, report, samples, tint, caption, out)


def _render_gregorian(plt, report, samples, tint, caption, out):
    scheme = report.scheme
    cells = {d: (a, i) for d, a, i in day_cells(samples, report.tz)}
    marks = principal_phase_days(samples, report.tz)
    years = sorted({d[:4] for d in cells})
    fig, ax = plt.subplots(figsize=(11, 0.5 + 0.42 * 12 * len(years)))
    try:
        row = 0
        for y in years:
            for m in range(1, 13):
                ax.text(-0.6, row + 0.5, f"{_MON[m - 1]} {y}", ha="right", va="center",
                        fontsize=7)
                ndays = (date(int(y) + (m // 12), (m % 12) + 1, 1)
                         - date(int(y), m, 1)).days
                for dd in range(1, ndays + 1):
                    key = f"{y}-{m:02d}-{dd:02d}"
                    if key not in cells:
                        continue
                    a, i = cells[key]
                    ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                                 facecolor=_tint(a, i, scheme, tint), edgecolor="none"))
                    if key in marks:
                        _draw_marker(ax, dd - 0.53, row + 0.47, 0.30, marks[key])
                row += 1
        ax.set_xlim(-0.5, 31)
        ax.set_ylim(row, -0.5)
        ax.set_xticks([0.5, 9.5, 19.5, 29.5])
        ax.set_xticklabels(["1", "10", "20", "30"], fontsize=7)
        ax.set_yticks([])
        ax.set_title(f"{', '.join(years)} — {scheme.divisions} microphases · "
                     f"tint: {tint} · times in {caption}", fontsize=10)
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _render_lunar(plt, report, samples, tint, anchor, caption, out):
    scheme = report.scheme
    segs = lunations(samples, report.tz, anchor)
    if not segs:
        raise ValueError("no complete lunations in range for the lunar layout")
    opp = "full" if anchor == "new" else "new"
    cols = 64
    fig, ax = plt.subplots(figsize=(11, 0.6 + 0.5 * len(segs)))
    try:
        for r, seg in enumerate(segs):
            for c in range(cols):
                frac = c / cols                          # 0..1 across the lunation
                ang = (frac * 360.0 + (0 if anchor == "new" else 180.0)) % 360.0
                ax.add_patch(plt.Rectangle((c, r), 1.02, 0.9,
                             facecolor=_tint(ang, int(ang / scheme.step_deg + 0.5)
                                             % scheme.divisions, scheme, tint),
                             edgecolor="none"))
            ax.text(-1, r + 0.45, f"{anchor.title()} {seg['start']}", ha="right",
                    va="center", fontsize=7.5)
            ax.text(cols + 1, r + 0.45, seg["end"], ha="left", va="center", fontsize=7.5)
            ax.text(cols / 2, r + 1.02, f"{opp} {seg['mid']}", ha="center", va="top",
                    fontsize=6.5, color="#555")
        ax.set_xlim(-1, cols + 1)
        ax.set_ylim(len(segs) + 0.3, -0.3)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"Lunar months ({anchor}-anchored) — {scheme.divisions} microphases · "
                     f"tint: {tint} · times in {caption}", fontsize=10)
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _save(plt, fig, out):
    if out:
        fig.savefig(out, dpi=150)
    else:
        plt.show()
```

- [ ] **Step 4: Register it.** In `src/moonphase/renderers/__init__.py`, extend the import line:

```python
from . import chart, data, terminal, almanac, heatmap  # noqa: E402,F401
```

- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_renderers.py -k heatmap -v` (5 pass), then `.venv/bin/python -m pytest -q` (full suite), then `.venv/bin/ruff check src tests` (clean). If ruff flags the unused `scheme`/`anchor` locals in `render`, remove them (they are recomputed in the sub-functions).

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/renderers/heatmap.py src/moonphase/renderers/__init__.py tests/test_renderers.py
git commit -m "feat: heatmap renderer (gregorian + lunar layouts, illumination/index tint)"
```

---

## Task 6: Docs + final verification

**Files:** Modify `README.md`, `docs/specs/primary.md`.

- [ ] **Step 1: README.** In "Renderers", add `heatmap` and `almanac` rows to the table (they were placeholders). In "Design mockups", change B and C from "planned" to "implemented". In "Status & roadmap", move Phase 3 to Implemented and remove it from Planned (leaving Phase 4). Add to "Usage" an example each:
```bash
# Year heatmap tinted by microphase index
moonphase --start 2026-01-01 --end 2026-12-31 --divisions 16 --format heatmap --tint index --out year.png

# Lunar-month heatmap (new-moon boundaries)
moonphase --start 2026-01-01 --end 2026-12-31 --divisions 16 --format heatmap --calendar lunar --out lunar.png

# Almanac ribbon of the principal phases for a quarter
moonphase --start 2026-01-01 --end 2026-03-31 --divisions 4 --format almanac --transitions --out almanac.svg
```

- [ ] **Step 2: Spec.** In `docs/specs/primary.md`, append " *(implemented in Phase 3)*" to the F6.3 bullets for `heatmap` and `almanac` is not granular; instead add a one-line note under §5.6: `> heatmap, almanac, --tint, --calendar/--lunar-anchor implemented in Phase 3.`

- [ ] **Step 3: Final verification + sample renders.**
```bash
.venv/bin/python -m pytest -q          # all green
.venv/bin/ruff check src tests          # clean
```
Render real samples (synthetic ephemeris, no kernel) for visual confirmation:
```bash
.venv/bin/python -c "
import matplotlib; matplotlib.use('Agg')
import moonphase.cli as c, types, numpy as np
from datetime import datetime, timezone
c.PhaseEphemeris=lambda **k: types.SimpleNamespace(phase_angles_deg=lambda ts: np.array([(12.19*(t-datetime(2026,1,1,tzinfo=timezone.utc)).total_seconds()/86400)%360 for t in ts]))
c.main(['--start','2026-01-01','--end','2026-12-31','--divisions','16','--format','heatmap','--tint','index','--out','/tmp/hm_index.png'])
c.main(['--start','2026-01-01','--end','2026-12-31','--divisions','16','--format','heatmap','--calendar','lunar','--out','/tmp/hm_lunar.png'])
c.main(['--start','2026-01-01','--end','2026-03-31','--divisions','4','--format','almanac','--transitions','--out','/tmp/almanac.png'])
print('rendered /tmp/hm_index.png /tmp/hm_lunar.png /tmp/almanac.png')
"
```
Report the three file paths so the controller can surface them for visual review.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/specs/primary.md
git commit -m "docs: mark Phase 3 renderers implemented; add heatmap/almanac usage"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** Task 1 → moon geometry (shared); Task 2 → F5.3 flags + plumbing; Task 3 → F6.3 `almanac` (events mode); Tasks 4–5 → F6.3 `heatmap` (series mode, `--tint`, `--calendar`/`--lunar-anchor`); Task 6 → docs.
- **Purity / testability:** all data logic (geometry, day cells, principal phases, lunations) is in `moondisk.py` / `heatmap_layout.py` with real unit tests; matplotlib renderers are thin and smoke-tested (file written, non-empty), with empty-input guards mirroring the chart renderer.
- **Renderer modes:** `almanac` = events only, `heatmap` = series only — both declared via `register(..., modes=...)`, so `--mode` auto-resolves and incompatible combinations error.
- **No ephemeris in renderers:** lunation boundaries come from series crossings (cadence-accurate, fine for day-resolution). Document that the default 1h cadence gives good boundary dates; very coarse `--sample` would blur them.
- **Type consistency:** `report.options` is read via `_opts`/`.get` with defaults, so a directly-built `Report` (options=None) still renders with sensible defaults. `lit_polygon` / `illuminated_fraction` signatures are used identically in almanac and heatmap.
- **Out of scope:** `--labels` (Phase 4); an explicit `--timezone` override.
