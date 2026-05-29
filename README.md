# moonphase

Compute and chart **microphases** of the Moon — arbitrary divisions of the
synodic cycle — across a date range of any length.

The standard four phases (new, first quarter, full, last quarter) are just
`--divisions 4`. Want 32 phases? `--divisions 32`. Want one tick per degree
of Sun–Moon elongation? `--step 1deg` (= 360 microphases per cycle).

## Status

Early scaffolding. Core ephemeris + microphase math works; renderers are
pluggable so new output formats (PDF, etc.) can be added without touching
the calendar pipeline.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 32 microphases across 2026, write a PNG strip-chart
moonphase --start 2026-01-01 --end 2026-12-31 --divisions 32 --out chart.png

# 1-degree resolution as CSV
moonphase --start 2026-01-01 --end 2026-01-31 --step 1deg --format csv --out jan.csv

# Terminal view
moonphase --start 2026-01-01 --end 2026-01-31 --divisions 8 --format terminal
```

## Ephemeris

Uses Skyfield with the JPL DE421 kernel. The kernel (~17 MB) is downloaded
to `./data/` on first run; it is gitignored by default. Pass
`--ephemeris path/to/de421.bsp` to use a pre-bundled copy.

## License

AGPL-3.0-or-later. See `LICENSE`.
