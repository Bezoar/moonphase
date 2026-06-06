# Moon-Mother Labels, Abbreviations, Title & Footer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-microphase abbreviations (via a 2-column `--labels` CSV) rendered in the `--tint index` heatmap as in-cell codes plus a labelled legend, and add `--title` / `--footer` to the chart, heatmap, and almanac renderers.

**Architecture:** A new parallel `Report.abbrevs` list carries short codes alongside the existing `labels`. `labels.py` grows a `resolve_label_set` that detects a comma-delimited `@file` as `name,abbrev` CSV. A new `renderers/chrome.py` centralises the `--title` override and `--footer` drawing shared by all three image renderers. The heatmap gains in-cell codes and a column-major swatch grid legend when abbrevs are present.

**Tech Stack:** Python 3.10+, matplotlib (lazy-imported in renderers), pytest (offline synthetic ephemeris), ruff (line-length 100).

**Conventions:** Run `ruff check src tests` clean before every commit. Tests run fully offline. Reference spec: `docs/superpowers/specs/2026-06-06-moon-mother-labels-design.md`.

---

### Task 1: Add `Report.abbrevs` field

**Files:**
- Modify: `src/moonphase/report.py:22`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_report.py`:

```python
def test_report_abbrevs_defaults_none():
    s = MicrophaseScheme.from_divisions(16)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.abbrevs is None


def test_report_abbrevs_roundtrips():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[],
               labels=["Dark", "Wax", "Bright", "Wane"],
               abbrevs=["Da", "Wx", "Br", "Wn"])
    assert r.abbrevs == ["Da", "Wx", "Br", "Wn"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py::test_report_abbrevs_defaults_none -v`
Expected: FAIL — `TypeError: Report.__init__() got an unexpected keyword argument 'abbrevs'`

- [ ] **Step 3: Add the field**

In `src/moonphase/report.py`, add `abbrevs` right after the `labels` field (line 22):

```python
    labels: list[str] | None = None            # custom names (from --labels); None when unset
    abbrevs: list[str] | None = None           # per-microphase short codes (from a name,abbrev CSV)
    options: dict | None = None                # renderer-specific flags (tint/calendar/...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -v`
Expected: PASS (all, including the existing `test_report_defaults`)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/report.py tests/test_report.py
git commit -m "feat(report): add per-microphase abbrevs field"
```

---

### Task 2: CSV label resolution (`resolve_label_set`)

**Files:**
- Modify: `src/moonphase/labels.py`
- Test: `tests/test_labels.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_labels.py` (and add `resolve_label_set` to the import line `from moonphase.labels import resolve_labels, resolve_label_set`):

```python
def test_label_set_none_returns_none_pair():
    assert resolve_label_set(None, S16) == (None, None)


def test_label_set_non_csv_has_no_abbrevs():
    names, abbrevs = resolve_label_set("New,First Quarter,Full,Last Quarter", S4)
    assert names == ["New", "First Quarter", "Full", "Last Quarter"]
    assert abbrevs is None


def test_label_set_csv_file(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\nCrescent Moon,Cr\nEmerging Moon,Em\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[0] == "Dark Moon" and names[3] == "Emerging Moon"
    assert abbrevs[0] == "Da" and abbrevs[3] == "Em"
    assert abbrevs[4] is None              # unfilled slot -> None


def test_label_set_csv_row_index_alignment(tmp_path):
    # row 1 -> index 0 (new / Dark)
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert (names[0], abbrevs[0]) == ("Dark Moon", "Da")
    assert (names[1], abbrevs[1]) == ("Sickle Moon", "Si")


def test_label_set_csv_sparse_abbrev(tmp_path):
    # a row with a name but no second column -> abbrev None for that slot
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon\nCrescent Moon,Cr\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[1] == "Sickle Moon"
    assert abbrevs[1] is None
    assert abbrevs[2] == "Cr"


def test_label_set_csv_first_comma_only(tmp_path):
    # split on the first comma; defensive (names normally have no commas)
    p = tmp_path / "m.csv"
    p.write_text("Full, Moon,Fl\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[0] == "Full"
    assert abbrevs[0] == "Moon,Fl"          # everything after the first comma


def test_label_set_one_per_line_unchanged(tmp_path):
    p = tmp_path / "names.txt"
    p.write_text("New\n\nFirst Quarter\n")
    names, abbrevs = resolve_label_set(f"@{p}", S8)
    assert names[0] == "New"
    assert names[1] == "Waxing Crescent"     # blank -> built-in
    assert abbrevs is None


def test_resolve_labels_still_returns_names_only(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    assert resolve_labels(f"@{p}", S16)[0] == "Dark Moon"
```

Note: `test_label_set_csv_first_comma_only` asserts the abbrev is the remainder after the first comma (`"Moon,Fl"`), confirming we split once.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_labels.py::test_label_set_csv_file -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_label_set'`

- [ ] **Step 3: Implement `_parse_csv` + `resolve_label_set`**

In `src/moonphase/labels.py`, add `_parse_csv` after `_parse_overrides`, then add `resolve_label_set` and make `resolve_labels` a wrapper. Full new tail of the module:

```python
def _parse_csv(text: str, n: int) -> tuple[dict[int, str], dict[int, str]]:
    """Parse a 2-column ``name,abbrev`` CSV. Physical line order is the
    microphase index (line 1 -> index 0), matching the one-name-per-line form.
    Split on the first comma only; blank/missing fields leave that slot unset."""
    names: dict[int, str] = {}
    abbrevs: dict[int, str] = {}
    for i, line in enumerate(text.splitlines()):
        if i >= n:
            break
        name, _, abbr = line.partition(",")
        name, abbr = name.strip(), abbr.strip()
        if name:
            names[i] = name
        if abbr:
            abbrevs[i] = abbr
    return names, abbrevs


def resolve_label_set(
    spec: str | None, scheme: MicrophaseScheme
) -> tuple[list[str] | None, list[str] | None]:
    """Return ``(names, abbrevs)``. ``names`` is the resolved label list (built-in
    fallbacks applied) or ``None``; ``abbrevs`` is a length-``divisions`` list of
    codes-or-``None``, but only when ``spec`` is a 2-column ``@file`` CSV — every
    other spec form yields ``abbrevs is None``."""
    if spec is None:
        return None, None
    n = scheme.divisions
    if spec.startswith("@"):
        path = Path(spec[1:])
        try:
            text = path.read_text()
        except OSError as e:
            raise ValueError(f"cannot read --labels file {str(path)!r}: {e}") from e
        # CSV when it is not JSON and any line carries a comma. (Names have no
        # commas, so a comma signals the second 'abbrev' column.)
        if not text.strip().startswith("{") and any("," in ln for ln in text.splitlines()):
            names_d, abbr_d = _parse_csv(text, n)
            names = [names_d.get(i) or default_name(i, scheme) for i in range(n)]
            abbrevs = [abbr_d.get(i) for i in range(n)]
            return names, abbrevs
    overrides = _parse_overrides(spec, n)
    names = [overrides.get(i) or default_name(i, scheme) for i in range(n)]
    return names, None


def resolve_labels(spec: str | None, scheme: MicrophaseScheme) -> list[str | None] | None:
    """Names only (back-compatible wrapper over :func:`resolve_label_set`)."""
    return resolve_label_set(spec, scheme)[0]
```

Delete the OLD `resolve_labels` body (the one that called `_parse_overrides` directly) — it is replaced by the wrapper above. `_parse_overrides` is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_labels.py -v && ruff check src/moonphase/labels.py`
Expected: PASS, no lint errors

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/labels.py tests/test_labels.py
git commit -m "feat(labels): resolve 2-column name,abbrev CSV via resolve_label_set"
```

---

### Task 3: Shared title/footer helper (`renderers/chrome.py`)

**Files:**
- Create: `src/moonphase/renderers/chrome.py`
- Test: `tests/test_chrome.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chrome.py`:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report
from moonphase.renderers.chrome import resolved_title, draw_footer
from moonphase.theme import get_theme

S4 = MicrophaseScheme.from_divisions(4)


def _report(options=None):
    return Report(scheme=S4, mode="series", samples=[], options=options)


def test_resolved_title_prefers_override():
    assert resolved_title(_report({"title": "Custom"}), "auto") == "Custom"


def test_resolved_title_falls_back_to_default():
    assert resolved_title(_report(None), "auto") == "auto"
    assert resolved_title(_report({"title": None}), "auto") == "auto"


def test_draw_footer_adds_figure_text():
    fig = plt.figure()
    try:
        draw_footer(fig, _report({"footer": "cite me"}), get_theme("dark"))
        assert any(t.get_text() == "cite me" for t in fig.texts)
    finally:
        plt.close(fig)


def test_draw_footer_noop_when_unset():
    fig = plt.figure()
    try:
        before = len(fig.texts)
        draw_footer(fig, _report(None), get_theme("dark"))
        assert len(fig.texts) == before
    finally:
        plt.close(fig)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chrome.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonphase.renderers.chrome'`

- [ ] **Step 3: Implement `chrome.py`**

Create `src/moonphase/renderers/chrome.py`:

```python
"""Shared chart 'chrome': the --title override and the --footer line, used by
the chart, heatmap, and almanac renderers so title/footer behave identically."""

from __future__ import annotations


def resolved_title(report, default: str) -> str:
    """The ``--title`` override (options['title']) when set and non-empty,
    otherwise the renderer's auto-built ``default``."""
    title = (report.options or {}).get("title")
    return title if title else default


def draw_footer(fig, report, theme, scale: float = 1.0) -> None:
    """Draw ``options['footer']`` as a low-contrast, themed line centered at the
    figure bottom. Multi-line aware. No-op when no footer is set. Enlarges the
    bottom margin so the text is not clipped; call after ``fig.tight_layout()``."""
    footer = (report.options or {}).get("footer")
    if not footer:
        return
    nlines = footer.count("\n") + 1
    pad = 0.05 + 0.03 * nlines * scale
    fig.subplots_adjust(bottom=max(fig.subplotpars.bottom, pad + 0.02))
    fig.text(0.5, 0.012, footer, ha="center", va="bottom",
             fontsize=round(7 * scale), color=theme.muted, linespacing=1.2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chrome.py -v && ruff check src/moonphase/renderers/chrome.py`
Expected: PASS, no lint errors

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/chrome.py tests/test_chrome.py
git commit -m "feat(renderers): shared title/footer chrome helper"
```

---

### Task 4: Wire title/footer into the `chart` renderer

**Files:**
- Modify: `src/moonphase/renderers/chart.py`
- Test: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_renderers.py`:

```python
def test_chart_title_and_footer(tmp_path):
    samples = [PhaseSample(when=T0, angle_deg=0.0, microphase=0),
               PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0)]
    r = Report(scheme=S4, mode="series", samples=samples,
               options={"title": "My Title", "footer": "Source: book\nISBN 123"})
    out = tmp_path / "tf.png"
    renderers.get("chart")(r, str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it passes-as-smoke / then add assertion of wiring**

Run: `pytest tests/test_renderers.py::test_chart_title_and_footer -v`
Expected: PASS already as a smoke test (options are ignored today). This test guards against regressions once wired; proceed to wire the behavior.

- [ ] **Step 3: Wire chart.py**

In `src/moonphase/renderers/chart.py`:

Add to imports (after `from . import register`):

```python
from .chrome import draw_footer, resolved_title
```

Replace the title block (currently lines ~73–76):

```python
        start_utc, end_utc = report.span()
        caption = report.tz.caption(start_utc, end_utc)
        auto = (f"Lunar microphases — {s.divisions} divisions ({step:.3f}° each)\n"
                f"times in {caption}")
        ax.set_title(resolved_title(report, auto), fontsize=10)
```

Replace the closing block (currently `fig.tight_layout()` then save):

```python
        fig.tight_layout()
        draw_footer(fig, report, theme)
        if out:
            fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
        else:
            plt.show()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -k chart -v && ruff check src/moonphase/renderers/chart.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/chart.py tests/test_renderers.py
git commit -m "feat(chart): honor --title override and draw --footer"
```

---

### Task 5: Wire title/footer into the `almanac` renderer

**Files:**
- Modify: `src/moonphase/renderers/almanac.py`
- Test: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_renderers.py`:

```python
def test_almanac_title_and_footer(tmp_path):
    r = Report(scheme=S4, mode="events", events=_almanac_report().events,
               options={"title": "Almanac!", "footer": "cite"})
    out = tmp_path / "atf.png"
    renderers.get("almanac")(r, str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_renderers.py::test_almanac_title_and_footer -v`
Expected: PASS as smoke (options ignored today); wire behavior next.

- [ ] **Step 3: Wire almanac.py**

In `src/moonphase/renderers/almanac.py`:

Add to imports (after `from . import register`):

```python
from .chrome import draw_footer, resolved_title
```

Replace the title call (currently lines ~62–64):

```python
        start_utc, end_utc = report.span()
        auto = (f"Lunar almanac — {report.scheme.divisions} divisions · "
                f"times in {tz.caption(start_utc, end_utc)}")
        ax.set_title(resolved_title(report, auto), fontsize=10, color=theme.fg)
        fig.tight_layout()
        draw_footer(fig, report, theme)
```

(The existing `fig.tight_layout()` line is replaced by the two-line tight_layout + draw_footer above; the `if out:` save block below it is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -k almanac -v && ruff check src/moonphase/renderers/almanac.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/almanac.py tests/test_renderers.py
git commit -m "feat(almanac): honor --title override and draw --footer"
```

---

### Task 6: Wire title/footer into the `heatmap` renderer

**Files:**
- Modify: `src/moonphase/renderers/heatmap.py` (imports, `_render_gregorian`, `_render_lunar`)
- Test: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_renderers.py`:

```python
def test_heatmap_title_and_footer(tmp_path):
    r = _heatmap_report(options={"tint": "index", "calendar": "gregorian",
                                 "title": "Heat!", "footer": "cite\nline2"})
    out = tmp_path / "htf.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_renderers.py::test_heatmap_title_and_footer -v`
Expected: PASS as smoke; wire behavior next.

- [ ] **Step 3: Wire heatmap.py title + footer**

In `src/moonphase/renderers/heatmap.py`:

Add to imports (after `from .celltext import damped_text_color`):

```python
from .chrome import draw_footer, resolved_title
```

In `_render_gregorian`, replace the `_finish(...)` call (currently lines ~304–306) so the auto title goes through `resolved_title`, and add the footer after `fig.tight_layout()`:

```python
            years = sorted({d[:4] for d in cells})
            auto = (f"{', '.join(years)} — {scheme.divisions} microphases · "
                    f"tint: {tint} · times in {caption}")
            _finish(plt, fig, ax, theme, resolved_title(report, auto), scale=scale)
            fig.tight_layout()
            draw_footer(fig, report, theme, scale=scale)
            _save(plt, fig, out)
```

In `_render_lunar`, do the same for its `_finish(...)` call (currently lines ~344–346):

```python
        auto = (f"Lunar months ({anchor}-anchored) — {scheme.divisions} microphases · "
                f"tint: {tint} · times in {caption}")
        _finish(plt, fig, ax, theme, resolved_title(report, auto))
        fig.tight_layout()
        draw_footer(plt.gcf(), report, theme)
        _save(plt, fig, out)
```

(Use the local `fig` variable rather than `plt.gcf()` if it is in scope — in `_render_lunar` it is, so write `draw_footer(fig, report, theme)`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -k heatmap -v && ruff check src/moonphase/renderers/heatmap.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/heatmap.py tests/test_renderers.py
git commit -m "feat(heatmap): honor --title override and draw --footer"
```

---

### Task 7: Heatmap abbreviations — `_label_of` prefers abbrev; in-cell codes

**Files:**
- Modify: `src/moonphase/renderers/heatmap.py` (`_label_of`, add `_draw_cell_code`, `_render_gregorian` cell loop)
- Test: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_renderers.py`:

```python
def test_label_of_prefers_abbrev():
    from moonphase.renderers.heatmap import _label_of
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[],
               labels=["Dark Moon"] + [None] * 15,
               abbrevs=["Da"] + [None] * 15)
    label = _label_of(r)
    assert label(0) == "Da"          # abbrev wins
    assert label(1) == "1"           # no abbrev, no name -> index


def test_label_of_falls_back_to_name_then_index():
    from moonphase.renderers.heatmap import _label_of
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[],
               labels=["Dark Moon"] + [None] * 15)   # no abbrevs at all
    label = _label_of(r)
    assert label(0) == "Dark Moon"
    assert label(2) == "2"


def _heatmap_report_with_abbrevs(**opts):
    base = {"tint": "index", "calendar": "gregorian"}
    base.update(opts)
    r = _heatmap_report(options=base)
    codes = ["Da", "Si", "Cr", "Em", "1Q", "Sw", "Gb", "Cu",
             "Fl", "1W", "Di", "Tr", "LQ", "Yd", "Bl", "Im"]
    names = [c + " Moon" for c in codes]
    return Report(scheme=r.scheme, mode="series", samples=r.samples,
                  events=r.events, options=r.options, labels=names, abbrevs=codes)


def test_heatmap_index_with_abbrevs_writes_png(tmp_path):
    out = tmp_path / "abbr.png"
    renderers.get("heatmap")(_heatmap_report_with_abbrevs(), str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py::test_label_of_prefers_abbrev -v`
Expected: FAIL — `_label_of` currently ignores abbrevs, returns `"0"` (the index) for slot 0 because the name `"Dark Moon"` is at labels[0]... actually returns `"Dark Moon"`. The assertion `== "Da"` fails.

- [ ] **Step 3: Update `_label_of` and add `_draw_cell_code`**

In `src/moonphase/renderers/heatmap.py`, replace `_label_of` (lines ~47–57):

```python
def _label_of(report):
    """Return f(idx) -> short text: the abbreviation when one was given for that
    slot, else the custom name, else the bare index number."""
    labels = report.labels
    abbrevs = report.abbrevs

    def label(idx):
        if abbrevs and idx < len(abbrevs) and abbrevs[idx]:
            return abbrevs[idx]
        if labels and idx < len(labels) and labels[idx]:
            return labels[idx]
        return str(idx)

    return label


def _code_of(report, idx):
    """The compact code drawn inside an index-tint cell: the abbreviation when
    present for that slot, else the bare index number (never the long name)."""
    abbrevs = report.abbrevs
    if abbrevs and idx < len(abbrevs) and abbrevs[idx]:
        return abbrevs[idx]
    return str(idx)
```

Add `_draw_cell_code` next to `_draw_cell_times`:

```python
def _draw_cell_code(ax, x0, row, code, cell_rgb):
    """Draw a microphase's 2-letter code centered in its index-tint cell."""
    ax.text(x0 + 0.47, row + 0.47, code, ha="center", va="center",
            fontsize=9, color=damped_text_color(cell_rgb), zorder=8)
```

In `_render_gregorian`, set a `codes` flag near where `legend`/`label_of` are computed (after `label_of = _label_of(report)`):

```python
    codes = legend and bool(report.abbrevs)      # index tint + abbreviations present
```

(`legend` is already `tint == "index"`.) Then update the per-cell loop. Replace the rectangle + marker + cell-times block (currently lines ~263–275):

```python
                    a, i = cells[key]
                    rgb = _tint(a, i, scheme, tint)
                    ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                                 facecolor=rgb, edgecolor="none"))
                    # Markers (and centered codes) are suppressed in cell-times
                    # mode, where the cell prints times instead.
                    if key in marks and not cell_times and not codes:
                        _draw_marker(ax, dd - 0.53, row + 0.47, 0.30,
                                     marks[key], theme)
                    if cell_times and key in day_trans:
                        _draw_cell_times(ax, dd - 1, row, day_trans[key],
                                         cells[key], scheme, tint, label_of)
                    elif codes and not cell_times:
                        _draw_cell_code(ax, dd - 1, row, _code_of(report, i), rgb)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -k "label_of or abbrev or heatmap" -v && ruff check src/moonphase/renderers/heatmap.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/heatmap.py tests/test_renderers.py
git commit -m "feat(heatmap): in-cell microphase codes; abbrev-aware cell labels"
```

---

### Task 8: Heatmap labelled grid legend (`--tint index` + abbrevs)

**Files:**
- Modify: `src/moonphase/renderers/heatmap.py` (add `math` import, `_legend_grid_dims`, `_index_grid_legend`, `_legend_band`, sizing + ylim + legend dispatch)
- Test: `tests/test_renderers.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_renderers.py`:

```python
def test_legend_grid_dims():
    from moonphase.renderers.heatmap import _legend_grid_dims
    assert _legend_grid_dims(16) == (4, 4)
    assert _legend_grid_dims(8) == (3, 3)
    assert _legend_grid_dims(4) == (2, 2)


def test_index_grid_legend_draws_entries():
    import matplotlib.pyplot as plt
    from moonphase.renderers.heatmap import _index_grid_legend
    from moonphase.theme import get_theme
    r = _heatmap_report_with_abbrevs()
    fig, ax = plt.subplots()
    try:
        _index_grid_legend(plt, ax, r.scheme, r, get_theme("dark"), top_y=0.0, scale=1.0)
        texts = [t.get_text() for t in ax.texts]
        assert "Da = Da Moon" in texts        # code = full name
        assert "Im = Im Moon" in texts
        assert len(texts) == 16
    finally:
        plt.close(fig)
```

(`_heatmap_report_with_abbrevs` from Task 7 names each phase `"<code> Moon"`, so the entry text is `"Da = Da Moon"`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py::test_legend_grid_dims -v`
Expected: FAIL — `ImportError: cannot import name '_legend_grid_dims'`

- [ ] **Step 3: Implement the grid legend + sizing**

In `src/moonphase/renderers/heatmap.py`:

Add `import math` to the top imports (with the stdlib imports near `from datetime import date`):

```python
import math
from contextlib import nullcontext
from datetime import date
```

Add the grid helpers (place them just above `_index_legend`):

```python
_LEG_ROW_H = 0.7            # data-unit height of one grid-legend row


def _legend_grid_dims(n):
    """(cols, rows) for the labelled swatch grid: roughly square, max 4 columns.
    16 -> 4x4, 8 -> 3x3 (one empty), 4 -> 2x2."""
    cols = min(4, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    return cols, rows


def _index_grid_legend(plt, ax, scheme, report, theme, top_y, scale):
    """Column-major labelled legend: per microphase a hue swatch + 'code = name'.
    Drawn below the calendar grid when index tint has abbreviations. ``top_y`` is
    the data-y of the first row; rows grow downward."""
    n = scheme.divisions
    cols, rows = _legend_grid_dims(n)
    col_w = 31.0 / cols
    sw = 0.5
    fs = round(7 * scale)
    names = report.labels or []
    for k in range(n):
        c, r = divmod(k, rows)                 # column-major fill
        x = c * col_w + 0.1
        y = top_y + r * _LEG_ROW_H
        ax.add_patch(plt.Rectangle((x, y), sw, sw * 0.9,
                     facecolor=_index_color(k, n), edgecolor="none"))
        name = names[k] if k < len(names) and names[k] else ""
        code = _code_of(report, k)
        text = f"{code} = {name}" if name else code
        ax.text(x + sw + 0.2, y + sw * 0.45, text, ha="left", va="center",
                fontsize=fs, color=theme.muted)


def _legend_band(has_legend, cell_times, grid):
    """Data-unit height of the region below the calendar grid (day-of-month axis
    plus the legend). With a grid legend it grows to hold all legend rows."""
    if grid:
        _, rows = grid
        return _bottom_band(False, cell_times) + 0.6 + rows * _LEG_ROW_H
    return _bottom_band(has_legend, cell_times)
```

Change `_giant_figsize` to take the bottom band in data units instead of `has_legend`. Replace its signature and the `band = ...` line:

```python
def _giant_figsize(plt, day_trans, label_of, n_rows, band, family):
    """Figure size (inches) that fits the widest 'label HH:MM' line and the
    tallest stacked cell at the 9 pt floor. ``band`` is the bottom-region height
    in data units (day axis + legend)."""
```

and remove the internal `band = _bottom_band(has_legend, giant=True)` line (the parameter replaces it). The final return line stays:

```python
    return gutter + 31 * cell_w, title + cell * (n_rows + band + 0.5)
```

Update `_resolve_figsize` to forward `band` instead of `has_legend`. Replace its signature and the `_giant_figsize(...)` call:

```python
def _resolve_figsize(plt, size, cell_times, day_trans, label_of, n_rows,
                     band, family):
    ...
        need_w, need_h = _giant_figsize(plt, day_trans, label_of, n_rows,
                                        band, family)
```

In `_render_gregorian`, compute the grid + band before sizing. Replace the figsize block (currently lines ~237–245):

```python
    family = _resolve_font(font)
    day_trans = (cell_events_by_day(report.events, report.tz, scheme.divisions)
                 if cell_times else {})
    label_of = _label_of(report)
    codes = legend and bool(report.abbrevs)
    grid = _legend_grid_dims(scheme.divisions) if (legend and report.abbrevs) else None
    band_units = _legend_band(legend, cell_times, grid)
    figsize = _resolve_figsize(plt, size, cell_times, day_trans, label_of,
                               nrows, band_units, family)
    if figsize is None:
        figsize = (11, 0.9 + 0.42 * nrows)
    scale = _label_scale(figsize)
```

(Move the `codes = ...` line here from Task 7 so it sits with `grid`; delete the duplicate added in Task 7.)

Replace the legend-drawing block (currently lines ~294–299) to dispatch to the grid:

```python
            if legend:
                if grid:
                    legend_top = nrows + _bottom_band(False, cell_times) + 0.4
                    _index_grid_legend(plt, ax, scheme, report, theme,
                                       legend_top, scale)
                elif cell_times:
                    _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 1.6, 0.6,
                                  scale=scale, cap_below=True)
                else:
                    _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 1.05, 0.5)
```

Replace the ylim line (currently line ~301) to use `band_units`:

```python
            ax.set_ylim(nrows + band_units, -0.5)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -k "legend or heatmap or abbrev" -v && ruff check src/moonphase/renderers/heatmap.py`
Expected: PASS (including the existing `test_heatmap_index_tint_png` and `test_heatmap_light_theme_and_index_legend`, which have no abbrevs and so still use the strip legend)

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS (all prior tests plus the new ones)

- [ ] **Step 6: Commit**

```bash
git add src/moonphase/renderers/heatmap.py tests/test_renderers.py
git commit -m "feat(heatmap): labelled column-major grid legend for index tint + abbrevs"
```

---

### Task 9: CLI — `--title`, `--footer`, and abbrev-aware `--labels`

**Files:**
- Modify: `src/moonphase/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (the `_LinearEph` fixture already exists in this file):

```python
def test_main_title_footer_reach_options(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get",
                        lambda name: (lambda report, out: captured.__setitem__("r", report)))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "16",
        "--format", "csv", "--title", "My T", "--footer", "Source: book",
        "--out", str(tmp_path / "o.csv"),
    ])
    assert rc == 0
    assert captured["r"].options["title"] == "My T"
    assert captured["r"].options["footer"] == "Source: book"


def test_main_labels_csv_populates_abbrevs(tmp_path, monkeypatch):
    csvf = tmp_path / "m.csv"
    csvf.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    captured = {}
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get",
                        lambda name: (lambda report, out: captured.__setitem__("r", report)))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "16",
        "--format", "csv", "--labels", f"@{csvf}", "--out", str(tmp_path / "o.csv"),
    ])
    assert rc == 0
    assert captured["r"].labels[0] == "Dark Moon"
    assert captured["r"].abbrevs[0] == "Da"
    assert captured["r"].abbrevs[2] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_main_labels_csv_populates_abbrevs -v`
Expected: FAIL — `AttributeError`/`assert` because `report.abbrevs` is `None` (CLI doesn't resolve abbrevs yet)

- [ ] **Step 3: Wire cli.py**

In `src/moonphase/cli.py`:

Change the labels import (line 17):

```python
from .labels import resolve_label_set
```

Add the two arguments in `build_parser`, right after the existing `--labels` argument (after line 132):

```python
    p.add_argument("--title", default=None,
                   help="custom chart title (overrides the auto-generated one); "
                        "chart/heatmap/almanac")
    p.add_argument("--footer", default=None,
                   help="free-text footer line drawn under the chart; "
                        "chart/heatmap/almanac (supports embedded newlines)")
```

In `main`, replace the label resolution (line 161) inside the existing `try`:

```python
        mode = resolve_mode(args.format, args.mode, renderers.modes_for)
        labels, abbrevs = resolve_label_set(args.labels, scheme)
```

Add `title`/`footer` to the `options` dict (lines ~170–172):

```python
    options = {"theme": args.theme, "tint": args.tint, "calendar": args.calendar,
               "lunar_anchor": args.lunar_anchor, "size": args.size,
               "cell_times": args.cell_times, "font": args.font,
               "title": args.title, "footer": args.footer}
```

Pass `abbrevs` to both `Report(...)` constructions (events branch ~line 181 and series branch ~line 189):

```python
        report = Report(scheme=scheme, mode="events", events=events, tz=zone,
                        options=options, labels=labels, abbrevs=abbrevs)
```

```python
        report = Report(scheme=scheme, mode="series", samples=samples,
                        events=events, tz=zone, options=options,
                        labels=labels, abbrevs=abbrevs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v && ruff check src/moonphase/cli.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat(cli): --title, --footer, and 2-column --labels CSV (abbrevs)"
```

---

### Task 10: Ship the Moon-Mother example CSV

**Files:**
- Create: `examples/moon-mother-16.csv`
- Test: `tests/test_labels.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_labels.py`:

```python
def test_shipped_moon_mother_csv_resolves():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    csv_path = root / "examples" / "moon-mother-16.csv"
    names, abbrevs = resolve_label_set(f"@{csv_path}", S16)
    assert names[0] == "Dark Moon" and abbrevs[0] == "Da"
    assert names[4] == "First Quarter Moon" and abbrevs[4] == "1Q"
    assert names[8] == "Full Moon" and abbrevs[8] == "Fl"
    assert names[15] == "Immanent Moon" and abbrevs[15] == "Im"
    assert all(a for a in abbrevs)        # all 16 slots have a code
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_labels.py::test_shipped_moon_mother_csv_resolves -v`
Expected: FAIL — file does not exist (`cannot read --labels file`)

- [ ] **Step 3: Create the CSV**

Create `examples/moon-mother-16.csv`:

```csv
Dark Moon,Da
Sickle Moon,Si
Crescent Moon,Cr
Emerging Moon,Em
First Quarter Moon,1Q
Swelling Moon,Sw
Gibbous Moon,Gb
Culminating Moon,Cu
Full Moon,Fl
First Waning Moon,1W
Disseminating Moon,Di
Transporting Moon,Tr
Last Quarter Moon,LQ
Yielding Moon,Yd
Balsamic Moon,Bl
Immanent Moon,Im
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_labels.py::test_shipped_moon_mother_csv_resolves -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/moon-mother-16.csv tests/test_labels.py
git commit -m "feat(examples): ship moon-mother-16.csv name,abbrev label set"
```

---

### Task 11: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/primary.md`
- Modify: `docs/generated/moon-mother-phases.md`

- [ ] **Step 1: Update the README CLI synopsis & options**

In `README.md`, in the `## CLI` fenced synopsis block, add the two new flags near `--labels`:

```
          [--title TEXT]             # custom chart title (chart/heatmap/almanac)
          [--footer TEXT]            # free-text footer line (chart/heatmap/almanac)
```

Update the `--labels` line in the synopsis to mention the CSV form:

```
          [--labels SPEC]            # names: "A,B,C", @file (one per line / JSON), or @name,abbrev.csv
```

In the prose under "Calendar & almanac views", add an example:

```bash
# 16 Moon-Mother phases with 2-letter codes in each cell + a labelled legend,
# a custom title, and a book citation footer
moonphase --start 2026-01-01 --end 2026-12-31 --divisions 16 --format heatmap \
          --tint index --labels @examples/moon-mother-16.csv \
          --title "2026 — Faces of the Moon Mother" \
          --footer "Names: The Faces of the Moon Mother (ISBN 0-9624716-2-3)" --out mother.png
```

Update the `heatmap` row of the Renderers table to note: "With `--tint index` and a 2-column `--labels` CSV, each cell shows the microphase's 2-letter code and a labelled swatch legend is drawn beneath the grid."

- [ ] **Step 2: Update the `--labels` documentation paragraph**

In `README.md`, where `--labels` is described (under "Calendar & almanac views"), append:

> A 2-column `@file` CSV (`Full Name,AB` per line, row order = microphase index) also sets a short **abbreviation** per phase; those codes are drawn in `--tint index` heatmap cells and its legend. See `examples/moon-mother-16.csv`.

- [ ] **Step 3: Update the spec**

In `docs/specs/primary.md`, note in the appropriate feature section (and reconcile §9 roadmap) that custom `--title`/`--footer` and per-microphase abbreviations now exist. Add a one-line entry; if §9 listed either as future work, mark it resolved.

- [ ] **Step 4: Point the generated doc at the shipped CSV**

In `docs/generated/moon-mother-phases.md`, add a line under the table:

```markdown
These names and codes ship as `examples/moon-mother-16.csv` — use them with
`moonphase --divisions 16 --format heatmap --tint index --labels @examples/moon-mother-16.csv`.
```

- [ ] **Step 5: Verify docs reference real paths and the full suite is green**

Run: `pytest -q && ruff check src tests`
Expected: PASS, no lint errors

- [ ] **Step 6: Commit**

```bash
git add README.md docs/specs/primary.md docs/generated/moon-mother-phases.md
git commit -m "docs: document --title/--footer, 2-column labels CSV, moon-mother example"
```

---

## Self-Review Notes (for the implementer)

- **Spec coverage:** Task 2 → CSV labels; Tasks 7–8 → in-cell codes + grid legend; Tasks 3–6, 9 → `--title`/`--footer` across chart/heatmap/almanac + CLI; Task 10 → example asset; Task 11 → docs. Report field (Task 1) underpins all renderer work.
- **`--cell-times` interaction:** Task 7 routes cell-times labels through the abbrev-preferring `_label_of`; in-cell codes are only drawn in the non-cell-times branch (`elif codes and not cell_times`), so the two never collide.
- **Back-compat:** index-tint charts without abbrevs keep the strip legend (`grid is None`); non-CSV `--labels` forms yield `abbrevs is None`; `resolve_labels` remains a names-only wrapper.
- **Naming consistency:** `resolve_label_set`, `_parse_csv`, `_code_of`, `_legend_grid_dims`, `_index_grid_legend`, `_legend_band`, `_LEG_ROW_H`, `resolved_title`, `draw_footer` are used identically across tasks.
