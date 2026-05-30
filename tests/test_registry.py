import pytest

from moonphase import renderers


def test_builtin_renderers_registered():
    names = set(renderers.available())
    assert {"chart", "csv", "json", "terminal"} <= names


def test_modes_for_known_renderers():
    assert "series" in renderers.modes_for("csv")
    assert "events" in renderers.modes_for("csv")


def test_available_filters_by_mode():
    series_formats = set(renderers.available("series"))
    assert "chart" in series_formats and "csv" in series_formats


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        @renderers.register("csv", modes={"series"})
        def _dupe(report, out):
            pass


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        renderers.get("does-not-exist")
