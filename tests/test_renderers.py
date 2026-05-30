import csv as csvmod
import json
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")

from moonphase import renderers
from moonphase.calendar import PhaseSample
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
