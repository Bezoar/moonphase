import os
import time
from contextlib import contextmanager

import numpy as np
import pytest

import moonphase.cli as cli_mod
from moonphase.cli import resolve_mode


def fake_modes_for(name):
    return {
        "chart": frozenset({"series", "events"}),
        "almanac": frozenset({"events"}),
        "heatmap": frozenset({"series"}),
    }[name]


def test_single_mode_format_auto_resolves():
    assert resolve_mode("almanac", None, fake_modes_for) == "events"
    assert resolve_mode("heatmap", None, fake_modes_for) == "series"


def test_multi_mode_format_defaults_to_series():
    assert resolve_mode("chart", None, fake_modes_for) == "series"


def test_explicit_compatible_mode_kept():
    assert resolve_mode("chart", "events", fake_modes_for) == "events"


def test_incompatible_mode_raises_with_supported_list():
    with pytest.raises(ValueError) as exc:
        resolve_mode("almanac", "series", fake_modes_for)
    assert "events" in str(exc.value)


class _LinearEph:
    def __init__(self, *a, **k):
        from datetime import datetime, timezone
        self._t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def phase_angles_deg(self, times):
        return np.array([
            (12.0 * (t - self._t0).total_seconds() / 86400.0) % 360.0 for t in times
        ], dtype=float)


def test_main_events_mode_writes_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "events.csv"
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-31",
        "--divisions", "4", "--mode", "events", "--transitions",
        "--format", "csv", "--out", str(out),
    ])
    assert rc == 0
    text = out.read_text()
    assert "kind" in text.splitlines()[0]
    assert "transition" in text and "center" in text


def test_main_rejects_incompatible_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "modes_for", lambda n: frozenset({"events"}))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-02",
        "--divisions", "4", "--mode", "series", "--format", "csv",
    ])
    assert rc == 2
    assert "supports mode(s): events" in capsys.readouterr().err


@contextmanager
def _force_tz(name):
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_main_fixed_offset_start_propagates_to_output(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "ev.json"
    rc = cli_mod.main([
        "--start", "2026-01-01T00:00:00-08:00", "--end", "2026-01-31T00:00:00-08:00",
        "--divisions", "4", "--mode", "events", "--format", "json", "--out", str(out),
    ])
    assert rc == 0
    import json
    payload = json.loads(out.read_text())
    assert payload["timezone"] == "UTC-08:00"
    assert payload["events"][0]["time"].endswith("-08:00")


def test_main_bare_date_uses_local(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    with _force_tz("America/Los_Angeles"):
        out = tmp_path / "ev2.json"
        rc = cli_mod.main([
            "--start", "2026-01-01", "--end", "2026-01-31",
            "--divisions", "4", "--mode", "events", "--format", "json", "--out", str(out),
        ])
        assert rc == 0
        import json
        payload = json.loads(out.read_text())
        assert "local time" in payload["timezone"]
        assert payload["events"][0]["time"].endswith("-08:00")  # Jan -> PST
