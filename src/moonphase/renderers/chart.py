"""Matplotlib strip-chart: elongation vs time, centered phase bands, named
phases on the left axis, degrees on the right, with exact event overlays."""

from __future__ import annotations

import numpy as np

from ..naming import default_name
from . import register


@register("chart", modes={"series", "events"})
def render(report, out):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    s = report.scheme
    step = s.step_deg
    fig, ax = plt.subplots(figsize=(12, 3.5))

    sc = None
    if report.mode == "series":
        samples = report.samples or []
        if not samples:
            raise ValueError("no samples to render")
        times = [p.when for p in samples]
        angles = np.array([p.angle_deg for p in samples])
        sc = ax.scatter(times, angles, c=angles, cmap="twilight", s=4, marker="s")

    # centered phase bands (band k spans (k-0.5)..(k+0.5)*step; band 0 wraps)
    for k in range(0, s.divisions, 2):
        lo, hi = (k - 0.5) * step, (k + 0.5) * step
        if lo < 0:
            ax.axhspan(0, hi, color="black", alpha=0.04)
            ax.axhspan(360 + lo, 360, color="black", alpha=0.04)
        else:
            ax.axhspan(lo, hi, color="black", alpha=0.04)

    # event overlays: solid = centers, dashed orange = transitions
    for e in report.events or []:
        ax.axvline(e.when, color=("#d98324" if e.kind == "transition" else "#5b6b8a"),
                   lw=0.6, ls=("--" if e.kind == "transition" else "-"), alpha=0.7)

    ax.set_ylim(0, 360)
    # degrees on the right
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_yticks([0, 90, 180, 270, 360])
    ax.set_ylabel("Sun–Moon elongation (°)")
    # named phase centers on the left
    axL = ax.secondary_yaxis("left")
    axL.set_yticks([(k * step) % 360 for k in range(s.divisions)])
    axL.set_yticklabels([default_name(k, s) or f"{(k * step) % 360:.0f}°"
                         for k in range(s.divisions)])

    ax.set_title(f"Lunar microphases — {s.divisions} divisions ({step:.3f}° each)")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    if sc is not None:
        fig.colorbar(sc, ax=ax, label="phase angle", pad=0.08)
    fig.tight_layout()

    if out:
        fig.savefig(out, dpi=150)
    else:
        plt.show()
    plt.close(fig)
