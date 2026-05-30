"""Helpers for drawing low-contrast text inside heatmap cells."""

from __future__ import annotations


def _luminance(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def damped_text_color(cell_rgb, contrast: float = 0.55):
    """Return an RGB tuple for text drawn on ``cell_rgb`` that stays in a
    low-to-medium contrast band: pick black-or-white from the cell's luminance,
    then blend that target toward the cell color by ``contrast`` (0.0 = the cell
    color itself / invisible, 1.0 = full black/white)."""
    target = 0.0 if _luminance(cell_rgb) > 0.5 else 1.0
    return tuple(c + (target - c) * contrast for c in cell_rgb[:3])
