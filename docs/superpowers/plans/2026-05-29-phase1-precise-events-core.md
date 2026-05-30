# Phase 1: Precise Events Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the centered-phase model and exact phase-center / transition-point event-finding end-to-end, behind a `Report`-based renderer interface and a `--mode`/`--transitions` CLI.

**Architecture:** Add an `events.py` module that root-finds exact crossing instants from the existing `PhaseEphemeris.phase_angles_deg` interface (injectable, so it unit-tests offline with a synthetic ephemeris). Migrate the renderer registry from `render(samples, scheme, out)` to a frozen `Report` context object with mode-declaring renderers. Change microphase binning from left-edged to centered.

**Tech Stack:** Python ≥3.10, numpy, matplotlib (lazy), Skyfield (lazy, runtime only), pytest, ruff.

---

## Scope & phasing

This plan is **Phase 1 of a multi-phase delivery** of `docs/specs/primary.md`. It implements:

- **Centered binning** (§5.1 F1.3)
- **Exact events**: phase centers + transition points (§4, §5.3b, `--transitions`)
- **`Report` object + mode-declaring renderer registry** (§5.6 F6.1–F6.2, §8)
- **CLI** `--mode`, `--transitions`, mode auto-resolution + mismatch errors (§5.5 F5.3–F5.4)
- **Built-in microphase names** for N∈{4,8} (§6 names tables)
- Refit of the **existing** renderers (`chart`, `csv`, `json`, `terminal`) to the new interface, including event output and chart event-overlays + axis swap.

**Explicitly deferred (later phases):**
- **Phase 2 — Time handling** (§5.4): display-tz resolution, local-default interpretation, ISO-offset output, DST-aware conversions, mandatory timezone captions. *Phase 1 keeps the current behavior: naive datetimes → UTC, timestamps emitted as the stored UTC-aware ISO 8601.*
- **Phase 3 — New renderers & layouts**: `heatmap` (+`--tint`), `almanac` (+moon-disk geometry), `--calendar lunar` / `--lunar-anchor`.
- **Phase 4 — Custom naming** (`--labels` inline/`@file` sparse-merge). *Phase 1 ships built-in names only; `Report.labels` exists but stays `None`.*

The `Report` dataclass includes `tz` and `labels` fields now (with defaults) so Phases 2 and 4 fill them without changing the dataclass.

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/moonphase/microphase.py` | modify | centered `phase_to_index` |
| `src/moonphase/naming.py` | create | built-in name tables + `default_name` |
| `src/moonphase/events.py` | create | `PhaseEvent`, `build_events` (root-finding) |
| `src/moonphase/report.py` | create | frozen `Report` context object |
| `src/moonphase/renderers/__init__.py` | modify | `register(name, modes)`, `available(mode)`, `modes_for`, `get` |
| `src/moonphase/renderers/data.py` | modify | `csv`/`json` over `Report`, series + events |
| `src/moonphase/renderers/terminal.py` | modify | terminal over `Report`, series + events |
| `src/moonphase/renderers/chart.py` | modify | strip-chart over `Report`; centered bands, axis swap, event overlays |
| `src/moonphase/cli.py` | modify | `--mode`/`--transitions`, `resolve_mode`, build `Report` |
| `src/moonphase/__init__.py` | modify | export `PhaseEvent`, `Report`, `build_events` |
| `tests/test_microphase.py` | modify | centered-binning cases |
| `tests/test_naming.py` | create | name tables |
| `tests/test_events.py` | create | `build_events` with a synthetic ephemeris |
| `tests/test_registry.py` | create | registry modes/available/get |
| `tests/test_renderers.py` | create | data/terminal/chart over hand-built `Report`s |
| `tests/test_cli.py` | create | flag parsing, `resolve_mode`, `Report` construction |

---

## Task 1: Centered microphase binning

**Files:**
- Modify: `src/moonphase/microphase.py:39-45`
- Test: `tests/test_microphase.py`

- [ ] **Step 1: Replace the binning tests with centered-model cases**

Replace the entire contents of `tests/test_microphase.py` with:

```python
from moonphase.microphase import MicrophaseScheme, phase_to_index


def test_divisions_scheme():
    s = MicrophaseScheme.from_divisions(8)
    assert s.divisions == 8
    assert s.step_deg == 45.0


def test_step_scheme():
    s = MicrophaseScheme.from_step(1.0)
    assert s.divisions == 360
    assert s.step_deg == 1.0


def test_centered_buckets_standard_four():
    s = MicrophaseScheme.from_divisions(4)
    # k*step is the CENTER of microphase k
    assert phase_to_index(0.0, s) == 0      # New (center)
    assert phase_to_index(44.0, s) == 0     # still inside New arc
    assert phase_to_index(46.0, s) == 1     # crossed into First Quarter arc
    assert phase_to_index(90.0, s) == 1     # First Quarter center
    assert phase_to_index(180.0, s) == 2    # Full center
    assert phase_to_index(270.0, s) == 3    # Last Quarter center


def test_transition_boundaries_round_half_up():
    s = MicrophaseScheme.from_divisions(4)
    # transition points (k+0.5)*step assign UP to the higher-index arc
    assert phase_to_index(45.0, s) == 1
    assert phase_to_index(135.0, s) == 2
    assert phase_to_index(225.0, s) == 3
    assert phase_to_index(315.0, s) == 0    # wraps up into New (index 4 mod 4)
    assert phase_to_index(314.9, s) == 3    # just below stays in Last Quarter


def test_centered_buckets_sixteen_fractional_step():
    s = MicrophaseScheme.from_divisions(16)  # step 22.5
    assert phase_to_index(11.25, s) == 1     # exact transition → up
    assert phase_to_index(33.75, s) == 2     # exact transition → up
    assert phase_to_index(0.0, s) == 0
    assert phase_to_index(359.999, s) == 0   # wraps to New center


def test_wrap_around():
    s = MicrophaseScheme.from_divisions(32)
    assert phase_to_index(360.0, s) == 0
    assert phase_to_index(-1.0, s) == 0      # just before New center → New
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_microphase.py -v`
Expected: FAIL — current left-edged `phase_to_index` returns the wrong indices (e.g. `phase_to_index(46.0)` returns 0, `phase_to_index(315.0)` returns 3).

- [ ] **Step 3: Implement centered binning**

In `src/moonphase/microphase.py`, replace the body of `phase_to_index` (currently lines 39-45) with:

```python
def phase_to_index(phase_deg: float, scheme: MicrophaseScheme) -> int:
    """Map a phase angle to its microphase index.

    Microphases are *centered* on ``k * step_deg``; an angle maps to the
    nearest center via round-half-up, so exact transition boundaries
    ``(k+0.5)*step`` assign deterministically to the higher-index arc.
    """
    a = phase_deg % 360.0
    return int(a / scheme.step_deg + 0.5) % scheme.divisions
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_microphase.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/microphase.py tests/test_microphase.py
git commit -m "feat: center microphases on k*step with round-half-up binning"
```

---

## Task 2: Built-in microphase names

**Files:**
- Create: `src/moonphase/naming.py`
- Test: `tests/test_naming.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_naming.py`:

```python
from moonphase.microphase import MicrophaseScheme
from moonphase.naming import default_name


def test_names_for_four():
    s = MicrophaseScheme.from_divisions(4)
    assert default_name(0, s) == "New"
    assert default_name(1, s) == "First Quarter"
    assert default_name(2, s) == "Full"
    assert default_name(3, s) == "Last Quarter"


def test_names_for_eight():
    s = MicrophaseScheme.from_divisions(8)
    assert default_name(0, s) == "New"
    assert default_name(1, s) == "Waxing Crescent"
    assert default_name(4, s) == "Full"
    assert default_name(7, s) == "Waning Crescent"


def test_no_names_for_other_divisions():
    s = MicrophaseScheme.from_divisions(16)
    assert default_name(0, s) is None
    assert default_name(5, s) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonphase.naming'`

- [ ] **Step 3: Implement `naming.py`**

Create `src/moonphase/naming.py`:

```python
"""Built-in microphase names for the familiar 4- and 8-division schemes.

Custom names (the ``--labels`` flag) are a later phase; this module only
provides the traditional names, used when ``divisions`` is 4 or 8.
"""

from __future__ import annotations

from .microphase import MicrophaseScheme

_NAMES_4 = ["New", "First Quarter", "Full", "Last Quarter"]
_NAMES_8 = [
    "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


def default_name(index: int, scheme: MicrophaseScheme) -> str | None:
    """Traditional name for microphase ``index``, or ``None`` if the scheme
    has no built-in names (any ``divisions`` other than 4 or 8)."""
    if scheme.divisions == 4:
        return _NAMES_4[index % 4]
    if scheme.divisions == 8:
        return _NAMES_8[index % 8]
    return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_naming.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/naming.py tests/test_naming.py
git commit -m "feat: built-in microphase names for 4- and 8-division schemes"
```

---

## Task 3: Exact event-finding (`events.py`)

**Files:**
- Create: `src/moonphase/events.py`
- Test: `tests/test_events.py`

`build_events` depends only on `ephemeris.phase_angles_deg(times) -> np.ndarray` (the interface `PhaseEphemeris` already exposes), so it is fully unit-testable offline with a synthetic linear ephemeris.

- [ ] **Step 1: Write the failing test**

Create `tests/test_events.py`:

```python
from datetime import datetime, timedelta, timezone

import numpy as np

from moonphase.microphase import MicrophaseScheme
from moonphase.events import PhaseEvent, build_events


class LinearEphemeris:
    """Phase angle advances linearly from phase0 at `rate` deg/day."""

    def __init__(self, t0, rate_deg_per_day=12.0, phase0_deg=0.0):
        self.t0 = t0
        self.rate = rate_deg_per_day
        self.phase0 = phase0_deg

    def phase_angles_deg(self, times):
        return np.array([
            (self.phase0 + self.rate * (t - self.t0).total_seconds() / 86400.0) % 360.0
            for t in times
        ], dtype=float)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _days(event, start=START):
    return (event.when - start).total_seconds() / 86400.0


def test_centers_only_for_divisions_four():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=30), scheme, eph)

    assert all(e.kind == "center" for e in events)
    names = [e.name for e in events]
    # New(0d) FQ(7.5d) Full(15d) LQ(22.5d) New(30d)
    assert names == ["New", "First Quarter", "Full", "Last Quarter", "New"]
    assert _days(events[1]) == 12.0 * 0 + 7.5 or abs(_days(events[1]) - 7.5) < 0.01
    assert abs(_days(events[2]) - 15.0) < 0.01
    assert all(events[i].when < events[i + 1].when for i in range(len(events) - 1))


def test_transitions_interleave_with_centers():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=30), scheme, eph,
                          transitions=True)

    kinds = [e.kind for e in events]
    # 0,45,90,135,180,225,270,315,360 -> C,T,C,T,C,T,C,T,C
    assert kinds == ["center", "transition", "center", "transition",
                     "center", "transition", "center", "transition", "center"]
    # transition at 45 deg bounds microphase 0; at 135 bounds microphase 1
    t45 = next(e for e in events if abs(e.angle_deg - 45.0) < 1e-6)
    assert t45.kind == "transition" and t45.index == 0 and t45.name is None
    t135 = next(e for e in events if abs(e.angle_deg - 135.0) < 1e-6)
    assert t135.index == 1


def test_events_are_phaseevents():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=20), scheme, eph)
    assert events and isinstance(events[0], PhaseEvent)
    assert events[0].when.tzinfo is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonphase.events'`

- [ ] **Step 3: Implement `events.py`**

Create `src/moonphase/events.py`:

```python
"""Exact phase-center and transition-point events via root-finding.

The synodic phase angle advances monotonically (~12.2 deg/day). We coarse-
sample it, unwrap to a monotonic curve, then bisect within the bracketing
interval to locate the exact UTC instant each target angle is crossed.

Only ``ephemeris.phase_angles_deg(times) -> ndarray`` is required, so this is
unit-testable with any object exposing that method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from .microphase import MicrophaseScheme
from .naming import default_name

_DEG_PER_DAY = 12.2          # approximate Moon-minus-Sun elongation rate
_BISECT_ITERS = 40           # ~2e-12 day resolution; well sub-second


@dataclass(frozen=True)
class PhaseEvent:
    when: datetime            # exact UTC instant (tz-aware)
    angle_deg: float          # target elongation crossed (k*step or (k+0.5)*step)
    kind: str                 # "center" | "transition"
    index: int                # microphase index
    name: str | None          # built-in name (centers, N in {4,8}) else None


def _unwrap(angles: np.ndarray) -> np.ndarray:
    """Turn a wrapped [0,360) sequence into a monotonic increasing one."""
    out = np.array(angles, dtype=float)
    add = 0.0
    for i in range(1, len(out)):
        if angles[i] < angles[i - 1]:
            add += 360.0
        out[i] = angles[i] + add
    return out


def _classify(target_unwrapped: float, scheme: MicrophaseScheme):
    target_mod = target_unwrapped % 360.0
    ratio = target_mod / scheme.step_deg
    nearest = round(ratio)
    if abs(ratio - nearest) < 1e-6:
        idx = int(nearest) % scheme.divisions
        return target_mod, "center", idx, default_name(idx, scheme)
    idx = int(math.floor(ratio)) % scheme.divisions
    return target_mod, "transition", idx, None


def build_events(start, end, scheme, ephemeris, transitions=False):
    """Return chronological :class:`PhaseEvent`s in ``[start, end]``.

    With ``transitions=False`` only phase centers (multiples of ``step``).
    With ``transitions=True`` also transition points (odd multiples of
    ``step/2``); the half-step grid is an internal device — events are still
    labeled ``center``/``transition``, never treated as 2N microphases.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start > end:
        raise ValueError("start must be <= end")

    unit = scheme.step_deg / 2.0 if transitions else scheme.step_deg
    coarse_days = max(min((unit / _DEG_PER_DAY) / 4.0, 0.25), 1e-4)

    grid = []
    t = start
    while t <= end:
        grid.append(t)
        t += timedelta(days=coarse_days)
    if grid[-1] < end:
        grid.append(end)

    angles = np.asarray(ephemeris.phase_angles_deg(grid), dtype=float)
    U = _unwrap(angles)

    events: list[PhaseEvent] = []
    m_lo = math.ceil(U[0] / unit)
    m_hi = math.floor(U[-1] / unit)
    for m in range(m_lo, m_hi + 1):
        target = m * unit
        j = int(np.searchsorted(U, target)) - 1
        j = max(0, min(j, len(grid) - 2))
        lo, hi, ref = grid[j], grid[j + 1], float(U[j])
        for _ in range(_BISECT_ITERS):
            mid = lo + (hi - lo) / 2
            a = float(ephemeris.phase_angles_deg([mid])[0])
            u = a + 360.0 * round((ref - a) / 360.0)
            if u < target:
                lo = mid
            else:
                hi = mid
        when = lo + (hi - lo) / 2
        angle_deg, kind, index, name = _classify(target, scheme)
        events.append(PhaseEvent(when=when, angle_deg=angle_deg, kind=kind,
                                 index=index, name=name))
    return events
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/events.py tests/test_events.py
git commit -m "feat: exact phase-center and transition-point event-finding"
```

---

## Task 4: `Report` context object

**Files:**
- Create: `src/moonphase/report.py`

- [ ] **Step 1: Write the failing test (inline in registry test next task uses it; add a minimal smoke here)**

Create `tests/test_report.py`:

```python
from datetime import timezone

from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report


def test_report_defaults():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.mode == "series"
    assert r.events is None
    assert r.tz == timezone.utc      # default until Phase 2
    assert r.labels is None          # default until Phase 4


def test_report_is_frozen():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="events", events=[])
    try:
        r.mode = "series"
    except Exception as e:
        assert "frozen" in type(e).__name__.lower() or "attribute" in str(e).lower()
    else:
        raise AssertionError("Report should be frozen")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonphase.report'`

- [ ] **Step 3: Implement `report.py`**

Create `src/moonphase/report.py`:

```python
"""The frozen context object every renderer consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone, tzinfo

from .calendar import PhaseSample
from .events import PhaseEvent
from .microphase import MicrophaseScheme


@dataclass(frozen=True)
class Report:
    scheme: MicrophaseScheme
    mode: str                                  # "series" | "events"
    samples: list[PhaseSample] | None = None   # present iff mode == "series"
    events: list[PhaseEvent] | None = None      # exact events (overlay or primary)
    tz: tzinfo = timezone.utc                  # display tz; UTC until Phase 2
    labels: list[str] | None = None            # custom names; None until Phase 4
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/report.py tests/test_report.py
git commit -m "feat: add Report context object (tz/labels reserved for later phases)"
```

---

## Task 5: Registry with mode declarations

**Files:**
- Modify: `src/moonphase/renderers/__init__.py`
- Test: `tests/test_registry.py`

This task changes `register` to require a `modes` argument and adds `available(mode)` and `modes_for`. Because `register` now requires `modes`, the three existing renderer modules' decorators must pass it or imports break. So in this task we both rewrite the registry **and** add `modes=...` to each existing `@register(...)` call (Step 4). The renderer *bodies* keep their old `(samples, scheme, out)` signature for now — that's fine, because the registry only stores the function; the call site doesn't change until Task 7. The CLI still calls the old signature until Task 7, so `moonphase` keeps working between these tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_registry.py`:

```python
import pytest

from moonphase import renderers


def test_builtin_renderers_registered():
    names = set(renderers.available())
    assert {"chart", "csv", "json", "terminal"} <= names


def test_modes_for_known_renderers():
    assert "series" in renderers.modes_for("csv")
    assert "events" in renderers.modes_for("csv")


def test_available_filters_by_mode():
    series_formats = set(renderers.available("series"))
    assert "chart" in series_formats and "csv" in series_formats


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        @renderers.register("csv", modes={"series"})
        def _dupe(report, out):
            pass


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        renderers.get("does-not-exist")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL — `register` has no `modes` kwarg / `modes_for` and `available(mode)` don't exist.

- [ ] **Step 3: Rewrite the registry**

Replace the entire contents of `src/moonphase/renderers/__init__.py` with:

```python
"""Output renderer registry.

A renderer is ``render(report, out) -> None``. Register it with the modes it
supports; the CLI uses ``available(mode)`` to validate ``--format`` against
the resolved mode.
"""

from __future__ import annotations

from typing import Callable

from ..report import Report

Renderer = Callable[[Report, "str | None"], None]

_REGISTRY: dict[str, dict] = {}


def register(name: str, modes):
    """Decorator: register ``fn`` as renderer ``name`` supporting ``modes``
    (a set/iterable of "series" / "events")."""
    modes = frozenset(modes)
    if not modes <= {"series", "events"}:
        raise ValueError(f"invalid modes {set(modes)!r} for renderer {name!r}")

    def deco(fn: Renderer) -> Renderer:
        if name in _REGISTRY:
            raise ValueError(f"renderer {name!r} already registered")
        _REGISTRY[name] = {"fn": fn, "modes": modes}
        return fn
    return deco


def get(name: str) -> Renderer:
    try:
        return _REGISTRY[name]["fn"]
    except KeyError as e:
        raise KeyError(f"unknown renderer {name!r}; available: {sorted(_REGISTRY)}") from e


def modes_for(name: str) -> frozenset:
    try:
        return _REGISTRY[name]["modes"]
    except KeyError as e:
        raise KeyError(f"unknown renderer {name!r}; available: {sorted(_REGISTRY)}") from e


def available(mode: str | None = None) -> list[str]:
    if mode is None:
        return sorted(_REGISTRY)
    return sorted(n for n, v in _REGISTRY.items() if mode in v["modes"])


# Import side-effect: register built-in renderers.
from . import chart, data, terminal  # noqa: E402,F401
```

- [ ] **Step 4: Update the three existing renderers' registration calls so imports succeed**

In each existing renderer, add `modes=...` to the decorator (bodies are migrated in Task 7; this is only to satisfy the new `register` signature). Make exactly these edits:

`src/moonphase/renderers/chart.py` — change `@register("chart")` to:
```python
@register("chart", modes={"series", "events"})
```

`src/moonphase/renderers/data.py` — change `@register("csv")` to `@register("csv", modes={"series", "events"})` and `@register("json")` to `@register("json", modes={"series", "events"})`.

`src/moonphase/renderers/terminal.py` — change `@register("terminal")` to:
```python
@register("terminal", modes={"series", "events"})
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_registry.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/renderers/__init__.py src/moonphase/renderers/chart.py src/moonphase/renderers/data.py src/moonphase/renderers/terminal.py tests/test_registry.py
git commit -m "feat: mode-declaring renderer registry (register/modes_for/available)"
```

---

## Task 6: `resolve_mode` helper

**Files:**
- Modify: `src/moonphase/cli.py` (add a pure helper near the top)
- Test: `tests/test_cli.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import pytest

from moonphase.cli import resolve_mode


def fake_modes_for(name):
    return {
        "chart": frozenset({"series", "events"}),
        "almanac": frozenset({"events"}),
        "heatmap": frozenset({"series"}),
    }[name]


def test_single_mode_format_auto_resolves():
    assert resolve_mode("almanac", None, fake_modes_for) == "events"
    assert resolve_mode("heatmap", None, fake_modes_for) == "series"


def test_multi_mode_format_defaults_to_series():
    assert resolve_mode("chart", None, fake_modes_for) == "series"


def test_explicit_compatible_mode_kept():
    assert resolve_mode("chart", "events", fake_modes_for) == "events"


def test_incompatible_mode_raises_with_supported_list():
    with pytest.raises(ValueError) as exc:
        resolve_mode("almanac", "series", fake_modes_for)
    assert "events" in str(exc.value)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_mode'`

- [ ] **Step 3: Add `resolve_mode` to `cli.py`**

In `src/moonphase/cli.py`, add this function directly below the imports (above `_STEP_RE`):

```python
def resolve_mode(fmt, requested, modes_for):
    """Resolve the effective render mode for ``fmt``.

    ``requested`` is the user's --mode (or None). ``modes_for(fmt)`` returns
    the set of modes the format supports. Single-mode formats auto-resolve;
    multi-mode formats default to "series"; an incompatible explicit mode
    raises ValueError listing the supported modes.
    """
    supported = modes_for(fmt)
    if requested is None:
        if len(supported) == 1:
            return next(iter(supported))
        return "series"
    if requested not in supported:
        raise ValueError(
            f"format {fmt!r} supports mode(s): {', '.join(sorted(supported))}"
        )
    return requested
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat: resolve_mode helper for --mode auto-resolution and validation"
```

---

## Task 7: Migrate renderers + CLI to the `Report` interface

This is the interface migration: the three renderers switch to `render(report, out)` and the CLI builds a `Report` and dispatches with it. They change together because the call site and the callees share the signature.

**Files:**
- Modify: `src/moonphase/renderers/data.py`
- Modify: `src/moonphase/renderers/terminal.py`
- Modify: `src/moonphase/renderers/chart.py`
- Modify: `src/moonphase/cli.py`
- Modify: `src/moonphase/__init__.py`
- Test: `tests/test_renderers.py` (create)

- [ ] **Step 1: Write the failing renderer tests (hand-built Reports, no ephemeris)**

Create `tests/test_renderers.py`:

```python
import csv as csvmod
import json
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")

from moonphase import renderers
from moonphase.calendar import PhaseSample
from moonphase.events import PhaseEvent
from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report

S4 = MicrophaseScheme.from_divisions(4)
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _series_report():
    samples = [
        PhaseSample(when=T0, angle_deg=0.0, microphase=0),
        PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0),
    ]
    return Report(scheme=S4, mode="series", samples=samples)


def _events_report():
    events = [
        PhaseEvent(when=T0, angle_deg=0.0, kind="center", index=0, name="New"),
        PhaseEvent(when=T0.replace(hour=6), angle_deg=45.0, kind="transition",
                   index=0, name=None),
    ]
    return Report(scheme=S4, mode="events", events=events)


def test_csv_series(tmp_path):
    out = tmp_path / "s.csv"
    renderers.get("csv")(_series_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[0] == ["time", "phase_angle_deg", "microphase_index", "divisions", "step_deg"]
    assert rows[1][2] == "0"


def test_csv_events(tmp_path):
    out = tmp_path / "e.csv"
    renderers.get("csv")(_events_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[0] == ["time", "target_angle_deg", "kind", "microphase_index", "name", "divisions", "step_deg"]
    assert rows[1][2] == "center" and rows[1][4] == "New"
    assert rows[2][2] == "transition"


def test_json_events(tmp_path):
    out = tmp_path / "e.json"
    renderers.get("json")(_events_report(), str(out))
    payload = json.load(out.open())
    assert payload["scheme"]["divisions"] == 4
    assert payload["events"][0]["kind"] == "center"
    assert "samples" not in payload


def test_terminal_events(tmp_path):
    out = tmp_path / "e.txt"
    renderers.get("terminal")(_events_report(), str(out))
    text = out.read_text()
    assert "center" in text and "New" in text


def test_chart_series_writes_png(tmp_path):
    out = tmp_path / "c.png"
    renderers.get("chart")(_series_report(), str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_renderers.py -v`
Expected: FAIL — current renderers take `(samples, scheme, out)`, so calling with `(report, out)` raises `TypeError`.

- [ ] **Step 3: Rewrite `data.py`**

Replace the entire contents of `src/moonphase/renderers/data.py` with:

```python
"""CSV and JSON renderers (series rows or event rows)."""

from __future__ import annotations

import csv
import json
import sys

from . import register


@register("csv", modes={"series", "events"})
def render_csv(report, out):
    f = open(out, "w", newline="") if out else sys.stdout
    s = report.scheme
    try:
        w = csv.writer(f)
        if report.mode == "events":
            w.writerow(["time", "target_angle_deg", "kind", "microphase_index",
                        "name", "divisions", "step_deg"])
            for e in report.events or []:
                w.writerow([e.when.isoformat(), f"{e.angle_deg:.6f}", e.kind,
                            e.index, e.name or "", s.divisions, f"{s.step_deg:.6f}"])
        else:
            w.writerow(["time", "phase_angle_deg", "microphase_index",
                        "divisions", "step_deg"])
            for p in report.samples or []:
                w.writerow([p.when.isoformat(), f"{p.angle_deg:.6f}", p.microphase,
                            s.divisions, f"{s.step_deg:.6f}"])
    finally:
        if out:
            f.close()


@register("json", modes={"series", "events"})
def render_json(report, out):
    s = report.scheme
    payload = {"scheme": {"divisions": s.divisions, "step_deg": s.step_deg}}
    if report.mode == "events":
        payload["events"] = [
            {"time": e.when.isoformat(), "angle_deg": e.angle_deg, "kind": e.kind,
             "index": e.index, "name": e.name}
            for e in report.events or []
        ]
    else:
        payload["samples"] = [
            {"time": p.when.isoformat(), "angle_deg": p.angle_deg, "microphase": p.microphase}
            for p in report.samples or []
        ]
    if out:
        with open(out, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
```

- [ ] **Step 4: Rewrite `terminal.py`**

Replace the entire contents of `src/moonphase/renderers/terminal.py` with:

```python
"""Terminal view: a per-day glyph grid (series) or an event list (events)."""

from __future__ import annotations

import sys
from collections import defaultdict

from . import register

_GLYPHS = "🌑🌒🌓🌔🌕🌖🌗🌘"


def _glyph(idx: int, divisions: int) -> str:
    return _GLYPHS[int((idx / divisions) * len(_GLYPHS)) % len(_GLYPHS)]


@register("terminal", modes={"series", "events"})
def render(report, out):
    f = open(out, "w") if out else sys.stdout
    s = report.scheme
    try:
        if report.mode == "events":
            f.write(f"# {s.divisions} microphases, {s.step_deg:.3f}° per slice\n")
            for e in report.events or []:
                label = e.name or f"#{e.index}"
                f.write(f"{e.when.isoformat()}  {e.kind:10} {e.angle_deg:7.3f}°  {label}\n")
        else:
            by_day: dict[str, list] = defaultdict(list)
            for p in report.samples or []:
                by_day[p.when.date().isoformat()].append(p)
            f.write(f"# {s.divisions} microphases, {s.step_deg:.3f}° per slice\n")
            for day in sorted(by_day):
                row = "".join(_glyph(p.microphase, s.divisions) for p in by_day[day])
                f.write(f"{day}  {row}\n")
    finally:
        if out:
            f.close()
```

- [ ] **Step 5: Rewrite `chart.py`**

Replace the entire contents of `src/moonphase/renderers/chart.py` with:

```python
"""Matplotlib strip-chart: elongation vs time, centered phase bands, named
phases on the left axis, degrees on the right, with exact event overlays."""

from __future__ import annotations

import numpy as np

from ..naming import default_name
from . import register


@register("chart", modes={"series", "events"})
def render(report, out):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    s = report.scheme
    step = s.step_deg
    fig, ax = plt.subplots(figsize=(12, 3.5))

    sc = None
    if report.mode == "series":
        samples = report.samples or []
        if not samples:
            raise ValueError("no samples to render")
        times = [p.when for p in samples]
        angles = np.array([p.angle_deg for p in samples])
        sc = ax.scatter(times, angles, c=angles, cmap="twilight", s=4, marker="s")

    # centered phase bands (band k spans (k-0.5)..(k+0.5)*step; band 0 wraps)
    for k in range(0, s.divisions, 2):
        lo, hi = (k - 0.5) * step, (k + 0.5) * step
        if lo < 0:
            ax.axhspan(0, hi, color="black", alpha=0.04)
            ax.axhspan(360 + lo, 360, color="black", alpha=0.04)
        else:
            ax.axhspan(lo, hi, color="black", alpha=0.04)

    # event overlays: solid = centers, dashed orange = transitions
    for e in report.events or []:
        ax.axvline(e.when, color=("#d98324" if e.kind == "transition" else "#5b6b8a"),
                   lw=0.6, ls=("--" if e.kind == "transition" else "-"), alpha=0.7)

    ax.set_ylim(0, 360)
    # degrees on the right
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_yticks([0, 90, 180, 270, 360])
    ax.set_ylabel("Sun–Moon elongation (°)")
    # named phase centers on the left
    axL = ax.secondary_yaxis("left")
    axL.set_yticks([(k * step) % 360 for k in range(s.divisions)])
    axL.set_yticklabels([default_name(k, s) or f"{(k * step) % 360:.0f}°"
                         for k in range(s.divisions)])

    ax.set_title(f"Lunar microphases — {s.divisions} divisions ({step:.3f}° each)")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    if sc is not None:
        fig.colorbar(sc, ax=ax, label="phase angle", pad=0.08)
    fig.tight_layout()

    if out:
        fig.savefig(out, dpi=150)
    else:
        plt.show()
    plt.close(fig)
```

- [ ] **Step 6: Update `cli.py` `build_parser` and `main`**

In `src/moonphase/cli.py`, in `build_parser()` add these two arguments (immediately after the `--sample` argument):

```python
    p.add_argument("--mode", choices=["series", "events"], default=None,
                   help="output mode; auto-resolved from --format when omitted")
    p.add_argument("--transitions", action="store_true",
                   help="include transition points (overlays in series; rows in events)")
```

Replace the body of `main()` with:

```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    scheme = (MicrophaseScheme.from_divisions(args.divisions)
              if args.divisions is not None
              else MicrophaseScheme.from_step(args.step))

    try:
        mode = resolve_mode(args.format, args.mode, renderers.modes_for)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    eph = PhaseEphemeris(kernel_path=args.ephemeris)

    if mode == "events":
        events = build_events(args.start, args.end, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="events", events=events)
    else:
        samples = build_series(args.start, args.end, scheme,
                               sample_step=args.sample, ephemeris=eph)
        # series-mode events: phase centers always, transitions when requested
        events = build_events(args.start, args.end, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="series", samples=samples, events=events)

    renderers.get(args.format)(report, args.out)
    return 0
```

Add the needed imports at the top of `cli.py` (alongside the existing imports):

```python
from .events import build_events
from .report import Report
```

- [ ] **Step 7: Export new names from the package**

Replace the contents of `src/moonphase/__init__.py` with:

```python
"""moonphase: arbitrary microphase divisions of the lunar synodic cycle."""

from .microphase import MicrophaseScheme, phase_to_index
from .ephemeris import PhaseEphemeris
from .calendar import build_series, PhaseSample
from .events import PhaseEvent, build_events
from .report import Report

__all__ = [
    "MicrophaseScheme",
    "PhaseEphemeris",
    "PhaseSample",
    "PhaseEvent",
    "Report",
    "build_series",
    "build_events",
    "phase_to_index",
]
__version__ = "0.1.0"
```

- [ ] **Step 8: Run the renderer tests and the full suite**

Run: `pytest tests/test_renderers.py -v`
Expected: PASS (5 tests)

Run: `pytest -q`
Expected: all tests pass (microphase, naming, events, report, registry, cli, renderers).

- [ ] **Step 9: Commit**

```bash
git add src/moonphase/renderers/data.py src/moonphase/renderers/terminal.py src/moonphase/renderers/chart.py src/moonphase/cli.py src/moonphase/__init__.py tests/test_renderers.py
git commit -m "feat: migrate renderers and CLI to Report interface with --mode/--transitions"
```

---

## Task 8: CLI integration test + lint + final verification

**Files:**
- Modify: `tests/test_cli.py` (add a `main`-level integration test with a fake ephemeris)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_cli.py`:

```python
import numpy as np

import moonphase.cli as cli_mod


class _LinearEph:
    def __init__(self, *a, **k):
        from datetime import datetime, timezone
        self._t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def phase_angles_deg(self, times):
        return np.array([
            (12.0 * (t - self._t0).total_seconds() / 86400.0) % 360.0 for t in times
        ], dtype=float)


def test_main_events_mode_writes_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "events.csv"
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-31",
        "--divisions", "4", "--mode", "events", "--transitions",
        "--format", "csv", "--out", str(out),
    ])
    assert rc == 0
    text = out.read_text()
    assert "kind" in text.splitlines()[0]
    assert "transition" in text and "center" in text


def test_main_rejects_incompatible_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    # csv supports both modes, so force a single-mode mismatch via chart? chart is
    # multi-mode too; use a guaranteed events-only check by monkeypatching modes_for.
    monkeypatch.setattr(cli_mod.renderers, "modes_for", lambda n: frozenset({"events"}))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-02",
        "--divisions", "4", "--mode", "series", "--format", "csv",
    ])
    assert rc == 2
    assert "supports mode(s): events" in capsys.readouterr().err
```

- [ ] **Step 2: Run the integration test to verify it fails, then passes**

Run: `pytest tests/test_cli.py -v`
Expected: initially FAIL only if a wiring bug exists; with Task 7 complete it should PASS. If it fails, fix the wiring in `cli.py` (do not modify the test).

- [ ] **Step 3: Lint**

Run: `ruff check src tests`
Expected: no errors. Fix any reported issues (unused imports, line length > 100).

- [ ] **Step 4: Full suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: CLI main integration for events mode and mode mismatch"
```

---

## Self-review notes (for the implementer)

- **Spec coverage (Phase 1 subset):** Task 1 → §5.1 F1.3; Tasks 2 → names; Task 3 → §5.3b F3b.1–F3b.2; Tasks 4–5 → §5.6 F6.1–F6.2 + §8 `Report`; Task 6 → §5.5 F5.4 mode resolution; Task 7 → §5.6 F6.3 renderer refit + §5.5 F5.3 `--mode`/`--transitions`; Task 8 → §5.5 F5.5 exit codes.
- **Deferred on purpose (not gaps):** time handling / captions (§5.4, F6.4) = Phase 2; `heatmap`/`almanac`/lunar (§5.6) = Phase 3; `--labels`/`--tint` = Phase 4. `Report.tz`/`Report.labels` exist with defaults so later phases don't churn the dataclass.
- **Type consistency:** `PhaseEvent(when, angle_deg, kind, index, name)` is used identically in `events.py`, `report.py`, `data.py`, `terminal.py`, `chart.py`, and all tests. `Report(scheme, mode, samples, events, tz, labels)` field names match across `report.py`, `cli.py`, renderers, and tests. Registry API (`register(name, modes)`, `get`, `modes_for`, `available(mode)`) is consistent between `__init__.py`, `cli.py`, and `test_registry.py`.
- **Ephemeris testability:** `build_events` depends only on `phase_angles_deg`; every test injects a synthetic linear ephemeris, so the full suite runs offline (no DE421 download). A real-kernel integration test is a Phase-2+ addition once an offline fixture exists (consistent with the repo's existing deferral).
