from moonphase.displaytz import DisplayZone
from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report


def test_report_defaults():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.mode == "series"
    assert r.events is None
    assert isinstance(r.tz, DisplayZone) and r.tz.kind == "utc"  # default until set by CLI
    assert r.labels is None          # default until Phase 4
    assert r.abbrevs is None         # default until populated by renderers/CLI
    assert r.options is None


def test_report_is_frozen():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="events", events=[])
    try:
        r.mode = "series"
    except Exception as e:
        assert "frozen" in type(e).__name__.lower() or "attribute" in str(e).lower()
    else:
        raise AssertionError("Report should be frozen")


def test_report_abbrevs_defaults_none():
    s = MicrophaseScheme.from_divisions(16)
    r = Report(scheme=s, mode="series", samples=[])
    assert r.abbrevs is None


def test_report_abbrevs_roundtrips():
    s = MicrophaseScheme.from_divisions(4)
    r = Report(scheme=s, mode="series", samples=[],
               labels=["Dark", "Wax", "Bright", "Wane"],
               abbrevs=["Da", "Wx", "Br", "Wn"])
    assert r.abbrevs == ["Da", "Wx", "Br", "Wn"]
