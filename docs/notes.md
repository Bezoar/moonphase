# moonphase — Design Notes & Project Dump

This document is a context dump for future contributors (including future
me / future Claude sessions). It captures everything that informed the
current scaffold beyond what the formal spec records: decisions, the
rationale behind them, the alternatives that were considered and
rejected, the things that were deliberately deferred, and the small
gotchas worth knowing before touching the code.

---

## 1. Origin and intent

The project was kicked off on 2026-05-29 with a one-line brief:

> A Python stack to compute microphases of the moon — arbitrary divisions
> of moon phases, charted on an arbitrarily long calendar (across a
> year, perhaps). Standalone Python tool, possibly bundled with a lunar
> ephemeris in a public GitHub repository eventually.

Three explicit constraints came out of the kickoff Q&A:

1. **Ephemeris**: Skyfield + JPL DE421. Chosen for accuracy and the fact
   that Skyfield's loader handles caching automatically.
2. **Outputs**: matplotlib chart, CSV/JSON data, terminal view, and the
   architecture must make adding new formats (PDF being the named
   example) trivial.
3. **Microphase definition**: support **both** `--divisions N` and
   `--step Xdeg`, chosen by mutually exclusive CLI flags.

Everything else in the current scaffold is a consequence of those three.

## 2. Key design decisions

### 2.1 Phase angle, not phase fraction
Internally we work in **degrees of Sun–Moon elongation**, not in
"fraction of cycle" or "illuminated fraction". Reasons:

- Angle composes cleanly with arbitrary angular subdivisions.
- Illuminated fraction is non-monotonic across the cycle (it goes
  0 → 1 → 0) and would force every bucketing scheme to disambiguate
  waxing vs waning.
- Astronomers and ephemeris code already think in elongation.

The 0° convention (new moon) matches USNO and Skyfield's own
`almanac.MOON_PHASES`.

### 2.2 Pluggable renderer registry
The renderer layer is intentionally over-engineered for v0.1: a registry
with a decorator. This is justified because the user explicitly called
out future formats ("such as PDF") and the alternative — an `if/elif`
ladder in `cli.py` — would have to be refactored on the second new
format anyway. Cost now is ~20 lines; benefit is zero churn later.

Chart rendering deliberately delegates *file format* to matplotlib's
`savefig`, so PNG / SVG / PDF / EPS / PS all already work via the
`chart` renderer — `--out chart.pdf` produces a PDF today. The
registered name `chart` describes the *layout* (strip-chart of phase
angle), not the file type.

### 2.3 Lazy ephemeris construction
`PhaseEphemeris.__init__` imports Skyfield inside the method, not at
module import. Two reasons:

- The package's top-level `__init__.py` can be imported in environments
  that don't have Skyfield (e.g. for the microphase math alone) without
  blowing up.
- Cold-import cost stays low; the ~17 MB DE421 kernel is only loaded
  when something actually asks for a phase angle.

### 2.4 UTC everywhere
The series is built in UTC; naive datetimes are coerced to UTC at the
boundary. A `--timezone` flag is on the roadmap but was deferred —
mixing it in now would push timezone handling into every renderer and
the CSV schema. Better to ship UTC-only and add a single conversion
layer later.

### 2.5 Sampling cadence is explicit, not adaptive
We sample on a fixed cadence rather than walking phase angle and
emitting one row per microphase transition. The fixed-cadence approach:

- Maps cleanly to the "one cell per day per glyph" terminal view.
- Makes CSV/JSON output predictable in size.
- Is fast enough that even sub-hour cadences over a year are trivial.

A future `--transitions-only` mode (one row per microphase boundary
crossing) is a clear candidate for later work (see §10).

### 2.6 The non-integer-step edge case
`MicrophaseScheme.from_step(7.0)` is legal: 360 / 7 ≈ 51.43, so we
ceil to 52 bins and the last bin is short (`51 * 7 = 357°` → bin 51
covers `[357°, 360°)`, only 3° wide). This was a judgement call; the
spec flags it as open question R3. The current behavior favors
"never refuse user input" but means the last bin has different
semantics from the others.

## 3. Things considered and rejected

- **PyEphem instead of Skyfield**: lighter, but Skyfield's frame API
  (`ecliptic_frame`) gives us apparent ecliptic longitudes in two lines
  without manual precession bookkeeping.
- **Meeus algorithm with no ephemeris**: ~1 arcminute is plenty for
  phase angle, but shipping a kernel means we're also positioned to add
  rise/set, eclipses, libration later without changing dependencies.
- **`astropy.coordinates`**: works, but the install footprint
  (`numpy + scipy + astropy + erfa + ...`) is heavy for a tool whose
  core job is one cross-coordinate subtraction.
- **A `--phase-of CSV/JSON` separation**: instead of one CLI with
  `--format`, we considered separate `moonphase-chart` /
  `moonphase-data` scripts. Rejected — `--format` keeps the surface
  area small and matches how `ffmpeg`, `pandoc`, etc. work.
- **Storing samples as a pandas DataFrame**: tempting, but would add
  pandas as a hard dep for a feature (`.to_csv()`) we already do in
  ~10 lines of stdlib `csv`.
- **A `moon.py` top-level convenience module**: rejected — the
  three-module split (`microphase`, `ephemeris`, `calendar`) maps to the
  three independently testable concerns.
- **Auto-downloading the kernel on package import**: rejected as
  surprising; downloads only happen when `PhaseEphemeris()` is actually
  instantiated.

## 4. Repository layout

```
moonphase/
├── .gitignore               # excludes .venv, caches, *.bsp kernels
├── LICENSE                  # MIT
├── README.md                # quick-start oriented
├── pyproject.toml           # setuptools, console script, optional [dev]
├── docs/
│   ├── specs/primary.md     # the formal spec
│   └── notes.md             # ← this file
├── src/moonphase/
│   ├── __init__.py          # re-exports public API
│   ├── microphase.py        # MicrophaseScheme + phase_to_index
│   ├── ephemeris.py         # PhaseEphemeris (Skyfield wrapper)
│   ├── calendar.py          # build_series + PhaseSample
│   ├── cli.py               # argparse entry point (`moonphase`)
│   └── renderers/
│       ├── __init__.py      # registry + register()/get()/available()
│       ├── chart.py         # matplotlib strip-chart (png/svg/pdf/...)
│       ├── data.py          # csv + json renderers
│       └── terminal.py      # one-row-per-day unicode moon glyphs
└── tests/
    └── test_microphase.py   # 4 unit tests over the bucket math
```

The `src/`-layout (rather than a flat `moonphase/` package at the repo
root) is the modern Python packaging recommendation: it prevents
accidentally importing the source dir instead of the installed package
during tests.

## 5. Dependencies and why

| Package      | Why                                                            |
|--------------|----------------------------------------------------------------|
| `skyfield`   | Ephemeris + time scales + frames; lazy-imported inside class.  |
| `numpy`      | Used by Skyfield anyway; we use it for vector phase arrays.    |
| `matplotlib` | Strip-chart renderer; backend chosen by env (Agg if headless). |
| `pytest`     | `[dev]` extra; not required for end-users.                     |
| `ruff`       | `[dev]` extra; lint config in `pyproject.toml`.                |

No optional groups beyond `dev`. If we add HTML or ICS renderers and
they need extra deps (e.g. `icalendar`), introduce a `[ics]` extra at
that point rather than pre-allocating empty groups.

## 6. The renderer registry pattern

```
# src/moonphase/renderers/__init__.py
_REGISTRY: dict[str, Renderer] = {}

def register(name): ...
def get(name): ...
def available(): ...

# Import side-effect at bottom of __init__.py registers built-ins:
from . import chart, data, terminal  # noqa
```

To add a renderer:

1. Create `src/moonphase/renderers/<name>.py`.
2. Define `def render(samples, scheme, out): ...`.
3. Decorate it with `@register("<cli-name>")`.
4. Import the new module from `renderers/__init__.py` (one-line edit).

No other code needs to change. The CLI picks up the new name
automatically via `renderers.available()`.

## 7. CLI surface (current)

```
moonphase --start YYYY-MM-DD --end YYYY-MM-DD
          (--divisions N | --step Xdeg)
          [--sample 1h]
          [--format {chart,csv,json,terminal}]
          [--out PATH]
          [--ephemeris PATH.bsp]
```

Mutually exclusive group on `--divisions` / `--step` enforces "exactly
one" semantics at the argparse level — the CLI never has to validate
that itself.

Sampling cadence parser accepts a small DSL (`30m`, `1h`, `2d`); kept
deliberately tiny rather than pulling in `pytimeparse` or similar.

## 8. Verified behavior

- `pytest -q` → 115 passed, covering microphase math, event root-finding,
  every renderer, the CLI, labels, theming, and timezone handling — all
  **offline via a synthetic linear ephemeris** (no kernel download).
- `python -c "from moonphase.cli import build_parser; build_parser().parse_args(['--help'])"`
  → prints help with all six registered formats.
- The committed [`samples/`](../samples/README.md) gallery is rendered from
  the **real DE421 kernel** — the manual end-to-end check that download →
  ephemeris → every chart produces correct, eyeballed output for 2026.

Not yet verified in CI (deliberately):

- Automated validation against the real Skyfield/DE421 ephemeris — there is
  still no committed kernel fixture, so the suite can't assert astronomical
  accuracy (full-moon alignment with USNO dates, etc.) on every run. The
  `samples/` gallery covers this manually instead.

## 9. Things to remember when touching the code

- **Don't add `tzinfo` defaulting inside `PhaseEphemeris`** — it's
  `calendar.build_series`'s job to normalize. Keeping timezone logic in
  one place avoids drift.
- **Don't memoize phase angles in `PhaseEphemeris`** — callers may pass
  millions of distinct timestamps; a dict-cache would silently OOM.
- **Don't import matplotlib at module top-level in `renderers/chart.py`**
  — currently it's imported inside `render()`, which keeps the CLI's
  `--help` snappy and lets the package work in environments without
  matplotlib (e.g. CSV-only batch jobs once we make `matplotlib`
  optional).
- **Mind the wraparound in `phase_to_index`**: `360.0 % 360.0 = 0.0`,
  not `360.0`. The clamp `if idx >= divisions` is defensive; the only
  way to trigger it is float-rounding pathology near 360°.
- **Renderer registration is import-time, not lazy**. Importing
  `renderers/__init__.py` pulls in matplotlib (via `chart.py`) at
  import resolution… **except** that `chart.py` does its matplotlib
  import inside `render()`, so the side effect of registration is
  cheap. Don't undo that.

## 10. Roadmap (rough order)

**Shipped:** the four spec phases (centered model + exact events, time
handling, the `heatmap`/`almanac` renderers with tints/layouts, custom
labels), the `samples/` gallery rendered from the real kernel, and the
**PyPI release** — v1.0.0 (2026-05-30), then v1.1.0 (cell-times peak labels
+ transition arrows), then v1.2.0 (Moon-Mother labels: `name,abbrev` CSV →
`--tint index` in-cell codes + grid legend, `--title`/`--footer`; transition
marker changed from `→` to `Δ`). Versioning jumped straight to 1.0 at release,
so the old v0.x milestones are folded into "done".

**Possible future work** is tracked in one place — the spec's canonical
[§9 Possible Future Work / Roadmap](specs/primary.md#9-possible-future-work--roadmap).
Add new ideas there, not here, to avoid drift.

## 11. Known environment notes (2026-05-29 scaffold session)

- Python 3.11.15 was used; `pyproject.toml` claims `>=3.10`.
- Skyfield, numpy, matplotlib installed cleanly into a `.venv/` inside
  the project directory.
- `git init -b main` succeeded; the initial commit failed because the
  harness's commit-signing server rejected the request ("missing
  source" — environment-level issue, not a code problem). The working
  tree was left intact; the user can commit unsigned or from a signed
  context.
- No GitHub remote has been created yet. When that happens it will live
  at a URL the user controls; the current Claude session's MCP scope is
  locked to a different repository (`bezoar/group-synastry-private`) and
  cannot create new ones.

## 12. Glossary of one-line answers to questions a new contributor will ask

- *Why is the package layout `src/moonphase/` and not just `moonphase/`?*
  Modern Python packaging best practice; prevents shadowing the installed
  package with the source tree during tests.
- *Why is `de421.bsp` not committed?*
  ~17 MB binary; bloats clones; gitignored. Skyfield will download it on
  first use.
- *Why isn't there a `Makefile`?*
  Two commands (`pip install -e ".[dev]"` and `pytest`); a Makefile would
  be ceremony for no gain.
- *Why MIT?*
  Permissive license chosen by the project owner. All dependencies
  (Skyfield, numpy, matplotlib and their transitive deps) are permissive
  (MIT/BSD/Apache; certifi is file-scoped MPL-2.0), and the JPL DE421
  ephemeris is freely usable under NAIF's terms — nothing in the stack
  forces copyleft. (The project was briefly AGPL-3.0 during scaffolding;
  relicensed to MIT once the dependency licenses were confirmed clean.)
- *Why no CI yet?*
  Scaffold-only; CI lands when there's a remote to run it against.
