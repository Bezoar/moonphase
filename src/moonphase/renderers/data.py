"""CSV and JSON renderers."""

from __future__ import annotations

import csv
import json
import sys
from typing import Iterable

from ..calendar import PhaseSample
from ..microphase import MicrophaseScheme
from . import register


@register("csv", modes={"series", "events"})
def render_csv(samples: Iterable[PhaseSample], scheme: MicrophaseScheme, out: str | None) -> None:
    f = open(out, "w", newline="") if out else sys.stdout
    try:
        w = csv.writer(f)
        w.writerow(["utc", "phase_angle_deg", "microphase_index", "divisions", "step_deg"])
        for s in samples:
            w.writerow([
                s.when.isoformat(),
                f"{s.angle_deg:.6f}",
                s.microphase,
                scheme.divisions,
                f"{scheme.step_deg:.6f}",
            ])
    finally:
        if out:
            f.close()


@register("json", modes={"series", "events"})
def render_json(samples: Iterable[PhaseSample], scheme: MicrophaseScheme, out: str | None) -> None:
    payload = {
        "scheme": {"divisions": scheme.divisions, "step_deg": scheme.step_deg},
        "samples": [
            {"utc": s.when.isoformat(), "angle_deg": s.angle_deg, "microphase": s.microphase}
            for s in samples
        ],
    }
    if out:
        with open(out, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
