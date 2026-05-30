"""Calendar heatmap. Gregorian (months × days) or lunar (one phase-aligned
strip per lunation). Tinted by illuminated fraction or by microphase index."""

from __future__ import annotations

from datetime import date

from ..heatmap_layout import day_cells, lunations, principal_phase_days
from ..moondisk import illuminated_fraction, lit_polygon
from ..theme import theme_of
from . import register

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _index_color(microphase, divisions):
    import matplotlib.colors as mc
    return mc.hsv_to_rgb((microphase / divisions, 0.55, 0.72))


def _tint(angle, microphase, scheme, mode):
    if mode == "index":
        return _index_color(microphase, scheme.divisions)
    f = illuminated_fraction(angle)
    v = 0.13 + 0.82 * f          # floor keeps "new" cells visible on a dark bg
    return (v, v, min(1.0, v + 0.05))


def _opts(report):
    o = report.options or {}
    return (o.get("tint", "illumination"), o.get("calendar", "gregorian"),
            o.get("lunar_anchor", "new"))


def _draw_marker(ax, cx, cy, rr, principal_index, theme):
    from matplotlib.patches import Circle, Polygon
    ax.add_patch(Circle((cx, cy), rr * 1.35, facecolor=theme.chip,
                        edgecolor=theme.chip_ring, lw=0.6, zorder=4))
    ang = principal_index * 90.0
    ax.add_patch(Circle((cx, cy), rr, facecolor=theme.moon_dark, edgecolor="none", zorder=5))
    poly = lit_polygon(cx, cy, rr, ang)
    if poly:
        ax.add_patch(Polygon(poly, closed=True, facecolor=theme.moon_lit,
                            edgecolor="none", zorder=6))
    ax.add_patch(Circle((cx, cy), rr, fill=False, edgecolor=theme.moon_ring, lw=0.8, zorder=7))


def _index_legend(plt, ax, scheme, theme, x0, width, y, h):
    """A discrete 0..N-1 swatch strip, shown for index tint."""
    n = scheme.divisions
    sw = width / n
    for k in range(n):
        ax.add_patch(plt.Rectangle((x0 + k * sw, y), sw, h,
                                   facecolor=_index_color(k, n), edgecolor="none"))
    ax.text(x0, y - 0.3, "microphase 0", color=theme.muted, fontsize=7, ha="left", va="bottom")
    ax.text(x0 + width, y - 0.3, str(n - 1), color=theme.muted, fontsize=7, ha="right", va="bottom")


def _finish(plt, fig, ax, theme, title):
    fig.patch.set_facecolor(theme.bg)
    ax.set_facecolor(theme.bg)
    for spine in ax.spines.values():
        spine.set_color(theme.spine)
    ax.tick_params(colors=theme.fg)
    ax.set_title(title, fontsize=10, color=theme.fg)


@register("heatmap", modes={"series"})
def render(report, out):
    import matplotlib.pyplot as plt

    samples = report.samples or []
    if not samples:
        raise ValueError("no samples to render")
    tint, calendar, anchor = _opts(report)
    theme = theme_of(report)
    caption = report.tz.caption(*report.span())

    if calendar == "lunar":
        _render_lunar(plt, report, samples, tint, anchor, caption, theme, out)
    else:
        _render_gregorian(plt, report, samples, tint, caption, theme, out)


def _render_gregorian(plt, report, samples, tint, caption, theme, out):
    scheme = report.scheme
    cells = {d: (a, i) for d, a, i in day_cells(samples, report.tz)}
    marks = principal_phase_days(samples, report.tz)
    months = sorted({d[:7] for d in cells})
    legend = tint == "index"
    fig, ax = plt.subplots(figsize=(11, 0.9 + 0.42 * len(months)))
    try:
        for row, ym in enumerate(months):
            y, m = ym[:4], int(ym[5:7])
            ax.text(-0.6, row + 0.5, f"{_MON[m - 1]} {y}", ha="right", va="center",
                    fontsize=7, color=theme.fg)
            ndays = (date(int(y) + (m // 12), (m % 12) + 1, 1) - date(int(y), m, 1)).days
            for dd in range(1, ndays + 1):
                key = f"{y}-{m:02d}-{dd:02d}"
                if key not in cells:
                    continue
                a, i = cells[key]
                ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                             facecolor=_tint(a, i, scheme, tint), edgecolor="none"))
                if key in marks:
                    _draw_marker(ax, dd - 0.53, row + 0.47, 0.30, marks[key], theme)
        nrows = len(months)
        if legend:
            _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 0.9, 0.6)
        ax.set_xlim(-0.5, 31)
        ax.set_ylim(nrows + (2.0 if legend else 0.2), -0.5)
        ax.set_xticks([0.5, 9.5, 19.5, 29.5])
        ax.set_xticklabels(["1", "10", "20", "30"], fontsize=7)
        ax.set_yticks([])
        years = sorted({d[:4] for d in cells})
        _finish(plt, fig, ax, theme,
                f"{', '.join(years)} — {scheme.divisions} microphases · "
                f"tint: {tint} · times in {caption}")
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _render_lunar(plt, report, samples, tint, anchor, caption, theme, out):
    scheme = report.scheme
    segs = lunations(samples, report.tz, anchor)
    if not segs:
        raise ValueError("no complete lunations in range for the lunar layout")
    opp = "full" if anchor == "new" else "new"
    cols = 64
    legend = tint == "index"
    fig, ax = plt.subplots(figsize=(11, 0.9 + 0.5 * len(segs)))
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
                    va="center", fontsize=7.5, color=theme.fg)
            ax.text(cols + 1, r + 0.45, seg["end"], ha="left", va="center",
                    fontsize=7.5, color=theme.fg)
            ax.text(cols / 2, r + 1.02, f"{opp} {seg['mid']}", ha="center", va="top",
                    fontsize=6.5, color=theme.muted)
        nseg = len(segs)
        if legend:
            _index_legend(plt, ax, scheme, theme, 0, cols, nseg + 0.7, 0.4)
        ax.set_xlim(-1, cols + 1)
        ax.set_ylim(nseg + (1.6 if legend else 0.3), -0.3)
        ax.set_xticks([])
        ax.set_yticks([])
        _finish(plt, fig, ax, theme,
                f"Lunar months ({anchor}-anchored) — {scheme.divisions} microphases · "
                f"tint: {tint} · times in {caption}")
        fig.tight_layout()
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _save(plt, fig, out):
    if out:
        fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    else:
        plt.show()
