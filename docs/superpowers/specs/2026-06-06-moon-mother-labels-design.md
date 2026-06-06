# Design — Microphase abbreviations, custom title & footer

- **Date:** 2026-06-06
- **Branch:** `moon-mother`
- **Status:** approved design, pre-implementation
- **Motivation:** Support an alternate 16-name lunar scheme (*The Faces of the Moon
  Mother*) where each phase has a short 2-letter code, render those codes in the
  `--tint index` heatmap with a labelled legend, and let any chart carry a custom
  title and a free-text footer (for the book citation).

## 1. Goals

1. `--labels @file` accepts a 2-column CSV (`full name, abbreviation`); the
   abbreviation is a new per-microphase attribute alongside the existing name.
2. In the `--tint index` heatmap, draw each phase's 2-letter code in its day cells
   and a labelled legend (swatch + `AB = Full Name`) at the bottom.
3. `--title TEXT` overrides the auto-generated title on the `chart`, `heatmap`, and
   `almanac` renderers.
4. `--footer TEXT` draws a free-text footer line on those same three renderers.

Non-goals: abbreviations for inline `--labels` or JSON specs (CSV-only); a
structured citation format (footer is verbatim free text); per-renderer footer
styling beyond the shared themed treatment.

## 2. Label data model

Chosen approach: a **parallel `abbrevs` list on `Report`**, resolved beside
`labels`. Rejected alternatives: (B) replacing `labels` with `(name, abbrev)`
objects — rewrites every label consumer for no gain; (C) stashing abbrevs in the
untyped `options` dict — hides a first-class concept.

`Report` gains:

```python
abbrevs: list[str] | None = None   # per-microphase short codes; None when unset
```

`abbrevs` is either `None` (no CSV given) or a length-`divisions` list whose slots
are a code string or `None`.

### 2.1 `labels.py` resolution

A new combined resolver returns both lists from one spec parse:

```python
def resolve_label_set(spec, scheme) -> tuple[list[str] | None, list[str] | None]:
    """Return (names, abbrevs). abbrevs is None unless spec is a 2-column CSV."""
```

`resolve_labels` is kept as a thin wrapper (`resolve_label_set(...)[0]`) so any
external caller of the existing public function is unaffected.

CSV detection happens inside the `@file` branch:

- **CSV mode** — triggered when **any** non-blank line contains a comma. Each
  non-blank line is `full name, abbrev`; split on the **first** comma only (names
  have no commas, but this is defensive). Row order is the microphase index
  `0..N-1`. Row 1 → index 0 (new / Dark Moon). A missing or empty second field
  leaves that slot's abbrev `None`. Rows beyond `N` are ignored; fewer than `N`
  rows leaves trailing slots at their name fallback / abbrev `None`.
- **One-name-per-line** — no comma anywhere → today's behavior; abbrevs all `None`.
- **JSON `{index: name}`** — unchanged; abbrevs `None`.
- **Inline `--labels "A,B,C"`** — unchanged (names only; abbrevs `None`).

Names still fall back to `default_name(i, scheme)` per slot (built-ins for N∈{4,8}).
Abbrevs have **no built-in fallback**; an unset slot is `None` and renders as the
index number where a code is needed (mirrors `_label_of` today).

## 3. Heatmap: in-cell codes + labelled legend (`--tint index`)

All new drawing is conditional on `report.abbrevs` being non-`None`. Existing
index-tint charts (no CSV) are visually unchanged.

### 3.1 In-cell codes

In `_render_gregorian`, when `tint == "index"`, abbrevs present, and **not** in
`--cell-times` mode, each populated day cell draws its phase's code centered, using
`damped_text_color(_tint(...))` for contrast (same helper the cell-times text uses).
The code for a cell is `abbrevs[i] or str(i)`.

### 3.2 Labelled legend (4-column grid)

When abbrevs are present, `_index_legend` is replaced by a grid legend:

- One entry per microphase: a hue swatch (`_index_color(k, N)`) followed by
  `AB = Full Name` (code falls back to `str(k)`, name to its resolved label).
- **Column-major** fill: down column 1 (indices 0..r-1), then column 2, etc., so
  the cycle reads top-to-bottom, left-to-right.
- Column count adapts to `N`: `cols = min(4, ceil(sqrt(N)))`,
  `rows = ceil(N / cols)`; trailing cells in the last column stay empty. This gives
  N=16 → 4×4, N=8 → 3×3 (one empty), N=4 → 2×2.
- Column width is driven by the longest `AB = Full Name` string so columns align.
- When abbrevs are **absent**, the current `microphase 0 … N-1` hue strip stays.

The grid lives in the bottom band; `_bottom_band` (and the giant-mode sizing in
`_giant_figsize`) grow to reserve room for `rows` legend rows at the structural
label scale.

### 3.3 `--cell-times` interaction

When `--cell-times` is on **and** abbrevs are present, the per-line label produced
by `_label_of` uses the abbreviation (`Da 14:25`, `→1Q 09:02`) instead of the long
custom name / index. No separate centered code is drawn in that mode (the times
occupy the cell). `_label_of` gains access to abbrevs and prefers
`abbrevs[idx]` when set, else the existing behavior (custom name → index). Because
`_giant_figsize` measures via `_label_of`, auto-sizing follows automatically.

## 4. Custom title & footer (chart, heatmap, almanac)

### 4.1 CLI + plumbing

Two new options, threaded through the existing `options` dict:

```
--title TEXT     # override the auto-generated chart title
--footer TEXT    # free-text footer line (supports embedded \n)
```

`options` gains `"title"` and `"footer"` keys (default `None`).

### 4.2 Shared helper: `renderers/chrome.py`

A new tiny module so all three renderers share one implementation:

```python
def resolved_title(report, default: str) -> str:
    """The --title override if set, else the renderer's auto-built default."""

def draw_footer(fig, report, theme, scale=1.0) -> None:
    """Draw options['footer'] as a low-contrast, themed line at the figure
    bottom (fig.text in figure coords, muted color, multi-line aware). No-op
    when no footer is set. Reserves bottom margin so it isn't clipped."""
```

### 4.3 Per-renderer changes

- **heatmap** (`_finish`): title text becomes `resolved_title(report, <auto>)`;
  `draw_footer` called after layout. The footer sits below the legend grid; the
  bottom margin/figure height accounts for it.
- **chart** (`render`): `ax.set_title(resolved_title(report, <auto>))`;
  `draw_footer(fig, report, theme)` before `tight_layout`/save.
- **almanac** (`render`): same two calls.

Footer placement uses `fig.text` in figure coordinates with a small reserved bottom
margin (`fig.subplots_adjust` / added figure height) so it never overlaps axes
content. Themed with `theme.muted`.

## 5. CLI summary

- Add `--title`, `--footer` (both `default=None`), thread into `options`.
- `--labels` now resolves via `resolve_label_set`; both `labels` and `abbrevs`
  passed to `Report` in both `events` and `series` branches.
- `--labels` help text mentions the `name,abbrev` CSV form.
- No new hard errors: abbrevs supplied with `--tint illumination` are simply unused
  by cell tinting (still available as cell-times labels). Title/footer apply to the
  three image renderers; passing them to `csv`/`json`/`terminal` is ignored.

## 6. Tests (offline, synthetic ephemeris — consistent with the existing suite)

- `labels.py`: CSV parse (`name,abbrev`); comma-detection chooses CSV vs
  one-name-per-line; JSON still names-only; sparse abbrev rows → `None` slots;
  row→index alignment (row 1 = index 0); first-comma split.
- `Report`: `abbrevs` defaults `None`.
- `heatmap` (index tint + abbrevs): day cells draw codes (assert text artists);
  legend renders the labelled grid (assert per-entry text); cell-times mode uses
  abbrev labels in the time lines; no codes drawn when abbrevs absent.
- `chrome`: `resolved_title` returns override vs default; `draw_footer` adds a
  figure text when set, no-op when unset — exercised on chart, heatmap, almanac.
- CLI: `--title`/`--footer` reach `options`; `--labels @csv` populates
  `report.abbrevs`.

## 7. Docs & example asset

- Ship `examples/moon-mother-16.csv` — the 16 `name,abbrev` rows (Dark…Immanent),
  so `--labels @examples/moon-mother-16.csv` works out of the box.
- README: document the CSV form, `--title`, `--footer`, the abbrev legend; update
  the CLI synopsis block and the `--labels` row.
- `docs/specs/primary.md`: note that custom title/footer and per-microphase
  abbreviations now exist; reconcile the §9 roadmap if it listed either.
- `docs/generated/moon-mother-phases.md`: add a one-line pointer to the shipped CSV.

## 8. Out of scope / future

- Abbreviations via inline or JSON specs.
- A structured citation/credits block (footer stays verbatim free text).
- Title/footer on the text renderers (`csv`/`json`/`terminal`).
