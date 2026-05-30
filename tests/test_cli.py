import pytest

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
