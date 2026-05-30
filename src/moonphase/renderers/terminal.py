"""Terminal view: a per-day glyph grid (series) or an event list (events)."""

from __future__ import annotations

import sys
from collections import defaultdict

from . import register

_GLYPHS = "🌑🌒🌓🌔🌕🌖🌗🌘"


def _glyph(idx: int, divisions: int) -> str:
    return _GLYPHS[int((idx / divisions) * len(_GLYPHS)) % len(_GLYPHS)]


@register("terminal", modes={"series", "events"})
def render(report, out):
    f = open(out, "w") if out else sys.stdout
    s = report.scheme
    try:
        if report.mode == "events":
            f.write(f"# {s.divisions} microphases, {s.step_deg:.3f}° per slice\n")
            for e in report.events or []:
                label = e.name or f"#{e.index}"
                f.write(f"{e.when.isoformat()}  {e.kind:10} {e.angle_deg:7.3f}°  {label}\n")
        else:
            by_day: dict[str, list] = defaultdict(list)
            for p in report.samples or []:
                by_day[p.when.date().isoformat()].append(p)
            f.write(f"# {s.divisions} microphases, {s.step_deg:.3f}° per slice\n")
            for day in sorted(by_day):
                row = "".join(_glyph(p.microphase, s.divisions) for p in by_day[day])
                f.write(f"{day}  {row}\n")
    finally:
        if out:
            f.close()
