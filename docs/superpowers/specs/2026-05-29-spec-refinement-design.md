# moonphase — Spec Refinement: Centered Phases, Exact Events, Transition Points & Chart Designs

Status: **approved design** (brainstormed 2026-05-29)
Branch: `spec-refinement`
Supersedes/updates: parts of `docs/specs/primary.md` (§4 definitions, §5.1 binning, §5.3–5.5, §6 N6) and `docs/notes.md` §2.4 (UTC-only).

## 1. Summary

This refinement does four things:

1. **Redefines the microphase model** so a phase is an *arc centered on* `k·step`, with the
   `k·step` point being the phase's exact center/peak instant (New, Full, …). Binning shifts
   by half a step.
2. **Adds exact event-finding** — root-found, sub-second instants of phase centers and
   transition points — alongside the existing sampled series.
3. **Introduces transition points** as a first-class, separately-labeled category at
   `(k+½)·step`, exposed via a `--transitions` flag (not a finer division).
4. **Adds three chart renderers** (refined strip-chart, calendar heatmap, almanac moon ribbon),
   custom microphase naming (`--labels`), local-time handling, and explicit timezone captions.

## 2. Vocabulary (authoritative)

The synodic cycle is 360° of Sun–Moon elongation; 0° = New, 90° = First Quarter, 180° = Full,
270° = Last Quarter. For `divisions = N`, `step = 360/N`.

| Term | Location | Meaning |
|------|----------|---------|
| **Phase center** | `k·step` | The exact peak instant of microphase `k`. For `N=4` these are the classical principal phases. The "identify as precisely as possible" targets. |
| **Phase / microphase** | arc `[(k−½)·step, (k+½)·step)` | One of `N` equal arcs, **centered** on its phase center. "Phase" and "microphase" are synonyms; "microphase" emphasizes arbitrary `N`. |
| **Transition point** | `(k+½)·step` | The boundary between two adjacent microphase arcs. A separate labeled category — **not** a finer division. |

A microphase is bounded by two transition points and centered on one phase center.

## 3. Data model

### 3.1 Centered binning (`microphase.py`)

`MicrophaseScheme` is unchanged (`divisions`, `step_deg`, `from_divisions`, `from_step`).
`phase_to_index` changes from left-edged to **centered**, using deterministic round-half-up:

```python
def phase_to_index(phase_deg, scheme):
    return int((phase_deg / scheme.step_deg) + 0.5) % scheme.divisions
```

- `k·step` is the **center** of microphase `k` (so 0° → middle of microphase 0 = "New").
- `floor(x + 0.5)` (via `int()` on a non-negative value) is round-half-up, so exact transition
  boundaries (e.g. 11.25°, 33.75° at `N=16`) assign **consistently** to the higher-index arc —
  unlike Python's banker's `round()`.
- Precision is **not** lost here: the index is only a label; the full-resolution angle lives in
  `PhaseSample.angle_deg`, and exact instants come from root-finding (§3.3), never from rounding.

Note: callers must pass a non-negative normalized angle (`phase_deg % 360`) before the formula,
which `build_series` and the ephemeris already guarantee (`% 360.0`).

Updated unit tests (centered semantics) for `N=4`: `idx(0)=0`, `idx(44)=0`, `idx(46)=1`,
`idx(359.9)=0`. The transition-boundary case `idx(315)=0`: `(315/90)+0.5 = 4.0`,
`int(4.0)%4 = 0` — 315° is the Last-Quarter↔New transition and round-half-up assigns it *up*
into New (index 0); `idx(314.9)=3` stays in Last Quarter. These boundary cases become explicit
regression tests.

### 3.2 Events (`events.py`, new — same dependency level as `calendar.py`)

```python
@dataclass(frozen=True)
class PhaseEvent:
    when:   datetime          # exact UTC instant (sub-second), tz-aware
    angle_deg: float          # target elongation crossed: k·step or (k+½)·step
    kind:   str               # "center" | "transition"
    index:  int               # microphase index k
    name:   str | None        # resolved label (see §6) or None

def build_events(start, end, scheme, ephemeris, transitions=False) -> list[PhaseEvent]: ...
```

Events are returned in chronological order. `name` is resolved per §6.

### 3.3 Finding exact crossings (the precise part)

Use Skyfield's `almanac.find_discrete(t0, t1, fn)`, which locates instants where an integer
step-function changes value.

- **`transitions=False`**: define `fn(t) = floor(angle(t) / step)` (with `fn.step_days` set
  conservatively below the minimum spacing between centers). Each value-change is a crossing of
  a multiple of `step` → a **phase center**. `index = round(angle/step) mod N` at the crossing.
- **`transitions=True`**: define `fn(t) = floor(angle(t) / (step/2))` — half-step resolution.
  Each change is a crossing of a multiple of `step/2`; classify **even** multiples as `center`,
  **odd** multiples as `transition`. The half-step is purely an internal computational device;
  nothing downstream treats the result as `2N` microphases.

`fn.step_days` (find_discrete's coarse scan step) must be smaller than the minimum spacing
between adjacent targets so no crossing is skipped. The Moon advances ~12.2°/day in elongation,
so spacing in days ≈ `(step or step/2) / 12.2`. Set `step_days = spacing_days / 4` with a floor
(e.g. `min(0.25, …)`), and document that extremely large `N` shrinks the scan step (cost grows
with `N`). This is the one place runtime scales with `divisions`.

Internals operate in UTC/TT (Skyfield requirement); tz handling is a boundary concern (§5).

## 4. Renderer interface

### 4.1 `Report` context object (replaces the bare `samples` arg)

```python
@dataclass(frozen=True)
class Report:
    scheme:  MicrophaseScheme
    mode:    str                      # "series" | "events"
    samples: list[PhaseSample] | None # the dense series; present iff mode == "series"
    events:  list[PhaseEvent]  | None # root-found events (see table)
    tz:      tzinfo                    # resolved display timezone (§5)
    labels:  list[str] | None          # resolved per-microphase labels (§6)
```

New renderer signature: **`render(report, out) -> None`**. This supersedes the v0.1 frozen API
(§8 of primary.md) — the one intentional breaking change; the registry exists precisely so this
costs one signature update per renderer.

`events` contents by mode:
- `mode="events"`: phase centers always; transition points too iff `--transitions`. `samples=None`.
- `mode="series"`: `samples` = dense series; `events` = phase centers (always) + transition
  points (iff `--transitions`) **for overlay markers**, root-found within range.

### 4.2 Mode-declaring registry

```python
@register("chart", modes={"series", "events"})
def render(report, out): ...
```

`register(name, modes)` stores capabilities. `available(mode=None)` filters by supported mode.

| Renderer | series | events | notes |
|----------|:--:|:--:|-------|
| `chart` (A) | ✓ | ✓ | strip from `samples`; overlays markers from `events` |
| `heatmap` (B) | ✓ | — | needs the dense daily series; `--tint` option |
| `almanac` (C) | — | ✓ | moon disks at `events` (events-native view) |
| `csv` / `json` | ✓ | ✓ | series rows **or** event rows |
| `terminal` | ✓ | ✓ | glyph grid **or** event list |

Extensibility seam unchanged: a new renderer is one file — define `render(report, out)`,
`@register(name, modes=…)`, add the one import line in `renderers/__init__.py`.

## 5. Time handling (revises primary.md §F3.2, notes §2.4)

Resolve **one display timezone** per run, in priority order:

1. Explicit offset on `--start` (full ISO 8601, e.g. `…Z` or `…-08:00`) → that zone.
2. Else a discernible system-local timezone → local.
3. Else UTC (safety fallback).

Then:
- Bare dates / naive datetimes (`2026-01-01`) are interpreted in the display timezone (→ local
  midnight on a normal machine, **not** UTC).
- Internals convert to UTC for ephemeris + root-finding.
- **Output is rendered in the display timezone**, emitted as ISO 8601 **with offset**
  (`2026-01-01T00:00:00-08:00`). The CSV `utc` column is renamed `time`; JSON gains a
  `"timezone"` metadata field. Terminal grid and heatmap group by **display-tz calendar days**.
- Conversions are **DST-aware per instant** via `datetime.astimezone()` (OS local rules) — no new
  dependency. A year-long local chart correctly shows winter/summer offsets, and each event's ISO
  offset reflects its own instant.

**Timezone caption (mandatory on every time-bearing render):** charts, almanac, heatmap, terminal
all state their display tz explicitly. For a named/local zone the caption names the zone
(`local time (PST/PDT)`); for an explicit fixed offset / UTC it labels that offset; if the offset
changes within the range, the caption notes it (`local time, DST changes within range`).

**Determinism tradeoff (revises N6):** output now depends on the host timezone *unless* an
explicit offset is supplied. Documented; reproducible/CI runs should pass an explicit offset or
`Z`. An explicit `--timezone` override remains roadmap, out of scope here.

## 6. Custom microphase names (`--labels`)

`--labels` supplies names; resolution feeds `PhaseEvent.name` and renderer axis/marker labels.

- **Inline**: comma-separated list, e.g. `--labels "New,Early Crescent,Crescent,…"`.
- **File**: `--labels @path` — one name per line, **or** a JSON object `{ "0": "New", "4": "…" }`.
- **Sparse-merge**: blank/missing entries fall back to built-in names (for `N ∈ {4, 8}`) else to
  a default derived from index/angle. So you can name only the gradations you care about.
- Length: an inline/line list shorter or longer than `N` is padded/validated leniently per the
  sparse-merge rule (missing → fallback); a JSON map indexes directly. Out-of-range indices in a
  JSON map are an error listing the valid range `0..N-1`.
- Built-in name tables: `N=4` (New / First Quarter / Full / Last Quarter) and `N=8`
  (adds Waxing Crescent / Waxing Gibbous / Waning Gibbous / Waning Crescent at the odd indices).

## 7. CLI surface

```
moonphase --start DATE --end DATE
          (--divisions N | --step Xdeg)
          [--mode {series,events}]
          [--transitions]
          [--tint {illumination,index}]
          [--labels SPEC]
          [--sample DUR]
          [--format NAME]
          [--out PATH]
          [--ephemeris PATH.bsp]
```

| Flag | Required | Default | Notes |
|------|----------|---------|-------|
| `--start` / `--end` | yes | — | UTC offset honored; bare date → display tz (§5). |
| `--divisions N` \| `--step Xdeg` | exactly one | — | mutually exclusive group (unchanged). |
| `--mode` | no | auto from format | see resolution below. |
| `--transitions` | no | off | include transition points (overlay in series; rows in events). |
| `--tint` | no | `illumination` | **heatmap only**; `illumination` (grayscale by lit fraction) or `index` (discrete hue per microphase). |
| `--labels` | no | built-ins / auto | inline list or `@file`, sparse-merge (§6). |
| `--sample DUR` | no | `1h` | **series only**; ignored in events mode (documented). |
| `--format NAME` | no | `chart` | dynamic choices from registry, filtered by resolved mode. |
| `--out PATH` | no | stdout / `show()` | file format inferred from extension where applicable. |
| `--ephemeris PATH` | no | DE421 → `./data/` | unchanged. |

**Mode resolution:**
- `--mode` omitted + format supports exactly one mode → use it (`almanac`→events, `heatmap`→series).
- `--mode` omitted + multi-mode format → default `series`.
- `--mode` given but incompatible → single-line error listing compatible modes, e.g.
  `error: format 'almanac' supports mode(s): events`.

**Validation order** (failure → non-zero exit, single line to stderr, per primary.md F4.5):
1. argparse (dates parse; exactly one of `--divisions`/`--step`; `--format` registered).
2. Resolve mode; check format/mode compatibility.
3. `start <= end`; `divisions >= 1` / `step ∈ (0, 360]`; resolve `--labels`; resolve tz.

## 8. Renderers

All renderers emit a mandatory timezone caption (§5) and honor `report.labels`.

### 8.1 `chart` (A) — analytic strip-chart (refines existing)
- X = time with **daily tick marks, faint daily gridlines (every 7th heavier), weekly date
  labels**. Y = elongation 0–360°.
- **Named phases on the left axis**, **degree angle (0/90/180/270/360°) on the right axis**.
- Centered phase bands (alternating shade); solid phase-center gridlines; dashed transition
  gridlines (when `--transitions`).
- Phase-angle curve (sawtooth, broken at each lunation wrap). Event overlays: filled dots
  (colored by phase) at phase-center crossings; open orange rings at transition crossings.
- Colorbar / phase legend retained. Matplotlib; file format from `--out` extension.

### 8.2 `heatmap` (B) — calendar grid
- Real calendar: months × day-of-month (short months trimmed), grouped by display-tz days.
- `--tint illumination` (default): grayscale by illuminated fraction `(1−cos θ)/2` → ~29.5-day
  diagonal banding; gradient legend New→Full→New.
- `--tint index`: each microphase index gets a distinct hue (`hsl(idx/N·360, …)`); discrete
  swatch legend `0..N-1`.
- Principal-phase days carry a moon-disk marker on a **dark backing chip** (so New = empty white
  ring, Full = filled disk, quarters = half-lit, all visible on any cell tint).

### 8.3 `almanac` (C) — moon ribbon (new)
- Horizontal timeline; rendered moon disks at each phase-center event with name + date + exact
  time below. Transition points as dashed ticks between disks (when `--transitions`).
- Moon disks use correct lit-limb geometry with **degenerate-fraction handling** (New renders
  empty, Full renders solid — the naive limb path collapses to a full disk at exactly 0°).
- Traditional phases emphasized (bold); custom-labeled gradations in normal weight.

### 8.4 Moon-disk geometry (shared helper)
Lit-limb path: `rx = r·cos θ`, bright limb on the right for `θ ≤ 180°`, terminator half-ellipse
sweep flips for gibbous vs crescent. Guard: illuminated fraction `< 0.5%` → draw no lit region
(New); `> 99.5%` → full disk. Always stroke an outline ring for visibility.

## 9. Module / file impact

- `microphase.py` — change `phase_to_index` (centered, round-half-up); update tests.
- `events.py` — **new**: `PhaseEvent`, `build_events`, `find_discrete` wrapper.
- `calendar.py` — unchanged data flow; `build_series` still produces `PhaseSample`.
- `naming.py` (or within `events.py`) — built-in name tables + `--labels` resolution.
- `timezone`/parse helpers in `cli.py` — display-tz resolution; rename CSV column; ISO+offset out.
- `renderers/__init__.py` — `register(name, modes)`, `available(mode)`, `Report`-based dispatch.
- `renderers/chart.py` — refit to `Report`; axis swap, date axis, event overlays.
- `renderers/heatmap.py` — **new**.
- `renderers/almanac.py` — **new** (+ shared moon-disk helper).
- `renderers/data.py`, `renderers/terminal.py` — refit to `Report`; events-mode output;
  ISO+offset timestamps; tz caption/metadata.
- `cli.py` — `--mode`, `--transitions`, `--tint`, `--labels`; mode resolution + validation.
- `docs/specs/primary.md` — reconcile §4, §5.1, §5.3–5.5, §6 N6, §8 API with this doc.

## 10. Acceptance criteria

1. `phase_to_index` is centered: documented edge cases pass (incl. `N=16` transition boundaries).
2. `--mode events --divisions 4` yields New/FQ/Full/LQ instants within ±2 h of USNO 2026 dates;
   `--transitions` adds the four 45/135/225/315° crossings, all `kind="transition"`.
3. `--mode events --format almanac` (auto-resolves to events) renders New as an empty disk and
   Full as solid; `--format almanac --mode series` errors with the compatible-mode list.
4. A bare-date run on a non-UTC host produces local-time output with offsets and a tz caption;
   the same run with `--start …Z` produces UTC output. Captions are present on chart/heatmap/
   almanac/terminal.
5. `--labels @file` sparse-merge: named gradations appear; unnamed indices fall back to built-in
   or index/angle.
6. `heatmap --tint index` shows discrete hue bands; default `illumination` shows grayscale.
7. Adding a renderer is still one new file + one import; no edits to CLI/calendar/events.

## 11. Out of scope (roadmap)

- Explicit `--timezone` override.
- `--transitions-only` series mode; numpy-vectorized `phase_to_index`.
- ICS renderer (events-native), HTML month-grid renderer.
- Bundled-kernel wheel; accuracy bench vs Meeus/PyEphem.
