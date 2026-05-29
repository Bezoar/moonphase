"""Skyfield-backed Sun/Moon ecliptic-longitude lookup."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np


class PhaseEphemeris:
    """Wraps a JPL kernel to expose lunar phase angle (Moon − Sun ecliptic
    longitude, mod 360°) at arbitrary times.

    Construction is lazy so importing the package does not require Skyfield
    to be present, and so the ~17 MB DE421 kernel is only fetched when
    actually computing.
    """

    DEFAULT_KERNEL = "de421.bsp"

    def __init__(self, kernel_path: str | Path | None = None, data_dir: str | Path = "data"):
        from skyfield.api import Loader

        self._loader = Loader(str(data_dir))
        if kernel_path is None:
            self._eph = self._loader(self.DEFAULT_KERNEL)
        else:
            from skyfield.jpllib import SpiceKernel

            self._eph = SpiceKernel(str(kernel_path))
        self._ts = self._loader.timescale()
        self._earth = self._eph["earth"]
        self._sun = self._eph["sun"]
        self._moon = self._eph["moon"]

    def phase_angles_deg(self, times: Iterable[datetime]) -> np.ndarray:
        """Return phase angle (Moon − Sun ecliptic longitude) in degrees,
        wrapped to [0, 360), for each UTC datetime."""
        from skyfield.framelib import ecliptic_frame

        ts_list = list(times)
        if not ts_list:
            return np.empty(0, dtype=float)

        t = self._ts.from_datetimes(ts_list)
        e = self._earth.at(t)
        _, sun_lon, _ = e.observe(self._sun).apparent().frame_latlon(ecliptic_frame)
        _, moon_lon, _ = e.observe(self._moon).apparent().frame_latlon(ecliptic_frame)
        angles = (moon_lon.degrees - sun_lon.degrees) % 360.0
        return np.asarray(angles, dtype=float)
