"""Shared chart 'chrome': the --title override and the --footer line, used by
the chart, heatmap, and almanac renderers so title/footer behave identically."""

from __future__ import annotations


def resolved_title(report, default: str) -> str:
    """The ``--title`` override (options['title']) when set and non-empty,
    otherwise the renderer's auto-built ``default``."""
    title = (report.options or {}).get("title")
    return title if title else default


def draw_footer(fig, report, theme, scale: float = 1.0) -> None:
    """Draw ``options['footer']`` as a low-contrast, themed line centered at the
    figure bottom. Multi-line aware. No-op when no footer is set. Enlarges the
    bottom margin so the text is not clipped; call after ``fig.tight_layout()``."""
    footer = (report.options or {}).get("footer")
    if not footer:
        return
    nlines = footer.count("\n") + 1
    pad = 0.05 + 0.03 * nlines * scale
    fig.subplots_adjust(bottom=max(fig.subplotpars.bottom, pad + 0.02))
    fig.text(0.5, 0.012, footer, ha="center", va="bottom",
             fontsize=round(7 * scale), color=theme.muted, linespacing=1.2)
