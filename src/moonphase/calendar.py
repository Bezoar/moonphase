"""Build a time-indexed series of phase samples across a date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

import numpy as np

from .ephemeris import PhaseEphemeris
from .microphase import MicrophaseScheme, phase_to_index


@dataclass(frozen=True)
class PhaseSample:
    when: datetime
    angle_deg: float
    microphase: int


def _drange(start: datetime, end: datetime, step: timedelta) -> Iterator[datetime]:
    t = start
    while t <= end:
        yield t
        t += step


def build_series(
    start: datetime,
    end: datetime,
    scheme: MicrophaseScheme,
    sample_step: timedelta = timedelta(hours=1),
    ephemeris: PhaseEphemeris | None = None,
) -> list[PhaseSample]:
    """Sample the lunar phase angle across [start, end] at ``sample_step``
    cadence and bucket each into a microphase index.

    Both ``start`` and ``end`` are interpreted as UTC if naive.
    """
    if start > end:
        raise ValueError("start must be <= end")
    if sample_step <= timedelta(0):
        raise ValueError("sample_step must be positive")

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    eph = ephemeris or PhaseEphemeris()
    times = list(_drange(start, end, sample_step))
    angles = eph.phase_angles_deg(times)
    indices = np.array([phase_to_index(float(a), scheme) for a in angles], dtype=int)

    return [PhaseSample(when=t, angle_deg=float(a), microphase=int(i))
            for t, a, i in zip(times, angles, indices)]
