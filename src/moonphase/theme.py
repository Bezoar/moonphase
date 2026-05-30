"""Color themes for the matplotlib renderers (dark by default, light optional).

A ``Theme`` is a flat palette; ``style_axes`` applies the background, spine,
tick, and label colors to a figure/axes so each renderer only sets its own
element colors from the same palette. The default is dark, matching the design
mockups.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str            # figure / axes background
    fg: str            # primary text + ticks
    muted: str         # secondary text (dates, captions)
    spine: str         # axes spines / frame
    band: str          # phase-band shading color
    band_alpha: float
    moon_lit: str      # illuminated limb
    moon_dark: str     # unlit disk
    moon_ring: str     # disk outline (keeps a new moon visible)
    chip: str          # marker backing chip (heatmap principal days)
    chip_ring: str
    transition: str    # transition-point accent
    center: str        # phase-center accent


_DARK = Theme(
    name="dark", bg="#11131a", fg="#e8e6df", muted="#8a93a8", spine="#3a4154",
    band="#ffffff", band_alpha=0.05, moon_lit="#f4f1e6", moon_dark="#15171f",
    moon_ring="#aab2c4", chip="#0c0e14", chip_ring="#aab2c4",
    transition="#d98324", center="#8aa0c8",
)
_LIGHT = Theme(
    name="light", bg="#ffffff", fg="#222222", muted="#666666", spine="#888888",
    band="#000000", band_alpha=0.05, moon_lit="#f4f1e6", moon_dark="#15171f",
    moon_ring="#555555", chip="#15171f", chip_ring="#555555",
    transition="#c8741a", center="#3a5a8a",
)

_THEMES = {"dark": _DARK, "light": _LIGHT}


def get_theme(name: str | None) -> Theme:
    """Return the named theme; defaults to dark for ``None`` or unknown names."""
    return _THEMES.get(name or "dark", _DARK)


def theme_of(report) -> Theme:
    """Resolve the theme for a report from its ``options`` (default dark)."""
    return get_theme((report.options or {}).get("theme"))


def style_axes(fig, ax, theme: Theme) -> None:
    """Apply background, spine, tick, and label colors to a figure/axes."""
    fig.patch.set_facecolor(theme.bg)
    ax.set_facecolor(theme.bg)
    for spine in ax.spines.values():
        spine.set_color(theme.spine)
    ax.tick_params(colors=theme.fg, which="both")
    ax.xaxis.label.set_color(theme.fg)
    ax.yaxis.label.set_color(theme.fg)
    ax.title.set_color(theme.fg)
