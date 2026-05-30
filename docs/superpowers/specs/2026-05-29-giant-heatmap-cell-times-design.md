# Design: Giant heatmap with in-cell transition times

**Date:** 2026-05-29
**Status:** Draft for review
**Scope:** `heatmap` renderer (gregorian layout only), CLI flags `--size`, `--cell-times`, `--font`.

## Problem

The heatmap colours each day cell by its microphase but never says *when* the
phase changed. When the user wants the exact transition instants on the calendar
itself, they currently have to cross-reference the `almanac` or `events` output.

This feature lets the heatmap print, inside each day cell, the time(s) at which a
microphase transition took effect that day — at a deliberately low-to-medium
contrast so the colour field still reads as the primary signal. Because legible
text needs room, the chart is sized up to fit it ("giant").

## Why the data already supports this

In **series mode** (which `heatmap` uses) the `Report` already carries
`report.events`, built with `transitions=args.transitions`. The heatmap renderer
ignores them today. So no pipeline change is needed — this is a renderer feature
plus three CLI flags.

`phase_to_index` centres microphases on `k·step`, so a cell's microphase index
changes **at a transition** (the half-step boundary), not at a centre. "The time
the indicated phase took effect" therefore maps exactly to a `transition` event's
`.when`.

**Index correctness:** a `transition` event's `.index` is the bin being *left*
(`_classify` floors the ratio). The phase that *took effect* is the bin *entered*
= `(event.index + 1) % scheme.divisions`. The in-cell label must use the entered
index, matching the cell's own tint.

## CLI surface

Three new flags on the existing parser:

- **`--size WIDTHxHEIGHT`** — explicit output dimensions in **pixels**
  (e.g. `--size 5000x3000`). Order is **width × height** (the common convention).
  Parsed by a small `_parse_size` helper alongside `_parse_step`/`_parse_sample`.
  Stored in `options`. Converted to matplotlib `figsize = (w/dpi, h/dpi)` at the
  existing dpi. When omitted, today's auto-sizing is unchanged.

- **`--cell-times`** — turn on in-cell transition text. Constraints:
  - **Requires `--transitions`** — error if absent (no transition events exist).
  - **Requires `--calendar gregorian`** — error on `lunar` (lunar cells are
    synthetic gradient columns, not real days).
  - **Sizes the figure from content** (see "Sizing" below) rather than a fixed
    baseline.

- **`--font VALUE`** — `VALUE` is either an installed family name
  (e.g. `"Courier New"`) or a path to a `.ttf`/`.otf` file. A path is registered
  via `matplotlib.font_manager` and then referenced by its family name; an
  unknown family raises a clear `ValueError`. Default `None` → matplotlib default
  (DejaVu Sans). Applies to the heatmap's text (cells, row/column labels, title).
  Stored in `options`.

## Data helper (pure)

New function in `heatmap_layout.py` (consistent with its "pure layout helpers,
no matplotlib" charter — unit-testable with fake events):

```python
def transitions_by_day(events, tz, divisions) -> dict[str, list[tuple[int, datetime]]]:
    """date_iso -> time-sorted [(entered_index, local_datetime), ...] for each
    `kind == "transition"` event, where entered_index = (e.index + 1) % divisions."""
```

`divisions` is passed explicitly (from `report.scheme.divisions`) so the helper
stays pure and independent of the scheme object.

## Cell rendering (gregorian only)

In `_render_gregorian`, after the tint rect and any principal-phase moon-disk
marker, draw the day's transition list:

- **Per-crossing text** = `"{label} @ {HH:MM}"` in the display tz.
  - **Label** = `report.labels[entered_index]` when `--labels` was supplied,
    else the bare index number. This lets a user pass terse labels
    (`E+G`, `L-C`) and get `E+G @ 14:42`.
- **Adaptive by density:** stack one line per crossing while they fit the cell at
  the floor font; when the count exceeds `stack_cap` (default 4, tunable),
  collapse the cell to a count badge (e.g. `6×`). The tallest *rendered* stack is
  therefore `min(global_max_per_day, stack_cap)` lines — this is what sizing
  targets.
- **Colour — auto per-cell, damped:** derive a light-or-dark base from the cell's
  luminance, then blend it toward the cell colour so the result lands in a
  low–medium contrast band (never full black/white). One small helper, used for
  both `illumination` and `index` tints.

Empty days (no transition) render exactly as today: tint only, no text.

In cell-times mode the principal-phase moon-disk markers are suppressed: the
principal phases (New, 1Q, Full, 3Q) appear as plain `label @ HH:MM` text like
any other microphase transition. (The non-giant heatmap still draws the markers.)

## Sizing (content-driven, 9 pt floor)

Point size is absolute (9 pt = 9/72 inch) regardless of figure size, so a cell
holds the text only if the cell's *inch* size ≥ the text's inch size. We size the
figure directly from the labels:

1. **Measure, don't guess.** Render the longest `"{label} @ HH:MM"` once on a
   throwaway matplotlib renderer **in the chosen `--font` at 9 pt** to get its
   true pixel/inch extent (real glyph widths, not a 0.6-em estimate). This is why
   `--font` needs no special-casing: a wider font simply yields a larger figure.
2. **Rows of text per cell** = `min(max transitions in any single day, stack_cap)`
   — computed from the actual events, so it scales with `--divisions` and range.
3. **Required cell** inches = `(longest_line_w + pad_w)` ×
   `(rows × line_h + pad_h)`.
4. **Figure** inches = `label_gutter + 31·cell_w` wide ×
   `title + n_months·cell_h` tall (+ legend strip when `tint == index`).
   Pixels = `figsize × dpi`.

**Interaction with `--size`:**

- `--cell-times` **without** `--size` → use the computed size. No fixed baseline.
- `--size` ≥ computed (both dims) → honour it; cells get roomier than the floor.
- `--size` < computed in either dim → **raise `ValueError`**: "labels won't fit at
  the 9 pt minimum — need at least W×H." This is the label-fit guard, expressed as
  one size comparison rather than a per-cell check.

The only fixed constants are `stack_cap`, the 9 pt floor, and a few paddings — all
tunable. The 9 pt floor is the single legibility guarantee.

## Module boundaries

- `heatmap_layout.py` (pure): add `transitions_by_day`. No matplotlib. Unit-tested.
- `renderers/celltext.py` (new, small): damped-contrast colour helper. (The
  size/measurement logic stays in `heatmap.py` because it needs font metrics.)
- `heatmap.py`: wire the above into `_render_gregorian`; add the content-driven
  sizing + `--size`/`--font` handling. `_render_lunar` is untouched.
- `cli.py`: add `_parse_size`, the three arguments, and the
  `--cell-times` requires-`--transitions`/requires-`gregorian` validation.

## Testing

- **Pure, CI-tested:** `transitions_by_day` (entered-index math, tz-day mapping,
  time-sort, multi-per-day); the damped-contrast helper (output stays within the
  contrast band across a luminance sweep).
- **Manual/smoke** (consistent with the repo's deferred ephemeris/renderer tests):
  a giant `--cell-times` render at low and high `--divisions`; `--size` too-small
  error; `--cell-times` without `--transitions` error; `--cell-times` with
  `--calendar lunar` error; a custom `--font` path and an unknown-family error.

## Out of scope

- Lunar-calendar in-cell times (different "cell" semantics; revisit later).
- In-cell times for phase *centres* (only transitions change the microphase, so
  only transitions are shown).
- Applying `--size`/`--font` to the `chart`/`almanac` renderers — they may adopt
  the same `options` keys later, but this spec only commits the heatmap.

## Open tuning knobs (not blockers)

`stack_cap`, the cell paddings, the contrast-damp blend factor, and the dpi used
for the px↔inch conversion. All have sane defaults above and can be adjusted after
seeing real output.
