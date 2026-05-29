# moonphase — Preliminary Specification

Status: **draft**
Owner: project author
Last revised: 2026-05-29

## 1. Purpose

`moonphase` is a standalone Python tool that computes **microphases** of the
Moon — user-defined, arbitrarily fine subdivisions of the synodic cycle —
and emits them across a date range of any length, in multiple output
formats. It is intended for both casual calendar use ("show me 32-step
moon phases for 2026") and analytical use ("give me 1-degree-resolution
phase angle as CSV for the next decade").

## 2. Goals

- **G1** Compute the lunar phase angle (Sun–Moon ecliptic longitude
  difference, mod 360°) at arbitrary UTC instants with sub-arcminute
  accuracy.
- **G2** Partition the 360° synodic cycle into N equal microphases, where
  N is user-specified either directly (`--divisions N`) or implicitly via
  angular step (`--step Xdeg`).
- **G3** Generate a time-indexed series of microphase samples across a
  user-supplied `[start, end]` date range at a configurable cadence.
- **G4** Emit the series through a **pluggable renderer registry** so that
  new output formats (PDF, HTML, ICS, ...) can be added without changing
  the calendar or CLI core.
- **G5** Ship as an installable Python package with a `moonphase` console
  script and a stable public API (`build_series`, `MicrophaseScheme`,
  `PhaseEphemeris`).
- **G6** Be runnable fully offline once the ephemeris kernel is cached.

## 3. Non-goals (for v0.x)

- Rise/set/transit times, eclipses, lunar libration analysis.
- Local-time / observer-location features beyond UTC sampling.
- GUI, web app, or interactive notebook widget.
- Sub-second timing for occultations (not the use case).
- Phases of bodies other than the Moon.

## 4. Definitions

- **Synodic cycle**: the ~29.53-day Sun→Moon→Sun cycle as seen from
  Earth, parameterized by phase angle ∈ [0°, 360°).
- **Phase angle**: `(λ_moon − λ_sun) mod 360°`, where λ are apparent
  geocentric ecliptic longitudes in the ICRS-aligned ecliptic-of-date
  frame. 0° = new moon; 90° = first quarter; 180° = full; 270° = last
  quarter.
- **Microphase**: one of N equal-width angular bins partitioning
  [0°, 360°). Bin `k` covers `[k·Δ, (k+1)·Δ)` where `Δ = 360°/N`.
- **Sample**: a tuple `(utc_time, phase_angle_deg, microphase_index)`.
- **Series**: an ordered list of samples spanning a date range at a
  fixed cadence.

## 5. Functional requirements

### 5.1 Microphase scheme
- **F1.1** `MicrophaseScheme.from_divisions(N)` accepts any integer N ≥ 1.
- **F1.2** `MicrophaseScheme.from_step(step_deg)` accepts any float in
  (0, 360]; non-integer divisors produce a final short bin (`divisions =
  ceil(360/step)`).
- **F1.3** `phase_to_index(angle, scheme)` is total over ℝ: inputs are
  normalized via mod 360 and clamped to `[0, divisions-1]`.

### 5.2 Ephemeris
- **F2.1** Default kernel: JPL **DE421**, fetched by Skyfield's `Loader`
  into `./data/` (or a path the user provides) on first use.
- **F2.2** `--ephemeris path/to/kernel.bsp` overrides the default and is
  the documented mechanism for bundling.
- **F2.3** Phase angle computation uses apparent geocentric positions in
  the ecliptic frame (Skyfield `ecliptic_frame`), not mean orbital
  elements.

### 5.3 Calendar series
- **F3.1** `build_series(start, end, scheme, sample_step, ephemeris)`
  returns a list of `PhaseSample` from `start` to `end` inclusive at
  `sample_step` cadence.
- **F3.2** Naive datetimes are interpreted as UTC.
- **F3.3** Cadence default: 1 hour. Min: 1 second. Max: 1 day (soft).
- **F3.4** Memory budget: one `(datetime, float, int)` per sample. Year
  at 1h cadence ≈ 8,760 samples → trivial; decade at 1-min cadence ≈
  5.2 M samples → user's problem to chunk.

### 5.4 CLI
- **F4.1** Entry point: `moonphase` (console script) and
  `python -m moonphase.cli`.
- **F4.2** Required flags: `--start`, `--end`, and exactly one of
  `--divisions` / `--step`.
- **F4.3** Optional flags: `--sample` (cadence), `--format` (renderer
  name, default `chart`), `--out` (output path; stdout if omitted where
  applicable), `--ephemeris` (kernel path).
- **F4.4** `--format` choices are populated **dynamically** from the
  renderer registry.
- **F4.5** Exit code 0 on success; non-zero on validation or runtime
  errors with a single-line message to stderr.

### 5.5 Renderers
- **F5.1** Each renderer is a callable
  `render(samples, scheme, out) -> None`.
- **F5.2** Registration via `@renderers.register("name")`; name
  collisions raise.
- **F5.3** Built-in renderers in v0.1:
  - `chart` — matplotlib strip-chart; file format inferred from `--out`
    extension (png, svg, pdf supported out of the box).
  - `csv` — UTC timestamp, angle, microphase index, scheme params.
  - `json` — `{scheme: {...}, samples: [...]}`.
  - `terminal` — one row per day, one glyph per sample, using the 8-step
    Unicode moon set as a gradient cycled by `index % 8`.
- **F5.4** Adding a renderer is a single-file change: import-time
  registration; no edits to CLI, calendar, or other renderers.

## 6. Non-functional requirements

- **N1** Python ≥ 3.10, pure-Python source.
- **N2** Hard dependencies: `skyfield`, `numpy`, `matplotlib`. No
  optional groups beyond `dev`.
- **N3** Cold-import time (no kernel load) under 500 ms on a modern
  laptop.
- **N4** Repository remains under 1 MB excluding the ephemeris kernel.
- **N5** AGPL-3.0-or-later licensed; downstream service operators must offer
  source for modified network deployments.
- **N6** Determinism: identical CLI invocations on the same kernel
  produce byte-identical output.

## 7. Architecture

```
              ┌────────────────────┐
   CLI ──────▶│  argparse + flags  │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐    ┌─────────────────────┐
              │  build_series()    │◀──▶│   PhaseEphemeris    │
              │  (calendar.py)     │    │   (Skyfield+DE421)  │
              └─────────┬──────────┘    └─────────────────────┘
                        │
                        ▼
              ┌────────────────────┐
              │  MicrophaseScheme  │  (microphase.py)
              └─────────┬──────────┘
                        │ list[PhaseSample]
                        ▼
              ┌────────────────────┐
              │  renderers.get()   │  ── chart / csv / json / terminal / ...
              └────────────────────┘
```

Data flow is one-way; renderers are leaves. The registry is the only
extensibility seam.

## 8. Public API surface (frozen for v0.1)

```python
from moonphase import (
    MicrophaseScheme,    # .from_divisions / .from_step
    PhaseEphemeris,      # (kernel_path=None, data_dir="data")
    PhaseSample,         # (when: datetime, angle_deg: float, microphase: int)
    build_series,        # (start, end, scheme, sample_step, ephemeris) -> [PhaseSample]
    phase_to_index,      # (phase_deg, scheme) -> int
)
from moonphase import renderers
renderers.register("name")(fn)
renderers.get("name")(samples, scheme, out)
renderers.available() -> list[str]
```

## 9. Out-of-scope but on the roadmap

- `--timezone` flag so calendars chart in local civil time.
- `--bundle-ephemeris` packaging mode that vendors `de421.bsp` into a
  wheel.
- ICS calendar renderer (one event per microphase transition).
- HTML renderer with a CSS-grid month view.
- Numpy-vectorized `phase_to_index` for million-sample series.
- A small `bench/` harness comparing accuracy against Meeus-only and
  PyEphem implementations.

## 10. Risks & open questions

- **R1** DE421 download size (~17 MB) is a friction point for first-run
  UX; consider an optional `de440s.bsp` (smaller) or shipping a wheel
  variant with the kernel embedded.
- **R2** Matplotlib backend selection in headless environments — we
  should ensure `Agg` is auto-selected when `DISPLAY` is unset.
- **R3** The "non-integer divisions" branch in `from_step` produces a
  short tail bin; should we instead refuse non-divisors and require the
  user to round explicitly?
- **R4** Public API freeze timing — wait until at least one external
  consumer exercises the renderer registry before declaring 1.0.

## 11. Acceptance criteria for v0.1

- All unit tests pass on Python 3.10, 3.11, 3.12.
- `moonphase --start 2026-01-01 --end 2026-12-31 --divisions 4 --out
  chart.png` produces a chart whose Full Moon markers align with USNO
  full-moon dates for 2026 within ±2 hours.
- `moonphase --start ... --step 1deg --format csv` writes a 360-bin
  series with monotonically increasing time and bounded angle ∈ [0,
  360).
- Adding a new renderer (e.g. a one-page HTML view) requires a single
  new file in `src/moonphase/renderers/` and zero edits elsewhere.
