"""Calendar heatmap. Gregorian (months × days) or lunar (one phase-aligned
strip per lunation). Tinted by illuminated fraction or by microphase index."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date

from ..heatmap_layout import cell_events_by_day, day_cells, lunations, principal_phase_days
from ..moondisk import illuminated_fraction, lit_polygon
from ..theme import theme_of
from . import register
from .celltext import damped_text_color
from .chrome import draw_footer, resolved_title

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
    """Figure size (inches) that fits the widest 'label HH:MM' line and the
    tallest stacked cell at the 9 pt floor."""
    lines, max_rows = [], 1
    for crossings in day_trans.values():
        max_rows = max(max_rows, min(len(crossings), _STACK_CAP))
        for is_t, idx, local in crossings:
            lines.append(_cell_line(is_t, label_of(idx), local.strftime("%H:%M")))
    # char-count proxy for pixel width; the arrow-prefixed transition lines are the
    # widest case. The true extent of this pick is measured by _measure_line_inches.
    longest = max(lines, key=len) if lines else "→0 00:00"
    w_in, h_in = _measure_line_inches(plt, longest, family)
    cell_w = w_in + 0.12                        # horizontal padding (inches)
    text_h = max_rows * (h_in * 1.30) + 0.06    # 1.30x line spacing + baseline pad
    # at least square (cell >= cell_w) so a couple of stacked transitions have
    # vertical room; taller still when a day needs more than ~one line of text
    cell = max(text_h, cell_w)
    gutter, title = 2.0, 1.2                      # left month-label gutter + title bar (inches)
    band = _bottom_band(has_legend, giant=True)   # day-of-month axis (+ swatch) region
    # rows ~`cell` inches tall; the bottom band gets the same per-row inches so
    # the enlarged day-axis / legend labels have room.
    return gutter + 31 * cell_w, title + cell * (n_rows + band + 0.5)


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


def _bottom_band(has_legend, giant):
    """Data-unit height of the region below the grid (day-of-month axis, plus the
    index swatch when present). Larger in giant mode to fit enlarged labels."""
    if giant:
        return 3.2 if has_legend else 1.3
    return 1.95 if has_legend else 0.75


def _label_scale(figsize):
    """Scale factor for the structural labels (title, months, day axis, legend) so
    they stay legible when a giant figure is viewed zoomed out. 1.0 at the default
    11-inch width; grows with the figure. Cell-time text intentionally stays 9 pt."""
    return max(1.0, min(1.0 + (figsize[0] - 11.0) / 6.0, 6.0))


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


def _cell_line(is_transition, label, hhmm):
    """One cell-times line: '→label HH:MM' for a transition *into* a phase,
    or bare 'label HH:MM' for a phase peak (center)."""
    return f"{'→' if is_transition else ''}{label} {hhmm}"


def _draw_cell_times(ax, x0, row, crossings, cell, scheme, tint, label_of):
    """Draw a day's phase-peak and transition times inside its cell as low-contrast
    text — transitions arrow-prefixed (entering a phase), peaks bare — collapsing to
    an 'N×' badge past the stack cap."""
    a, i = cell
    color = damped_text_color(_tint(a, i, scheme, tint))
    cx, cy = x0 + 0.47, row + 0.47
    if len(crossings) > _STACK_CAP:
        ax.text(cx, cy, f"{len(crossings)}×", ha="center", va="center",
                fontsize=9, color=color, zorder=8)
        return
    text = "\n".join(_cell_line(is_t, label_of(idx), local.strftime("%H:%M"))
                     for is_t, idx, local in crossings)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9, color=color,
            zorder=8)


def _index_legend(plt, ax, scheme, theme, x0, width, y, h, scale=1.0, cap_below=False):
    """A discrete 0..N-1 swatch strip, shown for index tint. ``cap_below`` places
    the end captions under the swatch (giant charts) rather than above it."""
    n = scheme.divisions
    sw = width / n
    for k in range(n):
        ax.add_patch(plt.Rectangle((x0 + k * sw, y), sw, h,
                                   facecolor=_index_color(k, n), edgecolor="none"))
    fs = round(7 * scale)
    cap_y, va = (y + h + 0.1 * scale + 0.05, "top") if cap_below else (y - 0.3, "bottom")
    ax.text(x0, cap_y, "microphase 0", color=theme.muted, fontsize=fs, ha="left", va=va)
    ax.text(x0 + width, cap_y, str(n - 1), color=theme.muted, fontsize=fs, ha="right", va=va)


def _finish(plt, fig, ax, theme, title, scale=1.0):
    fig.patch.set_facecolor(theme.bg)
    ax.set_facecolor(theme.bg)
    for spine in ax.spines.values():
        spine.set_color(theme.spine)
    ax.tick_params(colors=theme.fg)
    ax.set_title(title, fontsize=round(10 * scale), color=theme.fg)


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
    day_trans = (cell_events_by_day(report.events, report.tz, scheme.divisions)
                 if cell_times else {})
    label_of = _label_of(report)
    figsize = _resolve_figsize(plt, size, cell_times, day_trans, label_of,
                               nrows, legend, family)
    if figsize is None:
        figsize = (11, 0.9 + 0.42 * nrows)
    scale = _label_scale(figsize)

    ctx = (matplotlib.rc_context({"font.family": family}) if family
           else nullcontext())
    with ctx:
        fig, ax = plt.subplots(figsize=figsize)
        try:
            for row, ym in enumerate(months):
                y, m = ym[:4], int(ym[5:7])
                if not cell_times:               # giant charts label months as
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
                    # In cell-times mode the principal phases show as plain
                    # "label HH:MM" text like any other phase, so the
                    # moon-disk markers are suppressed.
                    if key in marks and not cell_times:
                        _draw_marker(ax, dd - 0.53, row + 0.47, 0.30,
                                     marks[key], theme)
                    if cell_times and key in day_trans:
                        _draw_cell_times(ax, dd - 1, row, day_trans[key],
                                         cells[key], scheme, tint, label_of)
            # Giant charts label months as proper y-ticks so tight_layout reserves
            # the (enlarged) left margin; the normal heatmap keeps the inline text
            # drawn above and an empty y-axis.
            if cell_times:
                ax.set_yticks([r + 0.5 for r in range(nrows)])
                ax.set_yticklabels([f"{_MON[int(ym[5:7]) - 1]} {ym[:4]}" for ym in months],
                                   fontsize=round(7 * scale), color=theme.fg)
                ax.tick_params(axis="y", length=0)
            else:
                ax.set_yticks([])
            # A single day-of-month axis directly beneath the grid, ticked and
            # labelled every 7 days (replaces matplotlib's bottom tick axis).
            for d in (1, 8, 15, 22, 29):
                x = d - 0.5
                ax.plot([x, x], [nrows + 0.02, nrows + 0.16], color=theme.spine,
                        lw=0.9 * min(scale, 3))
                ax.text(x, nrows + 0.22, str(d), ha="center", va="top",
                        fontsize=round(9 * scale), color=theme.fg)
            if legend:
                if cell_times:
                    _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 1.6, 0.6,
                                  scale=scale, cap_below=True)
                else:
                    _index_legend(plt, ax, scheme, theme, 0, 14, nrows + 1.05, 0.5)
            ax.set_xlim(-0.5, 31)
            ax.set_ylim(nrows + _bottom_band(legend, cell_times), -0.5)
            ax.set_xticks([])
            years = sorted({d[:4] for d in cells})
            auto = (f"{', '.join(years)} — {scheme.divisions} microphases · "
                    f"tint: {tint} · times in {caption}")
            _finish(plt, fig, ax, theme, resolved_title(report, auto), scale=scale)
            fig.tight_layout()
            draw_footer(fig, report, theme, scale=scale)
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
        auto = (f"Lunar months ({anchor}-anchored) — {scheme.divisions} microphases · "
                f"tint: {tint} · times in {caption}")
        _finish(plt, fig, ax, theme, resolved_title(report, auto))
        fig.tight_layout()
        draw_footer(fig, report, theme)
        _save(plt, fig, out)
    finally:
        plt.close(fig)


def _save(plt, fig, out):
    if out:
        fig.savefig(out, dpi=_DPI, facecolor=fig.get_facecolor())
    else:
        plt.show()
