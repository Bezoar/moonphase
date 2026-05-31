# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone Python CLI that computes **microphases** of the Moon — arbitrary equal-angle
subdivisions of the synodic cycle — and emits them across a date range through pluggable
renderers. "Microphase" = one of N equal bins partitioning Sun–Moon elongation [0°, 360°).
The standard four phases are just `--divisions 4`.

The formal spec is `docs/specs/primary.md`; design rationale, rejected alternatives, and
gotchas are in `docs/notes.md`. Read those before non-trivial changes — they record *why*
the structure is the way it is.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q                                   # full suite
pytest tests/test_microphase.py::test_wrap_around   # single test
ruff check src tests                        # lint (line-length 100, py310 target)

# Run the CLI (also: python -m moonphase.cli)
moonphase --start 2026-01-01 --end 2026-12-31 --divisions 32 --out chart.png
moonphase --start 2026-01-01 --end 2026-01-31 --step 1deg --format csv --out jan.csv
moonphase --start 2026-01-01 --end 2026-01-31 --divisions 8 --format terminal
```

Note: `pytest` (115 tests) covers the microphase math, event root-finding, the renderers,
the CLI, labels, theming, and timezone handling — all **offline via a synthetic linear
ephemeris** (no kernel download). What's still *not* validated in CI is real Skyfield/DE421
ephemeris accuracy (no committed kernel fixture), so a green run doesn't confirm astronomical
correctness against USNO. The committed `samples/` gallery is rendered from the real DE421
kernel and serves as the manual end-to-end check.

## Architecture

One-way pipeline; renderers are leaves. The renderer registry is the only extensibility seam.

```
cli.py (argparse) → build_series() ←→ PhaseEphemeris (Skyfield+DE421)
                          ↓
                    phase_to_index() bucketing (MicrophaseScheme)
                          ↓ list[PhaseSample]
                    renderers.get(name) → chart / csv / json / terminal
```

- `microphase.py` — `MicrophaseScheme` (`from_divisions` / `from_step`) + `phase_to_index`.
  Pure math, no heavy deps; importable on its own.
- `ephemeris.py` — `PhaseEphemeris`: phase angle = `(λ_moon − λ_sun) mod 360°` from apparent
  geocentric ecliptic longitudes (Skyfield `ecliptic_frame`). We work in **degrees of
  elongation**, never illuminated fraction (fraction is non-monotonic and would force every
  bucketing scheme to disambiguate waxing/waning). 0° = new, 90° = first quarter, 180° = full.
- `calendar.py` — `build_series` + `PhaseSample(when, angle_deg, microphase)`. Fixed-cadence
  sampling (not one-row-per-transition).
- `renderers/` — registry in `__init__.py`; built-ins registered via import side-effect at
  the bottom of that file.

### Adding a renderer

1. Create `src/moonphase/renderers/<name>.py` with `render(samples, scheme, out) -> None`.
2. Decorate it `@register("<cli-name>")`.
3. Add a one-line `from . import <name>` to `renderers/__init__.py`.

No edits to CLI or calendar — `--format` choices are populated dynamically from
`renderers.available()`. This is the acceptance test in the spec (§11): a new renderer is a
single new file plus that one import.

## Invariants — do not break these

- **Skyfield is lazy-imported inside `PhaseEphemeris.__init__`**, and **matplotlib inside
  `chart.render()`**. This keeps `__init__.py` / `--help` importable without those deps and
  keeps cold-import under the spec's 500 ms budget. Don't hoist these to module top-level.
- **Timezone normalization lives only in `build_series`** (naive → UTC). Don't add `tzinfo`
  defaulting inside `PhaseEphemeris`; one place avoids drift.
- **Never memoize phase angles in `PhaseEphemeris`** — callers may pass millions of distinct
  timestamps; a dict cache would silently OOM.
- `phase_to_index` is total over ℝ (mod 360 then clamp). Mind that `360.0 % 360.0 == 0.0`;
  the `idx >= divisions` clamp is the defensive guard for float pathology near 360°.

## Ephemeris kernel

Default JPL **DE421** (~17 MB) is downloaded by Skyfield's `Loader` into `./data/` on first
`PhaseEphemeris()` instantiation — never at import. `*.bsp` is gitignored. Override with
`--ephemeris path/to/kernel.bsp` (the documented bundling mechanism).

## License

MIT (see `pyproject.toml` / `LICENSE`). Permissive; no copyleft obligations. All deps
(Skyfield, numpy, matplotlib) are permissive and the DE421 ephemeris is freely usable under
NAIF's terms, so nothing forces copyleft.
