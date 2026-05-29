"""Terminal calendar view: one row per day, one glyph per sample."""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import Iterable

from ..calendar import PhaseSample
from ..microphase import MicrophaseScheme
from . import register

# Eight-step phase glyphs; for finer schemes we cycle a gradient by index%len.
_GLYPHS = "🌑🌒🌓🌔🌕🌖🌗🌘"


def _glyph(idx: int, divisions: int) -> str:
    bucket = int((idx / divisions) * len(_GLYPHS)) % len(_GLYPHS)
    return _GLYPHS[bucket]


@register("terminal")
def render(samples: Iterable[PhaseSample], scheme: MicrophaseScheme, out: str | None) -> None:
    by_day: dict[str, list[PhaseSample]] = defaultdict(list)
    for s in samples:
        by_day[s.when.date().isoformat()].append(s)

    f = open(out, "w") if out else sys.stdout
    try:
        f.write(f"# {scheme.divisions} microphases, {scheme.step_deg:.3f}° per slice\n")
        for day in sorted(by_day):
            row = "".join(_glyph(s.microphase, scheme.divisions) for s in by_day[day])
            f.write(f"{day}  {row}\n")
    finally:
        if out:
            f.close()
