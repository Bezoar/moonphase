import csv as csvmod
import json
from datetime import datetime, timedelta, timezone

import matplotlib
import pytest
matplotlib.use("Agg")

from moonphase import renderers
from moonphase.calendar import PhaseSample
from moonphase.displaytz import DisplayZone
from moonphase.events import PhaseEvent
from moonphase.microphase import MicrophaseScheme
from moonphase.report import Report

S4 = MicrophaseScheme.from_divisions(4)
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _series_report():
    samples = [
        PhaseSample(when=T0, angle_deg=0.0, microphase=0),
        PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0),
    ]
    return Report(scheme=S4, mode="series", samples=samples)


def _events_report():
    events = [
        PhaseEvent(when=T0, angle_deg=0.0, kind="center", index=0, name="New"),
        PhaseEvent(when=T0.replace(hour=6), angle_deg=45.0, kind="transition",
                   index=0, name=None),
    ]
    return Report(scheme=S4, mode="events", events=events)


def test_csv_series(tmp_path):
    out = tmp_path / "s.csv"
    renderers.get("csv")(_series_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[0] == ["time", "phase_angle_deg", "microphase_index", "divisions", "step_deg"]
    assert rows[1][2] == "0"


def test_csv_events(tmp_path):
    out = tmp_path / "e.csv"
    renderers.get("csv")(_events_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[0] == ["time", "target_angle_deg", "kind", "microphase_index", "name", "divisions", "step_deg"]
    assert rows[1][2] == "center" and rows[1][4] == "New"
    assert rows[2][2] == "transition"


def test_json_events(tmp_path):
    out = tmp_path / "e.json"
    renderers.get("json")(_events_report(), str(out))
    payload = json.load(out.open())
    assert payload["scheme"]["divisions"] == 4
    assert payload["events"][0]["kind"] == "center"
    assert "samples" not in payload


def test_terminal_events(tmp_path):
    out = tmp_path / "e.txt"
    renderers.get("terminal")(_events_report(), str(out))
    text = out.read_text()
    assert "center" in text and "New" in text


def test_chart_series_writes_png(tmp_path):
    out = tmp_path / "c.png"
    renderers.get("chart")(_series_report(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_chart_events_writes_png(tmp_path):
    out = tmp_path / "ce.png"
    renderers.get("chart")(_events_report(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_chart_series_with_overlay_writes_png(tmp_path):
    r = Report(scheme=S4, mode="series", samples=_series_report().samples, events=[
        PhaseEvent(when=T0.replace(hour=3), angle_deg=0.0, kind="center", index=0, name="New"),
        PhaseEvent(when=T0.replace(hour=9), angle_deg=45.0, kind="transition", index=0, name=None),
    ])
    out = tmp_path / "co.png"
    renderers.get("chart")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_chart_empty_series_raises(tmp_path):
    with pytest.raises(ValueError):
        renderers.get("chart")(Report(scheme=S4, mode="series", samples=[]), str(tmp_path / "x.png"))


def test_terminal_series_grid(tmp_path):
    out = tmp_path / "ts.txt"
    renderers.get("terminal")(_series_report(), str(out))
    assert "2026-01-01" in out.read_text()


def test_json_has_timezone_field(tmp_path):
    out = tmp_path / "e.json"
    renderers.get("json")(_events_report(), str(out))
    payload = json.load(out.open())
    assert payload["timezone"] == "UTC"  # default zone


def test_json_fixed_offset_timestamps_and_caption(tmp_path):
    z = DisplayZone("fixed", timedelta(hours=-8))
    r = Report(scheme=S4, mode="events", events=_events_report().events, tz=z)
    out = tmp_path / "e2.json"
    renderers.get("json")(r, str(out))
    payload = json.load(out.open())
    assert payload["timezone"] == "UTC-08:00"
    assert payload["events"][0]["time"].endswith("-08:00")


def test_csv_timestamps_carry_offset(tmp_path):
    out = tmp_path / "s.csv"
    renderers.get("csv")(_series_report(), str(out))
    rows = list(csvmod.reader(out.open()))
    assert rows[1][0].endswith("+00:00")  # default UTC


def test_terminal_header_states_timezone(tmp_path):
    out = tmp_path / "e.txt"
    renderers.get("terminal")(_events_report(), str(out))
    assert "UTC" in out.read_text().splitlines()[0]


def test_terminal_series_groups_by_display_tz_day(tmp_path):
    z = DisplayZone("fixed", timedelta(hours=-8))
    # 2026-01-02 03:00 UTC == 2026-01-01 19:00 in UTC-08:00 -> previous local day
    sample = PhaseSample(when=datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
                         angle_deg=0.0, microphase=0)
    r = Report(scheme=S4, mode="series", samples=[sample], tz=z)
    out = tmp_path / "tzday.txt"
    renderers.get("terminal")(r, str(out))
    assert "2026-01-01" in out.read_text()  # grouped under local day, not 01-02


def _almanac_report():
    evs = []
    names = ["New", "First Quarter", "Full", "Last Quarter"]
    for k, (ang, nm) in enumerate(zip((0, 90, 180, 270), names)):
        evs.append(PhaseEvent(when=T0 + timedelta(days=7.4 * k), angle_deg=float(ang),
                              kind="center", index=k, name=nm))
    return Report(scheme=S4, mode="events", events=evs)


def test_almanac_registered_events_only():
    assert "almanac" in renderers.available("events")
    assert "almanac" not in renderers.available("series")


def test_almanac_writes_png(tmp_path):
    out = tmp_path / "a.png"
    renderers.get("almanac")(_almanac_report(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_almanac_empty_events_raises(tmp_path):
    r = Report(scheme=S4, mode="events", events=[])
    import pytest
    with pytest.raises(ValueError):
        renderers.get("almanac")(r, str(tmp_path / "x.png"))


def _heatmap_report(days=70, options=None, events=None):
    from datetime import timedelta
    samples = []
    for i in range(days * 24):
        when = T0 + timedelta(hours=i)
        ang = (12.19 * (when - T0).total_seconds() / 86400.0) % 360.0
        samples.append(PhaseSample(when=when, angle_deg=ang,
                                   microphase=int(ang / 22.5 + 0.5) % 16))
    return Report(scheme=MicrophaseScheme.from_divisions(16), mode="series",
                  samples=samples, options=options, events=events)


def test_heatmap_registered_series_only():
    assert "heatmap" in renderers.available("series")
    assert "heatmap" not in renderers.available("events")


def test_heatmap_gregorian_illumination_png(tmp_path):
    out = tmp_path / "h.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "illumination",
                             "calendar": "gregorian"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_index_tint_png(tmp_path):
    out = tmp_path / "h2.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "index",
                             "calendar": "gregorian"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_lunar_layout_png(tmp_path):
    out = tmp_path / "h3.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "illumination",
                             "calendar": "lunar", "lunar_anchor": "new"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_empty_samples_raises(tmp_path):
    import pytest
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[])
    with pytest.raises(ValueError):
        renderers.get("heatmap")(r, str(tmp_path / "x.png"))


def test_heatmap_light_theme_and_index_legend(tmp_path):
    out = tmp_path / "hl.png"
    renderers.get("heatmap")(_heatmap_report(options={"tint": "index",
                             "calendar": "gregorian", "theme": "light"}), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_csv_events_use_custom_label(tmp_path):
    evs = [PhaseEvent(when=T0, angle_deg=0.0, kind="center", index=0, name="Dark")]
    r = Report(scheme=S4, mode="events", events=evs)
    out = tmp_path / "e.csv"
    renderers.get("csv")(r, str(out))
    assert "Dark" in out.read_text()


def test_chart_uses_report_labels(tmp_path):
    samples = [PhaseSample(when=T0, angle_deg=0.0, microphase=0),
               PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0)]
    r = Report(scheme=S4, mode="series", samples=samples,
               labels=["Dark", "Waxing", "Bright", "Waning"])
    out = tmp_path / "c.png"
    renderers.get("chart")(r, str(out))            # smoke: renders with custom axis
    assert out.exists() and out.stat().st_size > 0


def test_chart_renders_both_themes(tmp_path):
    samples = [PhaseSample(when=T0, angle_deg=0.0, microphase=0),
               PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0)]
    for theme in ("dark", "light"):
        r = Report(scheme=S4, mode="series", samples=samples, options={"theme": theme})
        out = tmp_path / f"c-{theme}.png"
        renderers.get("chart")(r, str(out))
        assert out.exists() and out.stat().st_size > 0


def test_almanac_renders_both_themes(tmp_path):
    for theme in ("dark", "light"):
        r = Report(scheme=S4, mode="events", events=_almanac_report().events,
                   options={"theme": theme})
        out = tmp_path / f"a-{theme}.png"
        renderers.get("almanac")(r, str(out))
        assert out.exists() and out.stat().st_size > 0


def _giant_transitions():
    from datetime import timedelta
    return [
        PhaseEvent(when=T0 + timedelta(days=2, hours=4), angle_deg=11.25,
                   kind="transition", index=0, name=None),
        PhaseEvent(when=T0 + timedelta(days=2, hours=20), angle_deg=33.75,
                   kind="transition", index=1, name=None),
        PhaseEvent(when=T0 + timedelta(days=6, hours=9), angle_deg=56.25,
                   kind="transition", index=2, name=None),
    ]


def _giant_centers():
    from datetime import timedelta
    return [
        PhaseEvent(when=T0 + timedelta(days=3, hours=5), angle_deg=0.0,
                   kind="center", index=0, name="New"),
        PhaseEvent(when=T0 + timedelta(days=10, hours=12), angle_deg=90.0,
                   kind="center", index=2, name="1Q"),
    ]


def test_heatmap_cell_times_peaks_only_writes_png(tmp_path):
    r = _heatmap_report(
        options={"tint": "index", "calendar": "gregorian", "cell_times": True},
        events=_giant_centers())
    out = tmp_path / "peaks.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_cell_line_format():
    from moonphase.renderers.heatmap import _cell_line
    assert _cell_line(True, "Full", "14:25") == "→Full 14:25"
    assert _cell_line(False, "Full", "21:23") == "Full 21:23"


def test_heatmap_cell_times_writes_png(tmp_path):
    r = _heatmap_report(
        options={"tint": "illumination", "calendar": "gregorian",
                 "cell_times": True},
        events=_giant_transitions())
    out = tmp_path / "giant.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_cell_times_too_small_size_raises(tmp_path):
    r = _heatmap_report(
        options={"tint": "illumination", "calendar": "gregorian",
                 "cell_times": True, "size": (200, 200)},
        events=_giant_transitions())
    with pytest.raises(ValueError):
        renderers.get("heatmap")(r, str(tmp_path / "x.png"))


def test_heatmap_size_override_writes_png(tmp_path):
    r = _heatmap_report(options={"tint": "illumination", "calendar": "gregorian",
                                 "size": (1600, 1200)})
    out = tmp_path / "sz.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_unknown_font_raises(tmp_path):
    r = _heatmap_report(options={"tint": "illumination", "calendar": "gregorian",
                                 "font": "NonExistentFontXYZ123"})
    with pytest.raises(ValueError):
        renderers.get("heatmap")(r, str(tmp_path / "x.png"))


def test_chart_title_and_footer(tmp_path):
    samples = [PhaseSample(when=T0, angle_deg=0.0, microphase=0),
               PhaseSample(when=T0.replace(hour=12), angle_deg=6.0, microphase=0)]
    r = Report(scheme=S4, mode="series", samples=samples,
               options={"title": "My Title", "footer": "Source: book\nISBN 123"})
    out = tmp_path / "tf.png"
    renderers.get("chart")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_almanac_title_and_footer(tmp_path):
    r = Report(scheme=S4, mode="events", events=_almanac_report().events,
               options={"title": "Almanac!", "footer": "cite"})
    out = tmp_path / "atf.png"
    renderers.get("almanac")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_title_and_footer(tmp_path):
    r = _heatmap_report(options={"tint": "index", "calendar": "gregorian",
                                 "title": "Heat!", "footer": "cite\nline2"})
    out = tmp_path / "htf.png"
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_label_of_prefers_abbrev():
    from moonphase.renderers.heatmap import _label_of
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[],
               labels=["Dark Moon"] + [None] * 15,
               abbrevs=["Da"] + [None] * 15)
    label = _label_of(r)
    assert label(0) == "Da"          # abbrev wins
    assert label(1) == "1"           # no abbrev, no name -> index


def test_label_of_falls_back_to_name_then_index():
    from moonphase.renderers.heatmap import _label_of
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[],
               labels=["Dark Moon"] + [None] * 15)   # no abbrevs at all
    label = _label_of(r)
    assert label(0) == "Dark Moon"
    assert label(2) == "2"


def test_label_of_abbrev_none_slot_falls_back_to_name():
    from moonphase.renderers.heatmap import _label_of
    r = Report(scheme=MicrophaseScheme.from_divisions(16), mode="series", samples=[],
               labels=["Dark Moon", "Sickle Moon"] + [None] * 14,
               abbrevs=["Da", None] + [None] * 14)     # slot 1 has a name but no code
    label = _label_of(r)
    assert label(0) == "Da"            # abbrev wins
    assert label(1) == "Sickle Moon"   # abbrev None at slot -> name
    assert label(2) == "2"             # neither -> index


def _heatmap_report_with_abbrevs(**opts):
    base = {"tint": "index", "calendar": "gregorian"}
    base.update(opts)
    r = _heatmap_report(options=base)
    codes = ["Da", "Si", "Cr", "Em", "1Q", "Sw", "Gb", "Cu",
             "Fl", "1W", "Di", "Tr", "LQ", "Yd", "Bl", "Im"]
    names = [c + " Moon" for c in codes]
    return Report(scheme=r.scheme, mode="series", samples=r.samples,
                  events=r.events, options=r.options, labels=names, abbrevs=codes)


def test_heatmap_index_with_abbrevs_writes_png(tmp_path):
    out = tmp_path / "abbr.png"
    renderers.get("heatmap")(_heatmap_report_with_abbrevs(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_heatmap_abbrevs_cell_times_writes_png(tmp_path):
    out = tmp_path / "abbr_ct.png"
    r = _heatmap_report_with_abbrevs(cell_times=True)
    renderers.get("heatmap")(r, str(out))
    assert out.exists() and out.stat().st_size > 0


def test_legend_grid_dims():
    from moonphase.renderers.heatmap import _legend_grid_dims
    assert _legend_grid_dims(16) == (4, 4)
    assert _legend_grid_dims(8) == (3, 3)
    assert _legend_grid_dims(4) == (2, 2)


def test_index_grid_legend_draws_entries():
    import matplotlib.pyplot as plt
    from moonphase.renderers.heatmap import _index_grid_legend
    from moonphase.theme import get_theme
    r = _heatmap_report_with_abbrevs()
    fig, ax = plt.subplots()
    try:
        _index_grid_legend(plt, ax, r.scheme, r, get_theme("dark"), top_y=0.0, scale=1.0)
        texts = [t.get_text() for t in ax.texts]
        assert "Da = Da Moon" in texts        # code = full name
        assert "Im = Im Moon" in texts
        assert len(texts) == 16
    finally:
        plt.close(fig)
