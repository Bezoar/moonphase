from datetime import timezone

from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report


def test_report_defaults():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.mode == "series"
    assert r.events is None
    assert r.tz == timezone.utc      # default until Phase 2
    assert r.labels is None          # default until Phase 4


def test_report_is_frozen():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="events", events=[])
    try:
        r.mode = "series"
    except Exception as e:
        assert "frozen" in type(e).__name__.lower() or "attribute" in str(e).lower()
    else:
        raise AssertionError("Report should be frozen")
