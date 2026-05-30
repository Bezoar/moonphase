"""Calendar heatmap. Gregorian (months × days) or lunar (one phase-aligned
strip per lunation). Tinted by illuminated fraction or by microphase index."""

from __future__ import annotations

from datetime import date

from ..heatmap_layout import day_cells, lunations, principal_phase_days
from ..moondisk import illuminated_fraction, lit_polygon
from . import register

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _tint(angle, microphase, scheme, mode):
    if mode == "index":
        import matplotlib.colors as mc
        return mc.hsv_to_rgb((microphase / scheme.divisions, 0.55, 0.72))
    f = illuminated_fraction(angle)
    v = 0.08 + 0.88 * f
    return (v, v, min(1.0, v + 0.05))


def _opts(report):
    o = report.options or {}
    return (o.get("tint", "illumination"), o.get("calendar", "gregorian"),
            o.get("lunar_anchor", "new"))


def _draw_marker(ax, cx, cy, rr, principal_index):
    from matplotlib.patches import Circle, Polygon
    ax.add_patch(Circle((cx, cy), rr * 1.35, facecolor="#0c0e14",
                        edgecolor="#aab2c4", lw=0.6, zorder=4))
    ang = principal_index * 90.0
    ax.add_patch(Circle((cx, cy), rr, facecolor="#15171f", edgecolor="none", zorder=5))
    poly = lit_polygon(cx, cy, rr, ang)
    if poly:
        ax.add_patch(Polygon(poly, closed=True, facecolor="#f4f1e6",
                            edgecolor="none", zorder=6))
    ax.add_patch(Circle((cx, cy), rr, fill=False, edgecolor="#cdd4e4", lw=0.8, zorder=7))


@register("heatmap", modes={"series"})
def render(report, out):
    import matplotlib.pyplot as plt

    samples = report.samples or []
    if not samples:
        raise ValueError("no samples to render")
    tint, calendar, anchor = _opts(report)
    caption = report.tz.caption(*report.span())

    if calendar == "lunar":
        _render_lunar(plt, report, samples, tint, anchor, caption, out)
    else:
        _render_gregorian(plt, report, samples, tint, caption, out)


def _render_gregorian(plt, report, samples, tint, caption, out):
    scheme = report.scheme
    cells = {d: (a, i) for d, a, i in day_cells(samples, report.tz)}
    marks = principal_phase_days(samples, report.tz)
    months = sorted({d[:7] for d in cells})          # 'YYYY-MM', only months with data
    fig, ax = plt.subplots(figsize=(11, 0.6 + 0.42 * len(months)))
    try:
        for row, ym in enumerate(months):
            y, m = ym[:4], int(ym[5:7])
            ax.text(-0.6, row + 0.5, f"{_MON[m - 1]} {y}", ha="right", va="center",
                    fontsize=7)
            ndays = (date(int(y) + (m // 12), (m % 12) + 1, 1)
                     - date(int(y), m, 1)).days
            for dd in range(1, ndays + 1):
                key = f"{y}-{m:02d}-{dd:02d}"
                if key not in cells:
                    continue
                a, i = cells[key]
                ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                             facecolor=_tint(a, i, scheme, tint), edgecolor="none"))
                if key in marks:
                    _draw_marker(ax, dd - 0.53, row + 0.47, 0.30, marks[key])
        ax.set_xlim(-0.5, 31)
        ax.set_ylim(len(months), -0.5)
        ax.set_xticks([0.5, 9.5, 19.5, 29.5])
        ax.set_xticklabels(["1", "10", "20", "30"], fontsize=7)
        ax.set_yticks([])
        years = sorted({d[:4] for d in cells})
        ax.set_title(f"{', '.join(years)} — {scheme.divisions} microphases · "
                     f"tint: {tint} · times in {caption}", fontsize=10)
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _render_lunar(plt, report, samples, tint, anchor, caption, out):
    scheme = report.scheme
    segs = lunations(samples, report.tz, anchor)
    if not segs:
        raise ValueError("no complete lunations in range for the lunar layout")
    opp = "full" if anchor == "new" else "new"
    cols = 64
    fig, ax = plt.subplots(figsize=(11, 0.6 + 0.5 * len(segs)))
    try:
        for r, seg in enumerate(segs):
            for c in range(cols):
                frac = c / cols
                ang = (frac * 360.0 + (0 if anchor == "new" else 180.0)) % 360.0
                ax.add_patch(plt.Rectangle((c, r), 1.02, 0.9,
                             facecolor=_tint(ang, int(ang / scheme.step_deg + 0.5)
                                             % scheme.divisions, scheme, tint),
                             edgecolor="none"))
            ax.text(-1, r + 0.45, f"{anchor.title()} {seg['start']}", ha="right",
                    va="center", fontsize=7.5)
            ax.text(cols + 1, r + 0.45, seg["end"], ha="left", va="center", fontsize=7.5)
            ax.text(cols / 2, r + 1.02, f"{opp} {seg['mid']}", ha="center", va="top",
                    fontsize=6.5, color="#555")
        ax.set_xlim(-1, cols + 1)
        ax.set_ylim(len(segs) + 0.3, -0.3)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"Lunar months ({anchor}-anchored) — {scheme.divisions} microphases · "
                     f"tint: {tint} · times in {caption}", fontsize=10)
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _save(plt, fig, out):
    if out:
        fig.savefig(out, dpi=150)
    else:
        plt.show()
