"""Matplotlib strip-chart: elongation vs time, centered phase bands, named
phases on the left axis, degrees on the right, with on-curve event markers."""

from __future__ import annotations

import numpy as np

from ..naming import default_name
from ..theme import style_axes, theme_of
from . import register


@register("chart", modes={"series", "events"})
def render(report, out):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    s = report.scheme
    step = s.step_deg
    theme = theme_of(report)
    fig, ax = plt.subplots(figsize=(12, 3.5))
    try:
        # plot display-zone wall-clock (naive) so the x-axis matches the caption
        def _disp(when):
            return report.tz.to_display(when).replace(tzinfo=None)

        sc = None
        if report.mode == "series":
            samples = report.samples or []
            if not samples:
                raise ValueError("no samples to render")
            times = [_disp(p.when) for p in samples]
            angles = np.array([p.angle_deg for p in samples])
            sc = ax.scatter(times, angles, c=angles, cmap="twilight",
                            vmin=0, vmax=360, s=4, marker="s")
        elif not (report.events or []):
            raise ValueError("no events to render")

        # centered phase bands (band k spans (k-0.5)..(k+0.5)*step; band 0 wraps)
        for k in range(0, s.divisions, 2):
            lo, hi = (k - 0.5) * step, (k + 0.5) * step
            if lo < 0:
                ax.axhspan(0, hi, color=theme.band, alpha=theme.band_alpha)
                ax.axhspan(360 + lo, 360, color=theme.band, alpha=theme.band_alpha)
            else:
                ax.axhspan(lo, hi, color=theme.band, alpha=theme.band_alpha)

        # on-curve event markers: filled dots (colored by phase) = centers,
        # open orange rings = transitions
        for e in report.events or []:
            x, y = _disp(e.when), e.angle_deg
            if e.kind == "transition":
                ax.scatter([x], [y], s=34, facecolors="none",
                           edgecolors=theme.transition, linewidths=1.3, zorder=5)
            else:
                ax.scatter([x], [y], c=[y], cmap="twilight", vmin=0, vmax=360,
                           s=30, edgecolors=theme.fg, linewidths=0.6, zorder=6)

        ax.set_ylim(0, 360)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.set_yticks([0, 90, 180, 270, 360])
        ax.set_ylabel("Sun–Moon elongation (°)")
        axL = ax.secondary_yaxis("left")
        axL.set_yticks([(k * step) % 360 for k in range(s.divisions)])
        labels = report.labels
        axL.set_yticklabels([
            (labels[k] if labels else default_name(k, s)) or f"{(k * step) % 360:.0f}°"
            for k in range(s.divisions)
        ])

        start_utc, end_utc = report.span()
        caption = report.tz.caption(start_utc, end_utc)
        ax.set_title(f"Lunar microphases — {s.divisions} divisions ({step:.3f}° each)\n"
                     f"times in {caption}", fontsize=10)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        # daily / weekly minor tick marks for a calendar feel (range-adaptive)
        span_days = (end_utc - start_utc).days if (start_utc and end_utc) else 0
        if 0 < span_days <= 120:
            ax.xaxis.set_minor_locator(mdates.DayLocator())
        elif span_days <= 800:
            ax.xaxis.set_minor_locator(mdates.DayLocator(interval=7))

        style_axes(fig, ax, theme)
        axL.tick_params(colors=theme.fg)
        axL.spines["left"].set_color(theme.spine)
        if sc is not None:
            cbar = fig.colorbar(sc, ax=ax, label="phase angle", pad=0.08)
            cbar.ax.yaxis.set_tick_params(color=theme.fg, labelcolor=theme.fg)
            cbar.set_label("phase angle", color=theme.fg)
            cbar.outline.set_edgecolor(theme.spine)

        fig.tight_layout()
        if out:
            fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
        else:
            plt.show()
    finally:
        plt.close(fig)
