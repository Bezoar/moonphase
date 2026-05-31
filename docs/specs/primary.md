# moonphase — Specification

Status: **production**
Owner: Mark Welch
Last revised: 2026-05-29 (rev 2 — centered phases, exact events, transition points, chart designs)

> Rev 2 integrates the spec-refinement design brainstormed on 2026-05-29
> (`docs/superpowers/specs/2026-05-29-spec-refinement-design.md`). Visual reference for the
> renderers: the [sample gallery](../../samples/README.md); the original design mockup is
> archived at `docs/archive/mockups-2026-05-29.png`.

## 1. Purpose

`moonphase` is a standalone Python tool that computes **microphases** of the Moon — user-defined,
arbitrarily fine subdivisions of the synodic cycle — and emits them across a date range of any
length, in multiple output formats. It serves both casual calendar use ("show me 32-step moon
phases for 2026") and analytical use ("give me 1-degree-resolution phase angle as CSV for the
next decade", "the exact UTC instant of every full moon").

## 2. Goals

- **G1** Compute the lunar phase angle (Sun–Moon ecliptic longitude difference, mod 360°) at
  arbitrary UTC instants with sub-arcminute accuracy.
- **G2** Partition the 360° synodic cycle into N equal microphases **centered on** `k·step`,
  where N is user-specified either directly (`--divisions N`) or via angular step (`--step Xdeg`).
- **G3** Generate a time-indexed **series** of microphase samples across a `[start, end]` range
  at a configurable cadence.
- **G4** Identify **exact events** — root-found UTC instants of every phase center and (optionally)
  transition point — to the precision of the ephemeris, independent of sampling cadence.
- **G5** Emit series and events through a **pluggable renderer registry** so new output formats
  (PDF, HTML, ICS, …) can be added without changing the calendar, events, or CLI core.
- **G6** Ship as an installable package with a `moonphase` console script and a stable public API.
- **G7** Be runnable fully offline once the ephemeris kernel is cached.

## 3. Non-goals (for v0.x)

- Rise/set/transit times, eclipses, lunar libration, or distance/angular-size (supermoon) metrics.
- Observer-location features; UTC + a single display timezone only.
- GUI, web app, or interactive notebook widget.
- Sub-second timing for occultations.
- Phases of bodies other than the Moon.

## 4. Definitions

- **Synodic cycle**: the ~29.53-day Sun→Moon→Sun cycle as seen from Earth, parameterized by
  phase angle ∈ [0°, 360°).
- **Phase angle**: `(λ_moon − λ_sun) mod 360°`, apparent geocentric ecliptic longitudes in the
  ecliptic-of-date frame. 0° = new, 90° = first quarter, 180° = full, 270° = last quarter.
- **Microphase (phase)**: one of N equal angular arcs, **centered on** its phase center. Arc `k`
  covers `[(k−½)·step, (k+½)·step)` where `step = 360°/N`. "Phase" and "microphase" are synonyms;
  "microphase" emphasizes arbitrary N. For N=4 the microphases are the classical phases.
- **Phase center**: the angle `k·step` — the exact peak instant of microphase `k` (New/Full/… for
  N=4). The "identify as precisely as possible" targets.
- **Transition point**: the angle `(k+½)·step` — the boundary between two adjacent microphase
  arcs. A separately-labeled category, **not** a finer division.
- **Sample**: a tuple `(utc_time, phase_angle_deg, microphase_index)` produced by fixed-cadence
  sampling.
- **Series**: an ordered list of samples spanning a date range at a fixed cadence.
- **Event**: a root-found `(utc_time, target_angle, kind, index, name)` where `kind` ∈
  {`center`, `transition`}.
- **Lunation**: one synodic month, delimited by consecutive new moons (or full moons).

## 5. Functional requirements

### 5.1 Microphase scheme
- **F1.1** `MicrophaseScheme.from_divisions(N)` accepts any integer N ≥ 1.
- **F1.2** `MicrophaseScheme.from_step(step_deg)` accepts any float in (0, 360]; non-integer
  divisors produce a final short arc (`divisions = ceil(360/step)`).
- **F1.3** `phase_to_index(angle, scheme)` maps an angle to its **centered** microphase via
  round-half-up: `int(angle/step + 0.5) mod divisions` (angle pre-normalized to `[0,360)`).
  `k·step` is the *center* of arc `k`; exact transition boundaries assign deterministically to the
  higher-index arc (unlike banker's `round`). The index is a label only — full angular precision
  lives in the sample's `angle_deg` and in events (§5.3b).

### 5.2 Ephemeris
- **F2.1** Default kernel: JPL **DE421**, fetched by Skyfield's `Loader` into `./data/` (or a
  user path) on first use.
- **F2.2** `--ephemeris path/to/kernel.bsp` overrides the default; documented bundling mechanism.
- **F2.3** Phase angle uses apparent geocentric positions in Skyfield's `ecliptic_frame`.

### 5.3 Calendar series
- **F3.1** `build_series(start, end, scheme, sample_step, ephemeris)` returns a list of
  `PhaseSample` from `start` to `end` inclusive at `sample_step` cadence.
- **F3.2** Cadence default 1 h; min 1 s; max 1 day (soft).
- **F3.3** Memory: one `(datetime, float, int)` per sample.

### 5.3b Exact events
- **F3b.1** `build_events(start, end, scheme, ephemeris, transitions=False)` returns chronological
  `PhaseEvent`s with sub-second UTC instants, root-found via Skyfield's `almanac.find_discrete`. The reference implementation locates crossings with an injectable bisection root-finder over ``phase_angles_deg`` (equivalent observable contract to ``find_discrete``, chosen so event-finding is unit-testable offline); events mode requires a step that divides 360 evenly.
- **F3b.2** With `transitions=False`, the discrete function is `floor(angle/step)`; each change is
  a **phase-center** crossing. With `transitions=True`, the function is `floor(angle/(step/2))`;
  even multiples are labeled `center`, odd multiples `transition`. The half-step is an internal
  computational device only — output never treats results as `2N` microphases.
- **F3b.3** The discrete-scan step (`find_discrete` `step_days`) must be smaller than the minimum
  target spacing (Moon advances ~12.2°/day); runtime grows with N. This is documented.

### 5.4 Time handling *(implemented in Phase 2)*
- **F4t.1** A single **display timezone** is resolved per run, in priority order: (1) explicit
  offset on `--start` (full ISO 8601), (2) discernible system-local timezone, (3) UTC.
- **F4t.2** Bare dates / naive datetimes are interpreted in the display timezone (→ local midnight
  on a normal machine, not UTC).
- **F4t.3** All computation is in UTC/TT internally. Output timestamps are rendered in the display
  timezone, emitted as ISO 8601 **with offset**; conversions are DST-aware per instant via
  `datetime.astimezone()` (no extra dependency). Terminal/heatmap group by display-tz calendar
  days.
- **F4t.4** Every time-bearing render states its timezone explicitly (see F5.x captions).

### 5.5 CLI
- **F5.1** Entry points: `moonphase` console script and `python -m moonphase.cli`.
- **F5.2** Required: `--start`, `--end`, and exactly one of `--divisions` / `--step`.
- **F5.3** Optional flags:
  - `--mode {series,events}` — auto-resolved from the format when omitted (single-mode format →
    its mode; multi-mode format → `series`).
  - `--transitions` — include transition points (overlay markers in series; rows in events).
  - `--theme {dark,light}` — color theme for the visual renderers (`chart`/`heatmap`/`almanac`);
    default `dark`. *(implemented in issue #7)*
  - `--tint {illumination,index}` — **heatmap only**; default `illumination`.
  - `--calendar {gregorian,lunar}` — **heatmap layout**; default `gregorian`.
  - `--lunar-anchor {new,full}` — default `new`; only meaningful with `--calendar lunar`.
  - `--size WIDTHxHEIGHT` — output image size in pixels (width first, e.g. `5000x3000`); a
    general override honored by the heatmap renderer. If an explicit `--size` is smaller than
    the computed minimum (see `--cell-times`), the renderer raises an error.
  - `--cell-times` — **heatmap only**, requires `--calendar gregorian`. Prints, inside each
    day cell, the local time(s) of phase **peaks** (centers) as bare `LABEL HH:MM`; with
    `--transitions`, also the **transition into** a phase as `→LABEL HH:MM`. LABEL is the
    `--labels` value for that microphase or the bare microphase index. A peak's microphase is
    the center's own index; the microphase *entered* by a transition is
    `(transition_index + 1) mod divisions`. Both kinds are merged and sorted by time within a
    cell. The figure is auto-sized from the labels at a 9 pt minimum font size. A day with more
    than 4 events collapses to an `N×` badge.
  - `--font NAME|PATH` — font family name (e.g. `Helvetica`) or a path to a `.ttf`/`.otf`
    file; applied to all heatmap text.
  - `--labels SPEC` — custom microphase names: inline comma list or `@file` (one per line, or JSON
    `index→name`), **sparse-merge** (blank/missing → built-in for N∈{4,8}, else index/angle).
    *(implemented in Phase 4)*
  - `--sample DUR` — cadence; **series mode only**, ignored in events mode (documented).
  - `--format NAME` — renderer; choices populated dynamically from the registry, filtered by mode.
  - `--out PATH` — output path; format inferred from extension where applicable.
  - `--ephemeris PATH.bsp` — kernel override.
- **F5.4** `--mode` given but incompatible with `--format` → single-line error listing the
  format's compatible modes (e.g. `error: format 'almanac' supports mode(s): events`).
- **F5.5** Exit 0 on success; non-zero on validation/runtime error with a single-line stderr msg.
- **F5.6** Validation order: argparse (dates, exactly-one divisions/step, format registered) →
  resolve & check mode → `start ≤ end`, `divisions ≥ 1` / `step ∈ (0,360]`, resolve labels & tz.

### 5.6 Renderers
> `chart`/`csv`/`json`/`terminal` shipped in Phase 1; `heatmap`, `almanac`, `--tint`, and
> `--calendar`/`--lunar-anchor` implemented in Phase 3 (renderer-specific flags travel on
> `Report.options`). `--calendar`/`--lunar-anchor` currently apply to `heatmap` only; lunar
> layouts for `chart`/`csv`/`terminal` are a possible future enhancement.

- **F6.1** A renderer is `render(report, out) -> None` where `report` is a frozen `Report`
  (scheme, mode, samples|None, events|None, tz, labels|None, options|None).
- **F6.2** Registration `@register(name, modes={...})`; name collisions raise; `available(mode)`
  filters by supported mode.
- **F6.3** Built-in renderers:
  - `chart` (series, events) — analytic strip-chart; elongation 0–360° on the Y axis with **named
    phases on the left, degrees on the right**; a readable date axis; centered phase bands;
    solid phase-center lines, dashed transition lines; phase-angle sawtooth with event overlays
    (filled dots = centers, orange rings = transitions). File format from `--out` extension
    (png/svg/pdf/…). *(`--calendar` is not consumed by `chart`.)*
  - `heatmap` (series) — calendar grid. `--tint illumination` (grayscale by illuminated fraction)
    or `--tint index` (distinct hue per microphase). `--calendar gregorian` → months × days, day
    cells marked with moon-disk glyphs on a dark backing chip at principal-phase days.
    `--calendar lunar` → one phase-aligned strip per lunation, annotated with Gregorian start
    (left), end (right), and mid/opposite-phase date (below center). `--cell-times`
    (gregorian only) prints phase-peak times — and, with `--transitions`, transition-into-phase
    times prefixed `→` — inside each day cell in low-contrast text; figure is auto-sized from
    labels at a 9 pt minimum; `--size` overrides; `--font` restyled text.
  - `almanac` (events) — moon-disk ribbon at exact phase centers with name + date + time;
    transition points dashed between (when `--transitions`). Correct lit-limb geometry with
    degenerate-fraction handling (New empty, Full solid).
  - `csv` (series, events) — series rows or event rows; ISO 8601 timestamps with offset (column
    `time`); scheme params.
  - `json` (series, events) — `{scheme, timezone, samples|events: [...]}`.
  - `terminal` (series, events) — glyph grid (one row per day) or an event list; header states
    the timezone.
- **F6.4** Every renderer that shows times emits a mandatory timezone caption (zone name for
  local/DST zones, fixed offset / UTC otherwise; notes mid-range DST changes).
- **F6.5** Adding a renderer is a single-file change: new module, `render(report, out)`,
  `@register(name, modes=…)`, one import line in `renderers/__init__.py`.

## 6. Non-functional requirements

- **N1** Python ≥ 3.10, pure-Python source.
- **N2** Hard deps: `skyfield`, `numpy`, `matplotlib`. No optional groups beyond `dev`.
- **N3** Cold-import time (no kernel load) under 500 ms — Skyfield/matplotlib stay lazily imported.
- **N4** Repository under 10 MB excluding the ephemeris kernel (raised from 1 MB to allow a
  committed `samples/` gallery of rendered charts).
- **N5** MIT-licensed; permissive, no copyleft obligations on downstream users.
- **N6** Determinism: identical invocations on the same kernel produce byte-identical output
  **when a timezone is pinned** (explicit `--start` offset / UTC). With local-tz resolution,
  output depends on the host timezone — documented; CI/reproducible runs should pin an offset.

## 7. Architecture

```
            ┌────────────────────┐
   CLI ────▶│  argparse + flags  │  (mode resolution, tz resolution, labels)
            └─────────┬──────────┘
                      │
          ┌───────────┴────────────┐
          ▼                        ▼
  ┌────────────────┐      ┌────────────────┐     ┌─────────────────────┐
  │ build_series() │      │ build_events() │◀───▶│   PhaseEphemeris    │
  │ (calendar.py)  │      │  (events.py)   │     │   (Skyfield+DE421)  │
  └───────┬────────┘      └───────┬────────┘     └─────────────────────┘
          │ samples               │ events
          └───────────┬───────────┘
                      ▼
            ┌────────────────────┐
            │   Report (frozen)  │  scheme · mode · samples? · events? · tz · labels?
            └─────────┬──────────┘
                      ▼
            ┌────────────────────┐
            │ renderers.get(fmt) │ ── chart / heatmap / almanac / csv / json / terminal / …
            └────────────────────┘
```

Data flow is one-way; renderers are leaves consuming a `Report`. The registry is the only
extensibility seam.

## 8. Public API surface

```python
from moonphase import (
    MicrophaseScheme,    # .from_divisions / .from_step
    PhaseEphemeris,      # (kernel_path=None, data_dir="data")
    PhaseSample,         # (when, angle_deg, microphase)
    PhaseEvent,          # (when, angle_deg, kind, index, name)
    Report,              # (scheme, mode, samples, events, tz, labels, options)
    build_series,        # (start, end, scheme, sample_step, ephemeris) -> [PhaseSample]
    build_events,        # (start, end, scheme, ephemeris, transitions=False) -> [PhaseEvent]
    phase_to_index,      # (phase_deg, scheme) -> int   (centered, round-half-up)
)
from moonphase import renderers
renderers.register("name", modes={"series", "events"})(fn)   # fn(report, out)
renderers.get("name")(report, out)
renderers.available(mode=None) -> list[str]
```

The v0.1 `render(samples, scheme, out)` signature is superseded by `render(report, out)` — the one
intentional pre-1.0 breaking change; the registry exists precisely to absorb it.

## 9. Out-of-scope but on the roadmap

- Explicit `--timezone` override (implicit local resolution ships now).
- `--transitions-only` series mode; numpy-vectorized `phase_to_index`.
- ICS renderer (events-native), HTML month-grid renderer.
- `--bundle-ephemeris` wheel variant; PyPI release.
- Accuracy bench vs Meeus/PyEphem.

## 10. Risks & open questions

- **R1** DE421 download size (~17 MB) is a first-run friction point; consider a smaller kernel or
  a wheel variant with the kernel embedded.
- **R2** Matplotlib backend in headless environments — ensure `Agg` when `DISPLAY` is unset.
- **R3** *(resolved)* Non-integer `--step` tail bin and edge assignment — round-half-up makes
  binning deterministic; the short final arc for non-divisors is accepted behavior.
- **R4** Public API freeze timing — wait for at least one external consumer of the renderer
  registry before declaring 1.0.
- **R5** Event-finding cost grows with N (scan step shrinks). Large N + long ranges may be slow;
  document and revisit if it bites.

## 11. Acceptance criteria for v0.x

1. `phase_to_index` is centered: documented edge cases pass on Python 3.10/3.11/3.12, including
   N=16 transition-boundary assignment.
2. `--mode events --divisions 4` yields New/FQ/Full/LQ instants within ±2 h of USNO 2026 dates;
   `--transitions` adds the four 45/135/225/315° crossings as `kind="transition"`.
3. `--format almanac` auto-resolves to events and renders New empty / Full solid;
   `--format almanac --mode series` errors with the compatible-mode list.
4. A bare-date run on a non-UTC host produces local-time output with offsets and a tz caption; the
   same run with `--start …Z` produces UTC output. Captions appear on chart/heatmap/almanac/terminal.
5. `--labels @file` sparse-merge: named gradations appear; unnamed indices fall back.
6. `heatmap --tint index` shows discrete hue bands; `--calendar lunar` lays out one dated,
   phase-aligned strip per lunation.
7. Adding a renderer requires a single new file plus one import; no edits to CLI/calendar/events.
