"""Moon-disk geometry: illuminated fraction and the lit-limb polygon.

Phase angle 0° = new (dark), 180° = full (lit). A renderer draws a dark disk
and fills the polygon returned here. New returns ``None`` (nothing lit); full
returns the whole disk. Coordinates are plain Cartesian; the lit region is
symmetric top-to-bottom, so callers may use either y-orientation.
"""

from __future__ import annotations

import math


def illuminated_fraction(theta_deg: float) -> float:
    """Fraction of the disk lit: 0 at new, 0.5 at the quarters, 1 at full."""
    return (1.0 - math.cos(math.radians(theta_deg))) / 2.0


def lit_polygon(cx: float, cy: float, r: float, theta_deg: float, n: int = 48):
    """Vertices of the illuminated region of a moon at phase ``theta_deg`` on a
    disk of radius ``r`` centered at ``(cx, cy)``. Returns ``None`` for new.

    The bright limb is the right semicircle for waxing phases; waning phases are
    the mirror image. The terminator is a half-ellipse whose signed x-radius is
    ``r·cos(folded angle)`` — at the quarter it collapses to the vertical
    diameter (exact half disk); at full it reaches the opposite limb.
    """
    th = theta_deg % 360.0
    if illuminated_fraction(th) < 0.005:
        return None
    waning = th > 180.0
    tp = 360.0 - th if waning else th
    rxt = r * math.cos(math.radians(tp))
    pts = []
    for i in range(n + 1):                       # bright limb: right semicircle
        phi = -math.pi / 2 + math.pi * i / n
        pts.append((cx + r * math.cos(phi), cy - r * math.sin(phi)))
    for i in range(n + 1):                       # terminator: back to start
        phi = math.pi / 2 - math.pi * i / n
        pts.append((cx + rxt * math.cos(phi), cy - r * math.sin(phi)))
    if waning:
        pts = [(2 * cx - x, y) for (x, y) in pts]
    return pts
