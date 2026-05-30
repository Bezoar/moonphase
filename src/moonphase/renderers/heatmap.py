"""Calendar heatmap. Gregorian (months × days) or lunar (one phase-aligned
strip per lunation). Tinted by illuminated fraction or by microphase index."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date

from ..heatmap_layout import day_cells, lunations, principal_phase_days, transitions_by_day
from ..moondisk import illuminated_fraction, lit_polygon
from ..theme import theme_of
from . import register
from .celltext import damped_text_color

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


_DPI = 150          # px <-> inch conversion for --size and giant sizing
_STACK_CAP = 4      # max stacked time lines before a cell collapses to a "N×" badge


def _giant_params(report):
    o = report.options or {}
    return o.get("size"), o.get("cell_times", False), o.get("font")


def _label_of(report):
    """Return f(entered_index) -> short text: the custom label when --labels was
    given and non-empty for that slot, else the bare index number."""
    labels = report.labels

    def label(idx):
        if labels and idx < len(labels) and labels[idx]:
            return labels[idx]
        return str(idx)

    return label


def _resolve_font(family):
    """Resolve ``--font`` to a usable family name. A filesystem path is
    registered with matplotlib; an unknown family name raises ValueError."""
    if not family:
        return None
    import os
    from matplotlib import font_manager
    if os.path.isfile(family):
        # addfont registers the font globally in matplotlib's fontManager for
        # the lifetime of the process.
        font_manager.fontManager.addfont(family)
        return font_manager.FontProperties(fname=family).get_name()
    available = {f.name for f in font_manager.fontManager.ttflist}
    if family not in available:
        raise ValueError(
            f"font {family!r} not found; install it or pass a .ttf/.otf path")
    return family


def _measure_line_inches(plt, text, family):
    """True width/height in inches of ``text`` rendered at 9 pt in ``family``."""
    fig = plt.figure(dpi=_DPI)
    try:
        t = fig.text(0.0, 0.0, text, fontsize=9, family=family)
        fig.canvas.draw()
        bb = t.get_window_extent()
        return bb.width / _DPI, bb.height / _DPI
    finally:
        plt.close(fig)


def _giant_figsize(plt, day_trans, label_of, n_rows, has_legend, family):
    """Figure size (inches) that fits the widest 'label @ HH:MM' line and the
    tallest stacked cell at the 9 pt floor."""
    lines, max_rows = [], 1
    for crossings in day_trans.values():
        max_rows = max(max_rows, min(len(crossings), _STACK_CAP))
        for idx, local in crossings:
            lines.append(f"{label_of(idx)} @ {local.strftime('%H:%M')}")
    # char-count proxy for pixel width; fine for short "label @ HH:MM" strings —
    # the true extent of this pick is then measured by _measure_line_inches.
    longest = max(lines, key=len) if lines else "0 @ 00:00"
    w_in, h_in = _measure_line_inches(plt, longest, family)
    cell_w = w_in + 0.12                        # horizontal padding (inches)
    cell_h = max_rows * (h_in * 1.30) + 0.06    # 1.30x line spacing + baseline pad
    gutter, title = 1.1, 0.6                     # left month-label gutter + title bar (inches)
    legend = 0.7 if has_legend else 0.2          # index-swatch strip allowance
    return gutter + 31 * cell_w, title + n_rows * cell_h + legend


def _resolve_figsize(plt, size, cell_times, day_trans, label_of, n_rows,
                     has_legend, family):
    """Pick the figure size (inches) or None to keep the default auto-size.
    Raises ValueError when an explicit --size is below the giant floor."""
    if cell_times:
        need_w, need_h = _giant_figsize(plt, day_trans, label_of, n_rows,
                                        has_legend, family)
        if size is not None:
            need_px = (need_w * _DPI, need_h * _DPI)
            if size[0] < need_px[0] or size[1] < need_px[1]:
                raise ValueError(
                    f"--size {size[0]}x{size[1]} is too small for --cell-times "
                    f"labels at the 9pt minimum; need at least "
                    f"{round(need_px[0])}x{round(need_px[1])}")
            return (size[0] / _DPI, size[1] / _DPI)
        return (need_w, need_h)
    if size is not None:
        return (size[0] / _DPI, size[1] / _DPI)
    return None


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


def _draw_cell_times(ax, x0, row, crossings, cell, scheme, tint, label_of):
    """Draw a day's transition times inside its cell as low-contrast text,
    collapsing to a 'N×' badge past the stack cap."""
    a, i = cell
    color = damped_text_color(_tint(a, i, scheme, tint))
    cx, cy = x0 + 0.47, row + 0.47
    if len(crossings) > _STACK_CAP:
        ax.text(cx, cy, f"{len(crossings)}×", ha="center", va="center",
                fontsize=9, color=color, zorder=8)
        return
    text = "\n".join(f"{label_of(idx)} @ {local.strftime('%H:%M')}"
                     for idx, local in crossings)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9, color=color,
            zorder=8)


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
    import matplotlib
    scheme = report.scheme
    size, cell_times, font = _giant_params(report)
    cells = {d: (a, i) for d, a, i in day_cells(samples, report.tz)}
    marks = principal_phase_days(samples, report.tz)
    months = sorted({d[:7] for d in cells})
    legend = tint == "index"
    nrows = len(months)

    family = _resolve_font(font)
    day_trans = (transitions_by_day(report.events, report.tz, scheme.divisions)
                 if cell_times else {})
    label_of = _label_of(report)
    figsize = _resolve_figsize(plt, size, cell_times, day_trans, label_of,
                               nrows, legend, family)
    if figsize is None:
        figsize = (11, 0.9 + 0.42 * nrows)

    ctx = (matplotlib.rc_context({"font.family": family}) if family
           else nullcontext())
    with ctx:
        fig, ax = plt.subplots(figsize=figsize)
        try:
            for row, ym in enumerate(months):
                y, m = ym[:4], int(ym[5:7])
                ax.text(-0.6, row + 0.5, f"{_MON[m - 1]} {y}", ha="right",
                        va="center", fontsize=7, color=theme.fg)
                ndays = (date(int(y) + (m // 12), (m % 12) + 1, 1)
                         - date(int(y), m, 1)).days
                for dd in range(1, ndays + 1):
                    key = f"{y}-{m:02d}-{dd:02d}"
                    if key not in cells:
                        continue
                    a, i = cells[key]
                    ax.add_patch(plt.Rectangle((dd - 1, row), 0.94, 0.94,
                                 facecolor=_tint(a, i, scheme, tint),
                                 edgecolor="none"))
                    if key in marks:
                        if cell_times:
                            _draw_marker(ax, dd - 0.85, row + 0.18, 0.13,
                                         marks[key], theme)
                        else:
                            _draw_marker(ax, dd - 0.53, row + 0.47, 0.30,
                                         marks[key], theme)
                    if cell_times and key in day_trans:
                        _draw_cell_times(ax, dd - 1, row, day_trans[key],
                                         cells[key], scheme, tint, label_of)
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
