"""CSV and JSON renderers (series rows or event rows)."""

from __future__ import annotations

import csv
import json
import sys

from . import register


@register("csv", modes={"series", "events"})
def render_csv(report, out):
    f = open(out, "w", newline="") if out else sys.stdout
    s = report.scheme
    try:
        w = csv.writer(f)
        if report.mode == "events":
            w.writerow(["time", "target_angle_deg", "kind", "microphase_index",
                        "name", "divisions", "step_deg"])
            for e in report.events or []:
                w.writerow([e.when.isoformat(), f"{e.angle_deg:.6f}", e.kind,
                            e.index, e.name or "", s.divisions, f"{s.step_deg:.6f}"])
        else:
            w.writerow(["time", "phase_angle_deg", "microphase_index",
                        "divisions", "step_deg"])
            for p in report.samples or []:
                w.writerow([p.when.isoformat(), f"{p.angle_deg:.6f}", p.microphase,
                            s.divisions, f"{s.step_deg:.6f}"])
    finally:
        if out:
            f.close()


@register("json", modes={"series", "events"})
def render_json(report, out):
    s = report.scheme
    payload = {"scheme": {"divisions": s.divisions, "step_deg": s.step_deg}}
    if report.mode == "events":
        payload["events"] = [
            {"time": e.when.isoformat(), "angle_deg": e.angle_deg, "kind": e.kind,
             "index": e.index, "name": e.name}
            for e in report.events or []
        ]
    else:
        payload["samples"] = [
            {"time": p.when.isoformat(), "angle_deg": p.angle_deg, "microphase": p.microphase}
            for p in report.samples or []
        ]
    if out:
        with open(out, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
