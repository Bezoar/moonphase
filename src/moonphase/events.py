"""Exact phase-center and transition-point events via root-finding.

The synodic phase angle advances monotonically (~12.2 deg/day). We coarse-
sample it, unwrap to a monotonic curve, then bisect within the bracketing
interval to locate the exact UTC instant each target angle is crossed.

Only ``ephemeris.phase_angles_deg(times) -> ndarray`` is required, so this is
unit-testable with any object exposing that method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from .microphase import MicrophaseScheme
from .naming import default_name

_DEG_PER_DAY = 12.2          # approximate Moon-minus-Sun elongation rate
_BISECT_ITERS = 40           # ~2e-12 day resolution; well sub-second


@dataclass(frozen=True)
class PhaseEvent:
    when: datetime            # exact UTC instant (tz-aware)
    angle_deg: float          # target elongation crossed (k*step or (k+0.5)*step)
    kind: str                 # "center" | "transition"
    index: int                # microphase index
    name: str | None          # built-in name (centers, N in {4,8}) else None


def _unwrap(angles: np.ndarray) -> np.ndarray:
    """Turn a wrapped [0,360) sequence into a monotonic increasing one."""
    out = np.array(angles, dtype=float)
    add = 0.0
    for i in range(1, len(out)):
        if angles[i] < angles[i - 1]:
            add += 360.0
        out[i] = angles[i] + add
    return out


def _classify(target_unwrapped: float, scheme: MicrophaseScheme):
    target_mod = target_unwrapped % 360.0
    ratio = target_mod / scheme.step_deg
    nearest = round(ratio)
    if abs(ratio - nearest) < 1e-6:
        idx = int(nearest) % scheme.divisions
        return target_mod, "center", idx, default_name(idx, scheme)
    idx = int(math.floor(ratio)) % scheme.divisions
    return target_mod, "transition", idx, None


def build_events(start, end, scheme, ephemeris, transitions=False):
    """Return chronological :class:`PhaseEvent`s in ``[start, end]``.

    With ``transitions=False`` only phase centers (multiples of ``step``).
    With ``transitions=True`` also transition points (odd multiples of
    ``step/2``); the half-step grid is an internal device - events are still
    labeled ``center``/``transition``, never treated as 2N microphases.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start > end:
        raise ValueError("start must be <= end")

    unit = scheme.step_deg / 2.0 if transitions else scheme.step_deg
    coarse_days = max(min((unit / _DEG_PER_DAY) / 4.0, 0.25), 1e-4)

    grid = []
    t = start
    while t <= end:
        grid.append(t)
        t += timedelta(days=coarse_days)
    if grid[-1] < end:
        grid.append(end)

    angles = np.asarray(ephemeris.phase_angles_deg(grid), dtype=float)
    U = _unwrap(angles)

    events: list[PhaseEvent] = []
    m_lo = math.ceil(U[0] / unit)
    m_hi = math.floor(U[-1] / unit)
    for m in range(m_lo, m_hi + 1):
        target = m * unit
        j = int(np.searchsorted(U, target)) - 1
        j = max(0, min(j, len(grid) - 2))
        lo, hi, ref = grid[j], grid[j + 1], float(U[j])
        for _ in range(_BISECT_ITERS):
            mid = lo + (hi - lo) / 2
            a = float(ephemeris.phase_angles_deg([mid])[0])
            u = a + 360.0 * round((ref - a) / 360.0)
            if u < target:
                lo = mid
            else:
                hi = mid
        when = lo + (hi - lo) / 2
        angle_deg, kind, index, name = _classify(target, scheme)
        events.append(PhaseEvent(when=when, angle_deg=angle_deg, kind=kind,
                                 index=index, name=name))
    return events
