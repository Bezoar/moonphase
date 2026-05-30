# Phase 4: Custom Microphase Names (`--labels`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users name microphases (especially the finer gradations) via `--labels`, supplied inline or from a file, sparse-merged over the built-in names.

**Architecture:** A pure `labels.py` resolves a `--labels` spec (inline comma list, or `@file` of one-per-line or a JSON `index→name` map) into a length-N list, sparse-merged with `default_name` fallback. The CLI resolves it, stores it on the existing `Report.labels`, and overrides phase-center `PhaseEvent.name`s. Renderers prefer `report.labels` (chart axis) or the now-overridden `event.name` (almanac/csv/json/terminal).

**Tech Stack:** Python ≥3.10 stdlib (`json`, `pathlib`, `dataclasses.replace`), numpy, matplotlib, pytest, ruff.

---

## Scope

Implements spec §5.5 (`--labels`, sparse-merge) and the §6 naming behavior. This is the **final** roadmap phase — afterward all of Phases 1–4 are implemented.

`Report.labels` already exists (a `list[str] | None`, unused until now). `PhaseEvent.name` is currently set from `default_name` in `build_events`.

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/moonphase/labels.py` | create | `resolve_labels(spec, scheme)` — parse + sparse-merge |
| `src/moonphase/cli.py` | modify | `--labels` flag; resolve; set `Report.labels`; override center event names |
| `src/moonphase/renderers/chart.py` | modify | left-axis names from `report.labels` (fallback `default_name`) |
| `tests/test_labels.py` | create | resolve_labels (inline / @file lines / @file JSON / sparse / errors) |
| `tests/test_cli.py` | modify | `--labels` reaches `Report.labels` + overrides event names; bad file errors |
| `tests/test_renderers.py` | modify | csv/almanac honor custom names; chart axis smoke with labels |

---

## Task 1: `resolve_labels` (`labels.py`)

**Files:** Create `src/moonphase/labels.py`, `tests/test_labels.py`.

- [ ] **Step 1: Write the failing test** — create `tests/test_labels.py`:

```python
import json

import pytest

from moonphase.labels import resolve_labels
from moonphase.microphase import MicrophaseScheme

S4 = MicrophaseScheme.from_divisions(4)
S8 = MicrophaseScheme.from_divisions(8)
S16 = MicrophaseScheme.from_divisions(16)


def test_none_spec_returns_none():
    assert resolve_labels(None, S16) is None


def test_inline_full_list():
    got = resolve_labels("New,Cres,Quarter,Gibbous", S4)
    assert got == ["New", "Cres", "Quarter", "Gibbous"]


def test_inline_sparse_falls_back_to_builtin():
    # blanks fall back to the built-in 8-division names
    got = resolve_labels("New,,First Quarter", S8)
    assert got[0] == "New"
    assert got[1] == "Waxing Crescent"      # blank -> built-in
    assert got[2] == "First Quarter"
    assert got[4] == "Full"                 # unspecified -> built-in


def test_inline_extras_ignored():
    got = resolve_labels("A,B,C,D,E,F", S4)   # 6 names for 4 arcs
    assert got == ["A", "B", "C", "D"]


def test_sixteen_unfilled_is_none():
    got = resolve_labels("New", S16)
    assert got[0] == "New"
    assert got[5] is None                    # no built-in for N=16, not overridden


def test_at_file_one_per_line(tmp_path):
    p = tmp_path / "names.txt"
    p.write_text("New\n\nFirst Quarter\n")    # blank line 2 -> fallback
    got = resolve_labels(f"@{p}", S8)
    assert got[0] == "New"
    assert got[1] == "Waxing Crescent"        # blank line -> built-in
    assert got[2] == "First Quarter"


def test_at_file_json_map(tmp_path):
    p = tmp_path / "names.json"
    p.write_text(json.dumps({"0": "Dark", "4": "Bright"}))
    got = resolve_labels(f"@{p}", S8)
    assert got[0] == "Dark"
    assert got[4] == "Bright"
    assert got[2] == "First Quarter"          # unspecified -> built-in


def test_at_file_json_out_of_range_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"9": "Nope"}))   # 9 not in 0..7
    with pytest.raises(ValueError):
        resolve_labels(f"@{p}", S8)


def test_missing_file_raises_valueerror(tmp_path):
    with pytest.raises(ValueError):
        resolve_labels(f"@{tmp_path / 'nope.txt'}", S8)
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_labels.py -v`** — FAIL (no module).

- [ ] **Step 3: Implement `src/moonphase/labels.py`:**

```python
"""Resolve a ``--labels`` spec into per-microphase names.

A spec is either an inline comma list (positional) or ``@path`` to a file that
is one-name-per-line (positional, blank lines skipped) or a JSON ``{index:
name}`` map. Provided names override; everything else falls back to the
built-in name (for N in {4, 8}) or ``None``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .microphase import MicrophaseScheme
from .naming import default_name


def _parse_overrides(spec: str, n: int) -> dict[int, str]:
    if spec.startswith("@"):
        path = Path(spec[1:])
        try:
            text = path.read_text()
        except OSError as e:
            raise ValueError(f"cannot read --labels file {str(path)!r}: {e}") from e
        stripped = text.strip()
        if stripped.startswith("{"):
            data = json.loads(stripped)              # JSONDecodeError is a ValueError
            out: dict[int, str] = {}
            for k, v in data.items():
                i = int(k)
                if not 0 <= i < n:
                    raise ValueError(f"--labels index {i} out of range 0..{n - 1}")
                name = str(v).strip()
                if name:
                    out[i] = name
            return out
        return {i: line.strip() for i, line in enumerate(text.splitlines())
                if i < n and line.strip()}
    return {i: part.strip() for i, part in enumerate(spec.split(","))
            if i < n and part.strip()}


def resolve_labels(spec: str | None, scheme: MicrophaseScheme) -> list[str | None] | None:
    """Return a length-``divisions`` list of names (or ``None`` per slot), or
    ``None`` if ``spec`` is ``None``. Provided names win; gaps fall back to the
    built-in name or ``None``."""
    if spec is None:
        return None
    n = scheme.divisions
    overrides = _parse_overrides(spec, n)
    return [overrides.get(i) or default_name(i, scheme) for i in range(n)]
```

- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_labels.py -v`** — PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/labels.py tests/test_labels.py
git commit -m "feat: resolve_labels — inline/@file custom microphase names with sparse-merge"
```

---

## Task 2: CLI `--labels` + wiring

**Files:** Modify `src/moonphase/cli.py`, `tests/test_cli.py`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_cli.py`:

```python
def test_main_labels_reach_report_and_events(tmp_path, monkeypatch):
    captured = {}

    def fake_render(report, out):
        captured["report"] = report

    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get", lambda name: fake_render)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-01", "--divisions", "4",
        "--mode", "events", "--format", "json", "--labels", "Dark,,Bright,",
    ])
    assert rc == 0
    rep = captured["report"]
    assert rep.labels[0] == "Dark" and rep.labels[2] == "Bright"
    assert rep.labels[1] == "First Quarter"        # blank -> built-in
    # phase-center event names are overridden from labels
    names = {e.index: e.name for e in rep.events if e.kind == "center"}
    assert names.get(0) == "Dark" and names.get(2) == "Bright"


def test_main_labels_bad_file_is_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-02-01", "--divisions", "4",
        "--mode", "events", "--format", "json", "--labels", f"@{tmp_path / 'nope.txt'}",
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_cli.py -k labels -v`** — FAIL (no `--labels`).

- [ ] **Step 3: Implement.** In `src/moonphase/cli.py`:

(a) Add imports:
```python
from dataclasses import replace
from .labels import resolve_labels
```

(b) In `build_parser()`, add after `--lunar-anchor`:
```python
    p.add_argument("--labels", default=None,
                   help="custom microphase names: inline comma list or @file "
                        "(one per line, or JSON index->name); sparse-merged over built-ins")
```

(c) In `main()`, resolve labels next to the mode resolution and surface errors cleanly. Change the existing mode-resolution try/except block so it also resolves labels:
```python
    try:
        mode = resolve_mode(args.format, args.mode, renderers.modes_for)
        labels = resolve_labels(args.labels, scheme)
    except (ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
```

(d) Add a helper near the top of `cli.py` (below `resolve_mode`):
```python
def _label_events(events, labels):
    """Override phase-center event names from resolved labels (transitions keep
    their None name)."""
    if not labels:
        return events
    return [replace(e, name=labels[e.index]) if e.kind == "center" else e
            for e in events]
```

(e) In `main()`, apply labels to the events and pass `labels` to both `Report(...)` constructions. Update the events-mode branch:
```python
    if mode == "events":
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        events = _label_events(events, labels)
        report = Report(scheme=scheme, mode="events", events=events, tz=zone,
                        options=options, labels=labels)
```
and the series-mode branch:
```python
    else:
        samples = build_series(start_utc, end_utc, scheme,
                               sample_step=args.sample, ephemeris=eph)
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        events = _label_events(events, labels)
        report = Report(scheme=scheme, mode="series", samples=samples,
                        events=events, tz=zone, options=options, labels=labels)
```

- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_cli.py -v`** (labels tests + all existing pass), then `.venv/bin/python -m pytest -q` (full suite), then `.venv/bin/ruff check src tests` (clean).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat: --labels CLI flag; set Report.labels and override center event names"
```

---

## Task 3: Renderers honor custom labels

**Files:** Modify `src/moonphase/renderers/chart.py`, `tests/test_renderers.py`.

The event-name consumers (`almanac`, `csv`, `json`, `terminal`) already read
`event.name`, which the CLI now overrides — so they need no change, only a test.
The `chart` left axis reads `default_name` directly and must prefer
`report.labels`.

- [ ] **Step 1: Add tests** to `tests/test_renderers.py`:

```python
def test_csv_events_use_custom_label(tmp_path):
    evs = [PhaseEvent(when=T0, angle_deg=0.0, kind="center", index=0, name="Dark")]
    r = Report(scheme=S4, mode="events", events=evs)
    out = tmp_path / "e.csv"
    renderers.get("csv")(r, str(out))
    assert "Dark" in out.read_text()


def test_chart_uses_report_labels(tmp_path):
    samples = [PhaseSample(when=T0, angle_deg=0.0, microphase=0),
               PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0)]
    r = Report(scheme=S4, mode="series", samples=samples,
               labels=["Dark", "Waxing", "Bright", "Waning"])
    out = tmp_path / "c.png"
    renderers.get("chart")(r, str(out))            # smoke: renders with custom axis
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/test_renderers.py -k "custom_label or report_labels" -v`** — the chart test FAILS (axis ignores labels); the csv test should already pass (it sets `name="Dark"` directly).

- [ ] **Step 3: Update `chart.py`.** Replace the left-axis label line:
```python
        axL.set_yticklabels([default_name(k, s) or f"{(k * step) % 360:.0f}°"
                             for k in range(s.divisions)])
```
with:
```python
        labels = report.labels
        axL.set_yticklabels([
            (labels[k] if labels else default_name(k, s)) or f"{(k * step) % 360:.0f}°"
            for k in range(s.divisions)
        ])
```

- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_renderers.py -v`** (all pass), then `.venv/bin/python -m pytest -q` (full suite), `.venv/bin/ruff check src tests` (clean).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/renderers/chart.py tests/test_renderers.py
git commit -m "feat: chart left axis honors report.labels (custom microphase names)"
```

---

## Task 4: Docs + final verification

**Files:** Modify `README.md`, `docs/specs/primary.md`.

- [ ] **Step 1: README.** In the CLI block, add `[--labels SPEC]`. Add a usage example under "Calendar & almanac views" or events:
```bash
# Custom names for a 16-microphase almanac (sparse — only the gradations you name)
moonphase --start 2026-01-01T00:00Z --end 2026-02-28T23:00Z --divisions 16 \
          --format almanac --labels @names.txt --out almanac-named.png
```
In "Status & roadmap": move **Phase 4 — Custom names** into the **Implemented** list and remove the now-empty "Planned" section (or replace it with a line noting all four roadmap phases are complete).

- [ ] **Step 2: Spec.** In `docs/specs/primary.md`, append " *(implemented in Phase 4)*" to the §5.5 `--labels` bullet line (the line beginning `  - `--labels SPEC``).

- [ ] **Step 3: Doc-sync check.** Extract ground truth and confirm docs match: CLI flags (`build_parser`), public API (`__all__` — `resolve_labels` is internal, not exported, which is fine), `Report` fields. Reconcile any drift.

- [ ] **Step 4: Final verification + a real sample.**
```bash
.venv/bin/python -m pytest -q          # all green
.venv/bin/ruff check src tests          # clean
```
Render a real labelled almanac (uses the cached DE421 kernel):
```bash
printf 'New\nWaxing Crescent\nFirst Quarter\nWaxing Gibbous\nFull\nWaning Gibbous\nLast Quarter\nWaning Crescent\n' > /tmp/names8.txt
.venv/bin/moonphase --start 2026-01-01T00:00Z --end 2026-02-28T23:00Z --divisions 8 \
    --format almanac --labels @/tmp/names8.txt --out /tmp/almanac-labelled.png && echo "rendered"
```
Report the path so the controller can surface it.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/specs/primary.md
git commit -m "docs: mark Phase 4 custom labels implemented; all roadmap phases complete"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** Task 1 → §5.5/§6 sparse-merge resolution; Task 2 → `--labels` flag + `Report.labels` + `PhaseEvent.name` override; Task 3 → chart axis naming; Task 4 → docs.
- **Backward compatibility:** with no `--labels`, `resolve_labels` returns `None`, `Report.labels` stays `None`, and every renderer keeps its `default_name`/`#index` behavior. Direct `Report(...)` construction is unaffected.
- **Error handling:** bad `@file` / malformed JSON / out-of-range index all raise `ValueError`, surfaced by `main()` as `error: …` / exit 2 (same pattern as mode mismatch).
- **Transitions:** labels apply to phase **centers** only (a transition sits between two microphases); transition `name` stays `None`.
- **Type consistency:** `resolve_labels -> list[str | None] | None`; `Report.labels` is `list[str] | None` (None entries are allowed at runtime and handled by renderers' `or` fallbacks — no signature change needed).
- **Out of scope:** none remaining — this is the final roadmap phase.
