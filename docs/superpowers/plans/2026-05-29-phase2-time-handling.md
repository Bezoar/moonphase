# Phase 2: Time Handling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve a single display timezone per run, interpret bare dates as local time, emit DST-aware ISO-8601-with-offset output, and state the timezone explicitly on every time-bearing render.

**Architecture:** Add `displaytz.py` with a `DisplayZone` value object (resolve / to_utc / to_display / caption). The CLI resolves the zone from `--start`, converts the range to UTC for the engine (which stays UTC-only), and stores the zone on `Report.tz`. Renderers convert each instant via `report.tz.to_display(...)` and add a caption from `report.tz.caption(...)`. Local conversion uses `datetime.astimezone()` (no arg) so DST is correct per instant with no new dependency.

**Tech Stack:** Python ≥3.10 stdlib `datetime` (+ `time.tzset`/`TZ` env in tests for deterministic local-zone tests), numpy, matplotlib, pytest, ruff.

---

## Scope

Implements spec `docs/specs/primary.md` §5.4 (F4t.1–F4t.4) and §5.6 F6.4 (timezone captions), plus the N6 determinism caveat. **Phase 3 (heatmap/almanac/lunar/`--tint`) and Phase 4 (`--labels`) remain out of scope.**

Phase 1 currently emits UTC and `Report.tz` defaults to `timezone.utc`. This phase changes `Report.tz` to a `DisplayZone` (default = UTC, so existing direct-construction call sites keep UTC behavior).

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/moonphase/displaytz.py` | create | `DisplayZone`: resolve, to_utc, to_display, caption |
| `src/moonphase/report.py` | modify | `tz: DisplayZone` (default UTC) |
| `src/moonphase/cli.py` | modify | naive-preserving `_parse_date`; resolve zone; convert range to UTC; set `Report.tz` |
| `src/moonphase/renderers/data.py` | modify | display-tz timestamps; JSON `timezone` field |
| `src/moonphase/renderers/terminal.py` | modify | display-tz timestamps + day grouping; tz caption in header |
| `src/moonphase/renderers/chart.py` | modify | tz caption in the title |
| `tests/test_displaytz.py` | create | zone resolution, conversion, captions, DST |
| `tests/test_report.py` | modify | `tz` is a `DisplayZone` |
| `tests/test_cli.py` | modify | fixed-offset and local-date integration |
| `tests/test_renderers.py` | modify | JSON `timezone`, csv offsets, terminal caption |

---

## Task 1: `DisplayZone` value object

**Files:**
- Create: `src/moonphase/displaytz.py`
- Test: `tests/test_displaytz.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_displaytz.py`:

```python
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from moonphase.displaytz import DisplayZone


@contextmanager
def _tz(name):
    """Force the system local timezone for the duration of the block (POSIX)."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_resolve_aware_utc():
    z = DisplayZone.resolve(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert z.kind == "utc"
    assert z.caption() == "UTC"


def test_resolve_aware_fixed_offset():
    z = DisplayZone.resolve(datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-8))))
    assert z.kind == "fixed"
    assert z.caption() == "UTC-08:00"


def test_resolve_naive_is_local():
    with _tz("America/Los_Angeles"):
        z = DisplayZone.resolve(datetime(2026, 1, 1))  # naive
        assert z.kind == "local"


def test_to_utc_fixed_offset_interprets_wall_clock():
    z = DisplayZone("fixed", timedelta(hours=-8))
    got = z.to_utc(datetime(2026, 1, 1, 0, 0))  # naive midnight in UTC-08:00
    assert got == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_to_utc_local_interprets_wall_clock():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        # Jan 1 2026 is PST (UTC-8): local midnight -> 08:00 UTC
        got = z.to_utc(datetime(2026, 1, 1, 0, 0))
        assert got == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_to_display_local_is_dst_aware():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        winter = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)  # PST -08
        summer = datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)  # PDT -07
        assert z.to_display(winter).utcoffset() == timedelta(hours=-8)
        assert z.to_display(summer).utcoffset() == timedelta(hours=-7)


def test_caption_local_notes_dst_change():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
        jul = datetime(2026, 7, 1, tzinfo=timezone.utc)
        same = z.caption(jan, jan)
        spanning = z.caption(jan, jul)
        assert "PST" in same and "DST" not in same
        assert "DST changes within range" in spanning


def test_utc_roundtrip_and_caption():
    z = DisplayZone.utc()
    dt = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)
    assert z.to_display(dt) == dt
    assert z.to_utc(datetime(2026, 5, 1, 12)) == dt  # naive read as UTC
    assert z.caption() == "UTC"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_displaytz.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonphase.displaytz'`

- [ ] **Step 3: Implement `displaytz.py`**

Create `src/moonphase/displaytz.py`:

```python
"""Display-timezone resolution, conversion, and human captions.

Phase 1 emitted UTC. This module resolves a single display timezone per run:
(1) an explicit offset on the start datetime, else (2) the system-local zone,
else (3) UTC. All computation stays in UTC; only output is converted to the
display zone. Local conversion uses ``datetime.astimezone()`` with no argument,
so DST is handled correctly per instant without any extra dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _fmt_offset(off: timedelta) -> str:
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


class DisplayZone:
    """How output timestamps are localized and labeled.

    ``kind`` is "utc", "fixed" (a constant offset), or "local" (the system
    zone, converted per-instant so DST is correct).
    """

    def __init__(self, kind: str, offset: timedelta | None = None):
        if kind not in ("utc", "fixed", "local"):
            raise ValueError(f"bad DisplayZone kind {kind!r}")
        self.kind = kind
        self._tz = (timezone.utc if kind == "utc"
                    else timezone(offset) if kind == "fixed"
                    else None)

    @classmethod
    def utc(cls) -> "DisplayZone":
        return cls("utc")

    @classmethod
    def resolve(cls, start: datetime) -> "DisplayZone":
        """Aware ``start`` -> its offset (UTC if zero). Naive ``start`` ->
        system-local if discernible, else UTC."""
        if start.tzinfo is not None:
            off = start.utcoffset() or timedelta(0)
            return cls("utc") if off == timedelta(0) else cls("fixed", off)
        try:
            local = datetime.now().astimezone().tzinfo
        except Exception:
            local = None
        return cls("local") if local is not None else cls("utc")

    def to_utc(self, dt: datetime) -> datetime:
        """Interpret ``dt`` in this zone; return the UTC-aware instant.

        An aware ``dt`` is converted directly. A naive ``dt`` is read as a
        wall-clock time in this zone.
        """
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        if self.kind == "utc":
            return dt.replace(tzinfo=timezone.utc)
        if self.kind == "fixed":
            return dt.replace(tzinfo=self._tz).astimezone(timezone.utc)
        return dt.astimezone(timezone.utc)  # local: naive read as system-local

    def to_display(self, dt: datetime) -> datetime:
        """Convert a UTC-aware instant into this display zone, DST-aware."""
        if self.kind == "local":
            return dt.astimezone()
        return dt.astimezone(self._tz)

    def caption(self, start_utc: datetime | None = None,
                end_utc: datetime | None = None) -> str:
        """Human label, e.g. 'UTC', 'UTC-08:00', 'local time (PST)',
        'local time (PST/PDT, DST changes within range)'."""
        if self.kind == "utc":
            return "UTC"
        if self.kind == "fixed":
            return "UTC" + _fmt_offset(self._tz.utcoffset(None))
        if start_utc is None:
            return "local time"
        a = start_utc.astimezone().tzname()
        b = (end_utc or start_utc).astimezone().tzname()
        if a == b:
            return f"local time ({a})"
        return f"local time ({a}/{b}, DST changes within range)"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_displaytz.py -v`
Expected: PASS (8 tests). (If the runner's OS lacks the `America/Los_Angeles` zone, that's a CI concern outside this task; on macOS/Linux it is present.)

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/displaytz.py tests/test_displaytz.py
git commit -m "feat: DisplayZone for timezone resolution, conversion, and captions"
```

---

## Task 2: `Report.tz` becomes a `DisplayZone`

**Files:**
- Modify: `src/moonphase/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Update the report test**

Replace the body of `test_report_defaults` in `tests/test_report.py` so the tz assertion expects a `DisplayZone` (keep the other test unchanged). The file becomes:

```python
from moonphase.displaytz import DisplayZone
from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report


def test_report_defaults():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.mode == "series"
    assert r.events is None
    assert isinstance(r.tz, DisplayZone) and r.tz.kind == "utc"  # default until set by CLI
    assert r.labels is None          # default until Phase 4


def test_report_is_frozen():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="events", events=[])
    try:
        r.mode = "series"
    except Exception as e:
        assert "frozen" in type(e).__name__.lower() or "attribute" in str(e).lower()
    else:
        raise AssertionError("Report should be frozen")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: FAIL (`r.tz` is still `timezone.utc`, not a `DisplayZone`).

- [ ] **Step 3: Update `report.py`**

Replace the entire contents of `src/moonphase/report.py` with:

```python
"""The frozen context object every renderer consumes."""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import PhaseSample
from .displaytz import DisplayZone
from .events import PhaseEvent
from .microphase import MicrophaseScheme

_UTC = DisplayZone.utc()


@dataclass(frozen=True)
class Report:
    scheme: MicrophaseScheme
    mode: str                                  # "series" | "events"
    samples: list[PhaseSample] | None = None   # present iff mode == "series"
    events: list[PhaseEvent] | None = None      # exact events (overlay or primary)
    tz: DisplayZone = _UTC                      # display timezone (UTC by default)
    labels: list[str] | None = None            # custom names; None until Phase 4
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: PASS (2 tests). Then `.venv/bin/python -m pytest -q` — the full suite must still pass (renderers default to UTC, so existing renderer/cli tests are unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/report.py tests/test_report.py
git commit -m "feat: Report.tz is now a DisplayZone (default UTC)"
```

---

## Task 3: CLI resolves and applies the display timezone

**Files:**
- Modify: `src/moonphase/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_cli.py`:

```python
import os
import time
from contextlib import contextmanager


@contextmanager
def _force_tz(name):
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_main_fixed_offset_start_propagates_to_output(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "ev.json"
    rc = cli_mod.main([
        "--start", "2026-01-01T00:00:00-08:00", "--end", "2026-01-31T00:00:00-08:00",
        "--divisions", "4", "--mode", "events", "--format", "json", "--out", str(out),
    ])
    assert rc == 0
    import json
    payload = json.loads(out.read_text())
    assert payload["timezone"] == "UTC-08:00"
    assert payload["events"][0]["time"].endswith("-08:00")


def test_main_bare_date_uses_local(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    with _force_tz("America/Los_Angeles"):
        out = tmp_path / "ev2.json"
        rc = cli_mod.main([
            "--start", "2026-01-01", "--end", "2026-01-31",
            "--divisions", "4", "--mode", "events", "--format", "json", "--out", str(out),
        ])
        assert rc == 0
        import json
        payload = json.loads(out.read_text())
        assert "local time" in payload["timezone"]
        assert payload["events"][0]["time"].endswith("-08:00")  # Jan -> PST
```

(The `_LinearEph` helper and `cli_mod` import already exist in this file from Phase 1.)

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `_parse_date` currently forces naive input to UTC, and `main()` does not resolve a zone or set `Report.tz`/the JSON `timezone` field (the JSON field arrives in Task 4, so these tests stay red until Task 4; that is expected — proceed with Step 3 here and they go green after Task 4). To keep this task self-contained and green, ALSO complete Task 4's `data.py` change is NOT required here — instead, verify failure is due to tz wiring by checking the offsets, and leave the JSON-field assertions to run green after Task 4.

> Implementer note: run these two tests at the END of Task 4, not Task 3. In Task 3, verify the wiring with the lighter check in Step 4 below; do not commit failing tests. Move the two tests above into the file but mark them with `@pytest.mark.skip(reason="enabled in Task 4")` here, and REMOVE the skip in Task 4 Step 1.

- [ ] **Step 3: Implement the CLI wiring**

In `src/moonphase/cli.py`:

(a) Add the import:
```python
from .displaytz import DisplayZone
```

(b) Replace `_parse_date` so naive input stays naive (no forced UTC):
```python
def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD or full ISO 8601. Naive input stays naive (its zone is
    resolved later); ISO input with an offset stays aware."""
    try:
        if "T" in s or " " in s:
            return datetime.fromisoformat(s)
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"bad date {s!r}: {e}") from e
```

(c) In `build_parser()`, update the `--start`/`--end` help text:
```python
    p.add_argument("--start", type=_parse_date, required=True,
                   help="start date (YYYY-MM-DD or ISO 8601); bare dates use local time")
    p.add_argument("--end", type=_parse_date, required=True,
                   help="end date (YYYY-MM-DD or ISO 8601); bare dates use local time")
```

(d) In `main()`, resolve the zone and convert the range to UTC before calling the engine, and pass the zone to `Report`. Replace the part of `main()` from the `eph = PhaseEphemeris(...)` line to the end with:
```python
    zone = DisplayZone.resolve(args.start)
    start_utc = zone.to_utc(args.start)
    end_utc = zone.to_utc(args.end)

    eph = PhaseEphemeris(kernel_path=args.ephemeris)

    if mode == "events":
        # --sample does not apply in events mode (events are root-found, not sampled)
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="events", events=events, tz=zone)
    else:
        samples = build_series(start_utc, end_utc, scheme,
                               sample_step=args.sample, ephemeris=eph)
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="series", samples=samples,
                        events=events, tz=zone)

    renderers.get(args.format)(report, args.out)
    return 0
```

- [ ] **Step 4: Verify wiring (lighter check), then full suite**

Run this probe and confirm the offset propagates (no JSON field yet — that's Task 4):
```bash
.venv/bin/python -c "
import moonphase.cli as c, types, numpy as np
from datetime import datetime, timezone
c.PhaseEphemeris=lambda **k: types.SimpleNamespace(phase_angles_deg=lambda ts: np.array([(12.0*(t-datetime(2026,1,1,tzinfo=timezone.utc)).total_seconds()/86400)%360 for t in ts]))
from moonphase.displaytz import DisplayZone
print(DisplayZone.resolve(datetime(2026,1,1)).kind, DisplayZone.resolve(datetime(2026,1,1,tzinfo=timezone(__import__('datetime').timedelta(hours=-8)))).caption())
"
```
Expected: prints `local UTC-08:00` (or `utc UTC-08:00` if run where no local zone is discernible).

Run: `.venv/bin/python -m pytest -q` — full suite green (the two skipped tests show as skipped).

- [ ] **Step 5: Commit**

```bash
git add src/moonphase/cli.py tests/test_cli.py
git commit -m "feat: CLI resolves display timezone from --start; range computed in UTC"
```

---

## Task 4: Renderers emit display-tz timestamps + captions

**Files:**
- Modify: `src/moonphase/renderers/data.py`, `terminal.py`, `chart.py`
- Test: `tests/test_renderers.py`, `tests/test_cli.py`

- [ ] **Step 1: Update/extend the tests**

In `tests/test_cli.py`, REMOVE the `@pytest.mark.skip(...)` decorators added to `test_main_fixed_offset_start_propagates_to_output` and `test_main_bare_date_uses_local` in Task 3 (they should now run for real).

In `tests/test_renderers.py`, add these tests (keep all existing ones; `Report`, `S4`, `T0`, `_events_report`, `_series_report` already exist):

```python
from moonphase.displaytz import DisplayZone


def test_json_has_timezone_field(tmp_path):
    out = tmp_path / "e.json"
    renderers.get("json")(_events_report(), str(out))
    payload = json.load(out.open())
    assert payload["timezone"] == "UTC"  # default zone


def test_json_fixed_offset_timestamps_and_caption(tmp_path):
    z = DisplayZone("fixed", __import__("datetime").timedelta(hours=-8))
    r = Report(scheme=S4, mode="events", events=_events_report().events, tz=z)
    out = tmp_path / "e2.json"
    renderers.get("json")(r, str(out))
    payload = json.load(out.open())
    assert payload["timezone"] == "UTC-08:00"
    assert payload["events"][0]["time"].endswith("-08:00")


def test_csv_timestamps_carry_offset(tmp_path):
    out = tmp_path / "s.csv"
    renderers.get("csv")(_series_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[1][0].endswith("+00:00")  # default UTC


def test_terminal_header_states_timezone(tmp_path):
    out = tmp_path / "e.txt"
    renderers.get("terminal")(_events_report(), str(out))
    assert "UTC" in out.read_text().splitlines()[0]
```

- [ ] **Step 2: Run to verify failures**

Run: `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -v`
Expected: the new tests FAIL (no `timezone` field; timestamps still raw `.isoformat()` on UTC; no terminal caption).

- [ ] **Step 3: Update `data.py`**

Replace the entire contents of `src/moonphase/renderers/data.py` with:

```python
"""CSV and JSON renderers (series rows or event rows)."""

from __future__ import annotations

import csv
import json
import sys

from . import register


def _span(report):
    items = report.events if report.mode == "events" else report.samples
    items = items or []
    return (items[0].when, items[-1].when) if items else (None, None)


@register("csv", modes={"series", "events"})
def render_csv(report, out):
    f = open(out, "w", newline="") if out else sys.stdout
    s = report.scheme
    tz = report.tz

    def t(when):
        return tz.to_display(when).isoformat()

    try:
        w = csv.writer(f)
        if report.mode == "events":
            w.writerow(["time", "target_angle_deg", "kind", "microphase_index",
                        "name", "divisions", "step_deg"])
            for e in report.events or []:
                w.writerow([t(e.when), f"{e.angle_deg:.6f}", e.kind,
                            e.index, e.name or "", s.divisions, f"{s.step_deg:.6f}"])
        else:
            w.writerow(["time", "phase_angle_deg", "microphase_index",
                        "divisions", "step_deg"])
            for p in report.samples or []:
                w.writerow([t(p.when), f"{p.angle_deg:.6f}", p.microphase,
                            s.divisions, f"{s.step_deg:.6f}"])
    finally:
        if out:
            f.close()


@register("json", modes={"series", "events"})
def render_json(report, out):
    s = report.scheme
    tz = report.tz
    start_utc, end_utc = _span(report)

    def t(when):
        return tz.to_display(when).isoformat()

    payload = {
        "scheme": {"divisions": s.divisions, "step_deg": s.step_deg},
        "timezone": tz.caption(start_utc, end_utc),
    }
    if report.mode == "events":
        payload["events"] = [
            {"time": t(e.when), "angle_deg": e.angle_deg, "kind": e.kind,
             "index": e.index, "name": e.name}
            for e in report.events or []
        ]
    else:
        payload["samples"] = [
            {"time": t(p.when), "angle_deg": p.angle_deg, "microphase": p.microphase}
            for p in report.samples or []
        ]
    if out:
        with open(out, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
```

- [ ] **Step 4: Update `terminal.py`**

Replace the entire contents of `src/moonphase/renderers/terminal.py` with:

```python
"""Terminal view: a per-day glyph grid (series) or an event list (events)."""

from __future__ import annotations

import sys
from collections import defaultdict

from . import register

_GLYPHS = "🌑🌒🌓🌔🌕🌖🌗🌘"


def _glyph(idx: int, divisions: int) -> str:
    return _GLYPHS[int((idx / divisions) * len(_GLYPHS)) % len(_GLYPHS)]


def _span(report):
    items = report.events if report.mode == "events" else report.samples
    items = items or []
    return (items[0].when, items[-1].when) if items else (None, None)


@register("terminal", modes={"series", "events"})
def render(report, out):
    f = open(out, "w") if out else sys.stdout
    s = report.scheme
    tz = report.tz
    start_utc, end_utc = _span(report)
    caption = tz.caption(start_utc, end_utc)
    try:
        header = f"# {s.divisions} microphases, {s.step_deg:.3f}° per slice · times in {caption}\n"
        if report.mode == "events":
            f.write(header)
            for e in report.events or []:
                label = e.name or f"#{e.index}"
                when = tz.to_display(e.when).isoformat()
                f.write(f"{when}  {e.kind:10} {e.angle_deg:7.3f}°  {label}\n")
        else:
            by_day: dict[str, list] = defaultdict(list)
            for p in report.samples or []:
                day = tz.to_display(p.when).date().isoformat()
                by_day[day].append(p)
            f.write(header)
            for day in sorted(by_day):
                row = "".join(_glyph(p.microphase, s.divisions) for p in by_day[day])
                f.write(f"{day}  {row}\n")
    finally:
        if out:
            f.close()
```

- [ ] **Step 5: Update `chart.py`** — add the caption to the title. Make exactly these two edits:

Add a span helper near the top (after the imports, before the `@register` line):
```python
def _span(report):
    items = report.events if report.mode == "events" else report.samples
    items = items or []
    return (items[0].when, items[-1].when) if items else (None, None)
```

Replace the single `ax.set_title(...)` line with:
```python
        start_utc, end_utc = _span(report)
        caption = report.tz.caption(start_utc, end_utc)
        ax.set_title(f"Lunar microphases — {s.divisions} divisions ({step:.3f}° each)\n"
                     f"times in {caption}", fontsize=10)
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -v` (all green, including the un-skipped CLI tests).
Run: `.venv/bin/python -m pytest -q` (full suite green).

- [ ] **Step 7: Commit**

```bash
git add src/moonphase/renderers/data.py src/moonphase/renderers/terminal.py src/moonphase/renderers/chart.py tests/test_renderers.py tests/test_cli.py
git commit -m "feat: render timestamps in display timezone with mandatory tz captions"
```

---

## Task 5: Docs + final verification

**Files:**
- Modify: `README.md`, `docs/specs/primary.md`

- [ ] **Step 1: Update README** — in the "Status & roadmap" section, move time handling from planned to implemented, and update the "Times are UTC" callouts.

In `README.md`:
- Change both `> **Times are UTC** for now...` callouts to:
  `> **Timezones:** bare dates use your local time; pass an ISO offset (e.g. \`2026-01-01T00:00-08:00\` or \`...Z\`) to pin a zone. Output carries the offset and every render states its timezone.`
- In "Status & roadmap", change the Phase 1 paragraph's lead to note Phase 2 is now done, and remove **Phase 2 — Time handling** from the "Planned" list (leaving Phase 3 and Phase 4).

- [ ] **Step 2: Update the spec** — in `docs/specs/primary.md`, append " *(implemented in Phase 2)*" to the §5.4 heading line (the `### 5.4 Time handling` line becomes `### 5.4 Time handling *(implemented in Phase 2)*`). No requirement text changes.

- [ ] **Step 3: Full verification**

Run: `.venv/bin/python -m pytest -q` — all green.
Run: `.venv/bin/ruff check src tests` — clean.
Run an end-to-end smoke (no kernel) confirming a local-time JSON caption:
```bash
TZ=America/Los_Angeles .venv/bin/python -c "
import moonphase.cli as c, types, numpy as np
from datetime import datetime, timezone
c.PhaseEphemeris=lambda **k: types.SimpleNamespace(phase_angles_deg=lambda ts: np.array([(12.0*(t-datetime(2026,1,1,tzinfo=timezone.utc)).total_seconds()/86400)%360 for t in ts]))
c.main(['--start','2026-01-01','--end','2026-12-31','--divisions','4','--mode','events','--format','json','--out','/tmp/mp_smoke.json'])
import json; p=json.load(open('/tmp/mp_smoke.json')); print('timezone:', p['timezone']); print('first event time:', p['events'][0]['time'])
"
```
Expected: a `local time (PST/PDT, DST changes within range)` caption and a first event time ending in `-08:00`.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/specs/primary.md
git commit -m "docs: mark Phase 2 time handling implemented; update README timezone notes"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** Task 1 → F4t.1/F4t.3 conversion + caption primitives; Task 3 → F4t.1/F4t.2 (resolution + bare-date-as-local) and "internals in UTC"; Task 4 → F4t.3 (display-tz ISO-offset output, JSON `timezone` field, day grouping) + F6.4 (mandatory captions); Task 5 → N6 caveat already in spec, docs updated.
- **Backward compatibility:** `Report.tz` defaults to UTC, so every existing test that builds a `Report` directly keeps UTC output; only the CLI sets a non-UTC zone. The Phase 1 csv header/row tests are unaffected (headers unchanged; timestamps gain `+00:00` which those tests don't assert on).
- **Type consistency:** `DisplayZone` API (`resolve`, `to_utc`, `to_display`, `caption`, `.kind`) is used identically in `cli.py`, `report.py`, all three renderers, and tests.
- **Determinism note:** local-zone tests force `TZ` + `time.tzset()` for reproducibility; production local resolution depends on the host zone (documented in spec N6).
- **Not in scope:** `heatmap`/`almanac`/lunar/`--tint` (Phase 3), `--labels` (Phase 4), an explicit `--timezone` override (roadmap).
