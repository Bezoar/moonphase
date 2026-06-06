import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from moonphase.microphase import MicrophaseScheme
from moonphase.renderers.chrome import draw_footer, resolved_title
from moonphase.report import Report
from moonphase.theme import get_theme

S4 = MicrophaseScheme.from_divisions(4)


def _report(options=None):
    return Report(scheme=S4, mode="series", samples=[], options=options)


def test_resolved_title_prefers_override():
    assert resolved_title(_report({"title": "Custom"}), "auto") == "Custom"


def test_resolved_title_falls_back_to_default():
    assert resolved_title(_report(None), "auto") == "auto"
    assert resolved_title(_report({"title": None}), "auto") == "auto"


def test_resolved_title_empty_string_falls_back():
    # empty string is falsy -> default
    assert resolved_title(_report({"title": ""}), "auto") == "auto"


def test_draw_footer_adds_figure_text():
    fig = plt.figure()
    try:
        draw_footer(fig, _report({"footer": "cite me"}), get_theme("dark"))
        assert any(t.get_text() == "cite me" for t in fig.texts)
    finally:
        plt.close(fig)


def test_draw_footer_noop_when_unset():
    fig = plt.figure()
    try:
        before = len(fig.texts)
        draw_footer(fig, _report(None), get_theme("dark"))
        assert len(fig.texts) == before
    finally:
        plt.close(fig)


def test_draw_footer_multiline_enlarges_bottom_margin():
    fig = plt.figure()
    try:
        draw_footer(fig, _report({"footer": "line1\nline2\nline3"}), get_theme("dark"))
        assert any(t.get_text() == "line1\nline2\nline3" for t in fig.texts)
        assert fig.subplotpars.bottom >= 0.05 + 0.03 * 3 + 0.02  # pad for 3 lines
    finally:
        plt.close(fig)
