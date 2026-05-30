"""Matplotlib strip-chart renderer. Output format is inferred from extension
(.png, .svg, .pdf, ...) — matplotlib handles all of them uniformly."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from ..calendar import PhaseSample
from ..microphase import MicrophaseScheme
from . import register


@register("chart", modes={"series", "events"})
def render(samples: Iterable[PhaseSample], scheme: MicrophaseScheme, out: str | None) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    samples = list(samples)
    if not samples:
        raise ValueError("no samples to render")

    times = [s.when for s in samples]
    angles = np.array([s.angle_deg for s in samples])

    fig, ax = plt.subplots(figsize=(12, 3.5))
    sc = ax.scatter(times, angles, c=angles, cmap="twilight", s=4, marker="s")

    for k in range(scheme.divisions + 1):
        ax.axhline(k * scheme.step_deg, color="black", lw=0.2, alpha=0.3)

    ax.set_ylim(0, 360)
    ax.set_ylabel("Sun–Moon elongation (°)")
    ax.set_title(
        f"Lunar microphases — {scheme.divisions} divisions "
        f"({scheme.step_deg:.3f}° each)"
    )
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    fig.colorbar(sc, ax=ax, label="phase angle")
    fig.tight_layout()

    if out:
        fig.savefig(out, dpi=150)
    else:
        plt.show()
    plt.close(fig)
