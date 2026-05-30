from datetime import datetime, timedelta, timezone

from moonphase.calendar import PhaseSample
from moonphase.displaytz import DisplayZone
from moonphase.heatmap_layout import day_cells, principal_phase_days, lunations

UTC = DisplayZone.utc()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _series(days, per_day=24, rate_deg_per_day=12.19, phase0=0.0):
    """Synthetic hourly samples with a linearly advancing phase angle."""
    out = []
    step_h = 24 // per_day
    n = days * per_day
    for i in range(n):
        when = T0 + timedelta(hours=i * step_h)
        ang = (phase0 + rate_deg_per_day * (when - T0).total_seconds() / 86400.0) % 360.0
        out.append(PhaseSample(when=when, angle_deg=ang, microphase=int(ang / 45 + 0.5) % 8))
    return out


def test_day_cells_one_per_local_day():
    cells = day_cells(_series(3), UTC)
    dates = [c[0] for c in cells]
    assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert all(0.0 <= c[1] < 360.0 for c in cells)   # angle present


def test_principal_phase_days_marks_quarters():
    # ~12.19 deg/day -> Full (180) near day 14-15, New (~360) near day 29-30
    marks = principal_phase_days(_series(31), UTC)
    # there must be a Full (index 2) and a First Quarter (index 1) marked
    assert 2 in marks.values()
    assert 1 in marks.values()
    # the marked dates are valid ISO days
    assert all(len(d) == 10 for d in marks)


def test_lunations_new_anchor_segments_a_cycle():
    segs = lunations(_series(70), UTC, "new")   # ~2.4 synodic months
    assert len(segs) >= 1
    s = segs[0]
    assert set(s) >= {"start", "end", "mid", "days"}
    assert 28 <= s["days"] <= 31
    # mid (full) falls between start and end
    assert s["start"] < s["mid"] < s["end"]


def test_lunations_full_anchor_uses_180_crossings():
    segs = lunations(_series(70), UTC, "full")
    assert segs and 28 <= segs[0]["days"] <= 31
