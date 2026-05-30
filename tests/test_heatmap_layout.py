from datetime import datetime, timedelta, timezone

from moonphase.calendar import PhaseSample
from moonphase.displaytz import DisplayZone
from moonphase.events import PhaseEvent
from moonphase.heatmap_layout import (
    day_cells, principal_phase_days, lunations, cell_events_by_day,
)

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


def test_cell_events_by_day_merges_centers_and_transitions_sorted():
    evs = [
        PhaseEvent(when=datetime(2026, 1, 1, 18, tzinfo=timezone.utc),
                   angle_deg=22.5, kind="transition", index=0, name=None),
        PhaseEvent(when=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
                   angle_deg=0.0, kind="center", index=0, name="New"),
        PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                   angle_deg=45.0, kind="center", index=1, name=None),
    ]
    m = cell_events_by_day(evs, UTC, 8)
    assert list(m) == ["2026-01-01", "2026-01-02"]
    # time-sorted within the day: center (06:00) before transition (18:00).
    # center index is the phase itself (no +1); transition entered = index+1.
    assert [(is_t, idx, t.hour) for is_t, idx, t in m["2026-01-01"]] == [
        (False, 0, 6), (True, 1, 18)]
    assert [(is_t, idx) for is_t, idx, _ in m["2026-01-02"]] == [(False, 1)]


def test_cell_events_by_day_centers_only_when_no_transitions():
    evs = [PhaseEvent(when=datetime(2026, 1, 3, 9, tzinfo=timezone.utc),
                      angle_deg=180.0, kind="center", index=4, name="Full")]
    m = cell_events_by_day(evs, UTC, 8)
    assert [(is_t, idx) for is_t, idx, _ in m["2026-01-03"]] == [(False, 4)]


def test_cell_events_by_day_handles_none_events():
    assert cell_events_by_day(None, UTC, 8) == {}


def test_cell_events_by_day_uses_display_tz_day():
    z = DisplayZone("fixed", timedelta(hours=-8))
    # 2026-01-02 03:00 UTC == 2026-01-01 19:00 local -> previous local day
    evs = [PhaseEvent(when=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
                      angle_deg=11.25, kind="transition", index=0, name=None)]
    m = cell_events_by_day(evs, z, 8)
    assert list(m) == ["2026-01-01"]
