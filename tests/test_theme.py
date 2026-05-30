import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from moonphase.theme import get_theme, style_axes


def test_default_is_dark():
    assert get_theme(None).name == "dark"
    assert get_theme("nonsense").name == "dark"


def test_named_themes_differ():
    assert get_theme("dark").name == "dark"
    assert get_theme("light").name == "light"
    assert get_theme("dark").bg != get_theme("light").bg


def test_theme_palette_is_hex():
    t = get_theme("dark")
    for field in ("bg", "fg", "moon_lit", "moon_dark", "transition", "band", "spine"):
        assert getattr(t, field).startswith("#")


def test_style_axes_sets_dark_background():
    t = get_theme("dark")
    fig, ax = plt.subplots()
    style_axes(fig, ax, t)
    assert ax.get_facecolor()[:3] != (1.0, 1.0, 1.0)   # not white
    assert fig.get_facecolor()[:3] != (1.0, 1.0, 1.0)
    plt.close(fig)
