"""Pure layout helpers for the heatmap renderer, derived entirely from the
time-ordered series samples (no ephemeris needed). Boundaries are accurate to
the sampling cadence, which is plenty for a day-resolution calendar.
"""

from __future__ import annotations


def day_cells(samples, tz):
    """One representative ``(date_iso, angle_deg, microphase)`` per display-tz
    day — the first sample falling in that local day."""
    seen: dict[str, tuple] = {}
    for p in samples:
        d = tz.to_display(p.when).date().isoformat()
        if d not in seen:
            seen[d] = (p.angle_deg, p.microphase)
    return [(d, a, i) for d, (a, i) in sorted(seen.items())]


def principal_phase_days(samples, tz):
    """Map ``date_iso -> principal index`` (0=New, 1=First Qtr, 2=Full,
    3=Last Qtr) for each day a principal phase (a multiple of 90°) is crossed.
    Detected from forward-advancing angle between consecutive samples."""
    out: dict[str, int] = {}
    prev = None
    for p in samples:
        a = p.angle_deg
        if prev is not None:
            pa, _ = prev
            day = tz.to_display(p.when).date().isoformat()
            if a < pa:                       # wrapped through 360 -> New
                out[day] = 0
            for k, target in ((1, 90.0), (2, 180.0), (3, 270.0)):
                if pa < target <= a:
                    out[day] = k
        prev = (a, p.when)
    return out


def lunations(samples, tz, anchor):
    """Segment the series into lunations bounded by ``anchor`` crossings
    ('new' -> 0° wrap, 'full' -> 180°). Each segment is a dict with display-tz
    ``start``/``end``/``mid`` ISO dates and a ``days`` count. ``mid`` is the
    opposite anchor's date (full for new-anchored, new for full-anchored)."""
    boundaries = []
    prev = None
    for p in samples:
        a = p.angle_deg
        if prev is not None:
            pa, _ = prev
            crossed = (a < pa) if anchor == "new" else (pa < 180.0 <= a)
            if crossed:
                boundaries.append(tz.to_display(p.when))
        prev = (a, p.when)

    segs = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        mid = s + (e - s) / 2
        segs.append({
            "start": s.date().isoformat(),
            "end": e.date().isoformat(),
            "mid": mid.date().isoformat(),
            "days": (e.date() - s.date()).days,
        })
    return segs


def cell_events_by_day(events, tz, divisions):
    """Map ``date_iso -> time-sorted [(is_transition, idx, local), ...]`` over both
    phase-center and transition events.

    A ``center`` event's ``index`` is the phase at its peak (``is_transition`` False,
    rendered bare). A ``transition`` event's ``index`` is the microphase being *left*,
    so the entered phase is ``(index + 1) % divisions`` (``is_transition`` True,
    rendered with a leading arrow by the renderer). ``events`` may be ``None``."""
    out: dict[str, list[tuple[bool, int, object]]] = {}
    for e in events or []:
        if e.kind == "transition":
            is_transition, idx = True, (e.index + 1) % divisions
        elif e.kind == "center":
            is_transition, idx = False, e.index
        else:
            continue
        local = tz.to_display(e.when)
        day = local.date().isoformat()
        out.setdefault(day, []).append((is_transition, idx, local))
    for day in out:
        out[day].sort(key=lambda t: t[2])
    return out
