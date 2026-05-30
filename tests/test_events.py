from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from moonphase.microphase import MicrophaseScheme
from moonphase.events import PhaseEvent, build_events


class LinearEphemeris:
    """Phase angle advances linearly from phase0 at `rate` deg/day."""

    def __init__(self, t0, rate_deg_per_day=12.0, phase0_deg=0.0):
        self.t0 = t0
        self.rate = rate_deg_per_day
        self.phase0 = phase0_deg

    def phase_angles_deg(self, times):
        return np.array([
            (self.phase0 + self.rate * (t - self.t0).total_seconds() / 86400.0) % 360.0
            for t in times
        ], dtype=float)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _days(event, start=START):
    return (event.when - start).total_seconds() / 86400.0


def test_centers_only_for_divisions_four():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=30), scheme, eph)

    assert all(e.kind == "center" for e in events)
    names = [e.name for e in events]
    # New(0d) FQ(7.5d) Full(15d) LQ(22.5d) New(30d)
    assert names == ["New", "First Quarter", "Full", "Last Quarter", "New"]
    assert abs(_days(events[1]) - 7.5) < 0.01
    assert abs(_days(events[2]) - 15.0) < 0.01
    assert all(events[i].when < events[i + 1].when for i in range(len(events) - 1))


def test_transitions_interleave_with_centers():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=30), scheme, eph,
                          transitions=True)

    kinds = [e.kind for e in events]
    # 0,45,90,135,180,225,270,315,360 -> C,T,C,T,C,T,C,T,C
    assert kinds == ["center", "transition", "center", "transition",
                     "center", "transition", "center", "transition", "center"]
    # transition at 45 deg bounds microphase 0; at 135 bounds microphase 1
    t45 = next(e for e in events if abs(e.angle_deg - 45.0) < 1e-6)
    assert t45.kind == "transition" and t45.index == 0 and t45.name is None
    t135 = next(e for e in events if abs(e.angle_deg - 135.0) < 1e-6)
    assert t135.index == 1


def test_events_are_phaseevents():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_divisions(4)
    events = build_events(START, START + timedelta(days=20), scheme, eph)
    assert events and isinstance(events[0], PhaseEvent)
    assert events[0].when.tzinfo is not None


def test_point_interval_returns_empty():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=90.0)
    scheme = MicrophaseScheme.from_divisions(4)
    assert build_events(START, START, scheme, eph) == []


def test_start_after_end_raises():
    eph = LinearEphemeris(START)
    with pytest.raises(ValueError):
        build_events(START + timedelta(days=1), START, MicrophaseScheme.from_divisions(4), eph)


def test_non_dividing_step_rejected_in_events():
    eph = LinearEphemeris(START)
    scheme = MicrophaseScheme.from_step(7.0)  # 360/7 is not an integer
    with pytest.raises(ValueError):
        build_events(START, START + timedelta(days=40), scheme, eph)


def test_dividing_step_allowed_in_events():
    eph = LinearEphemeris(START, rate_deg_per_day=12.0, phase0_deg=0.0)
    scheme = MicrophaseScheme.from_step(90.0)  # divides 360 -> 4 arcs
    events = build_events(START, START + timedelta(days=30), scheme, eph)
    assert events and all(e.kind == "center" for e in events)
