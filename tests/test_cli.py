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


def test_main_passes_options_to_report(monkeypatch):
    captured = {}

    def fake_render(report, out):
        captured["opts"] = report.options

    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get", lambda name: fake_render)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "8",
        "--format", "json", "--theme", "light", "--tint", "index", "--calendar", "lunar",
        "--lunar-anchor", "full",
    ])
    assert rc == 0
    assert captured["opts"] == {"theme": "light", "tint": "index", "calendar": "lunar",
                                "lunar_anchor": "full", "size": None,
                                "cell_times": False, "font": None,
                                "title": None, "footer": None}


def test_main_theme_defaults_to_dark(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get", lambda name: lambda r, o: captured.update(t=r.options["theme"]))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "8", "--format", "json",
    ])
    assert rc == 0 and captured["t"] == "dark"


def test_main_renderer_value_error_is_clean(tmp_path, monkeypatch, capsys):
    # lunar heatmap over a sub-lunation range -> renderer raises ValueError;
    # main must surface it as a clean "error: ..." with exit code 2, not a traceback.
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-08", "--divisions", "16",
        "--format", "heatmap", "--calendar", "lunar", "--out", str(tmp_path / "x.png"),
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_labels_reach_report_and_events(tmp_path, monkeypatch):
    captured = {}

    def fake_render(report, out):
        captured["report"] = report

    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get", lambda name: fake_render)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-01", "--divisions", "4",
        "--mode", "events", "--format", "json", "--labels", "Dark,,Bright,",
    ])
    assert rc == 0
    rep = captured["report"]
    assert rep.labels[0] == "Dark" and rep.labels[2] == "Bright"
    assert rep.labels[1] == "First Quarter"        # blank -> built-in
    names = {e.index: e.name for e in rep.events if e.kind == "center"}
    assert names.get(0) == "Dark" and names.get(2) == "Bright"


def test_main_labels_bad_file_is_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-02-01", "--divisions", "4",
        "--mode", "events", "--format", "json", "--labels", f"@{tmp_path / 'nope.txt'}",
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_labels_malformed_json_is_clean_error(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-02-01", "--divisions", "4",
        "--mode", "events", "--format", "json", "--labels", f"@{bad}",
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_parse_size_ok():
    assert cli_mod._parse_size("5000x3000") == (5000, 3000)
    assert cli_mod._parse_size(" 800X600 ") == (800, 600)


def test_parse_size_bad():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        cli_mod._parse_size("wide")
    with pytest.raises(argparse.ArgumentTypeError):
        cli_mod._parse_size("0x100")


def test_cell_times_without_transitions_renders_peaks(monkeypatch, tmp_path):
    # --cell-times without --transitions is now valid: cells show phase peaks only.
    # A 3-month range guarantees several phase-center events land in day cells so the
    # _draw_cell_times path is actually exercised (one month may yield none at 8 div).
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    out = tmp_path / "h.png"
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-31", "--divisions", "8",
        "--format", "heatmap", "--cell-times", "--out", str(out),
    ])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_cell_times_rejects_lunar(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-03-31", "--divisions", "8",
        "--transitions", "--format", "heatmap", "--calendar", "lunar",
        "--cell-times", "--out", str(tmp_path / "h.png"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--cell-times requires --calendar gregorian" in err


def test_cell_times_rejects_non_heatmap_format(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-31", "--divisions", "8",
        "--transitions", "--format", "chart", "--cell-times",
        "--out", str(tmp_path / "c.png"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--cell-times applies only to --format heatmap" in err


def test_main_title_footer_reach_options(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get",
                        lambda name: (lambda report, out: captured.__setitem__("r", report)))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "16",
        "--format", "csv", "--title", "My T", "--footer", "Source: book",
        "--out", str(tmp_path / "o.csv"),
    ])
    assert rc == 0
    assert captured["r"].options["title"] == "My T"
    assert captured["r"].options["footer"] == "Source: book"


def test_main_labels_csv_populates_abbrevs(tmp_path, monkeypatch):
    csvf = tmp_path / "m.csv"
    csvf.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    captured = {}
    monkeypatch.setattr(cli_mod, "PhaseEphemeris", _LinearEph)
    monkeypatch.setattr(cli_mod.renderers, "get",
                        lambda name: (lambda report, out: captured.__setitem__("r", report)))
    rc = cli_mod.main([
        "--start", "2026-01-01", "--end", "2026-01-10", "--divisions", "16",
        "--format", "csv", "--labels", f"@{csvf}", "--out", str(tmp_path / "o.csv"),
    ])
    assert rc == 0
    assert captured["r"].labels[0] == "Dark Moon"
    assert captured["r"].abbrevs[0] == "Da"
    assert captured["r"].abbrevs[2] is None
