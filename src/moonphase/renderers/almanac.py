"""Almanac moon-disk ribbon: rendered moon disks at each phase-center event,
with transition points marked between them."""

from __future__ import annotations

from ..moondisk import lit_polygon
from . import register

_DARK = "#15171f"
_LIT = "#f4f1e6"
_OUT = "#717a90"
_TRANS = "#d98324"


def _interp_x(when, centers):
    """X position for a transition time, interpolated between bounding centers
    (centers are drawn at integer x = their list index)."""
    for i in range(len(centers) - 1):
        a, b = centers[i].when, centers[i + 1].when
        if a <= when <= b and b > a:
            return i + (when - a) / (b - a)
    return None


@register("almanac", modes={"events"})
def render(report, out):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon

    centers = [e for e in (report.events or []) if e.kind == "center"]
    transitions = [e for e in (report.events or []) if e.kind == "transition"]
    if not centers:
        raise ValueError("no phase-center events to render")

    tz = report.tz
    n = len(centers)
    fig, ax = plt.subplots(figsize=(min(2.0 + 1.7 * n, 26), 3.2))
    try:
        r = 0.34
        for i, e in enumerate(centers):
            ax.add_patch(Circle((i, 0), r, facecolor=_DARK, edgecolor=_OUT, lw=1, zorder=2))
            poly = lit_polygon(i, 0, r, e.angle_deg)
            if poly:
                ax.add_patch(Polygon(poly, closed=True, facecolor=_LIT,
                                     edgecolor="none", zorder=3))
            ax.add_patch(Circle((i, 0), r, fill=False, edgecolor=_OUT, lw=1, zorder=4))
            local = tz.to_display(e.when)
            ax.text(i, -0.60, e.name or f"#{e.index}", ha="center", va="top",
                    fontsize=9, fontweight="bold")
            ax.text(i, -0.78, local.strftime("%b %d %H:%M"), ha="center", va="top",
                    fontsize=7.5, color="#888")
        for tr in transitions:
            x = _interp_x(tr.when, centers)
            if x is not None:
                ax.plot([x, x], [-0.42, 0.42], color=_TRANS, ls="--", lw=1.2, zorder=1)

        ax.set_xlim(-0.7, n - 0.3)
        ax.set_ylim(-1.0, 0.7)
        ax.axis("off")
        start_utc, end_utc = report.span()
        ax.set_title(f"Lunar almanac — {report.scheme.divisions} divisions · "
                     f"times in {tz.caption(start_utc, end_utc)}", fontsize=10)
        fig.tight_layout()
        if out:
            fig.savefig(out, dpi=150)
        else:
            plt.show()
    finally:
        plt.close(fig)
