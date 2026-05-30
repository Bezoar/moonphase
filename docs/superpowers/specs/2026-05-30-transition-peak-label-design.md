# Cell-times: peak labels + transition arrows — design

**Date:** 2026-05-30
**Status:** Approved
**Branch:** `feat/transition-peak-label`

## Summary

Extend the giant `--cell-times` heatmap so each day cell can print two kinds of
moment, visually distinguished:

- **Transition into a phase** — arrow prefix: `→Full 14:25`
- **Phase peak (center)** — bare label: `Full 21:23`

And decouple `--cell-times` from `--transitions`:

| Flags | Cell contents |
|---|---|
| `--cell-times` alone | peaks only — `Full 21:23` |
| `--cell-times --transitions` | peaks + transitions, merged & time-sorted — `→Full 14:25` / `Full 21:23` |

The `@` separator used today (`label @ HH:MM`) is dropped throughout this
renderer; lines are now `label HH:MM` (peaks) or `→label HH:MM` (transitions).

## Motivation

Today the cell-times renderer shows only the *boundary crossing* into each phase,
which sits roughly half a microphase before that phase's actual peak. Users
reading the chart want the peak instant too (the exact New/Full/quarter/… moment,
and the center of every finer microphase). Distinguishing the two with a leading
`→` keeps both legible in one cell without a separate legend.

## Behavior

- A **center** event's `index` *is* the peaked phase (no offset). Rendered bare.
- A **transition** event's `index` is the phase being *left*; the entered phase is
  `(index + 1) % divisions`. Rendered with a `→` prefix.
- Both kinds for a day are merged and sorted chronologically, so a cell may read
  `→Full 14:25` / `Full 21:23` when the crossing and the peak fall on the same day
  (usually they're on different days).
- The `N×` overflow badge (past `_STACK_CAP == 4`) counts transitions + peaks
  together.

## Data source — no pipeline change

`report.events` already carries everything:

- `build_events` emits `kind == "center"` events **unconditionally**.
- `--transitions` adds `kind == "transition"` events.

So peak-only mode needs no special branch — under `--cell-times` without
`--transitions`, the transition events simply aren't present to render.

## Changes by file

1. **`src/moonphase/heatmap_layout.py`** — replace `transitions_by_day` with
   `cell_events_by_day(events, tz, divisions)` returning
   `dict[date_iso → time-sorted list[(is_transition: bool, idx, local)]]`.
   Collects both `center` and `transition` kinds. The module stays
   presentation-free — it returns the `is_transition` flag, not the `→` glyph;
   the renderer owns the arrow.

2. **`src/moonphase/renderers/heatmap.py`**
   - `_draw_cell_times`: each line is
     `f"{'→' if is_trans else ''}{label_of(idx)} {local:%H:%M}"`.
   - `_giant_figsize`: build the width-measurement candidate lines the same way
     (arrow-prefixed transition lines are the widest case) and count merged
     events for stacked-cell height.
   - Swap the `transitions_by_day` call and the `day_trans` variable to
     `cell_events_by_day`.

3. **`src/moonphase/cli.py`**
   - Remove the `elif not args.transitions: "--cell-times requires --transitions"`
     check. Keep the `--format heatmap` and `--calendar gregorian` checks.
   - Update `--cell-times` help: prints phase-peak times inside heatmap day cells,
     and with `--transitions` also the transition-into-phase times;
     `--calendar gregorian` only.

4. **`samples/README.md`** — update the `--cell-times` blurb to document both
   modes and the arrow-vs-bare distinction; regenerate
   `heatmap-cell-times-2026-16div.png` (kept on the `--transitions` command so the
   sample shows both kinds).

5. **Tests** — update `test_heatmap_layout.py` for `cell_events_by_day` (cover
   centers-only, transitions+centers merge/sort, and the entered-index vs
   center-index distinction); extend the renderer format assertions
   (`→label HH:MM` and bare `label HH:MM`, no `@`).

## Edge notes

- `→` (U+2192) is present in matplotlib's default DejaVu Sans. A `--font`
  override lacking the glyph is the user's responsibility (same posture as today).
- The `--calendar gregorian` and `--format heatmap` gates are unchanged.
