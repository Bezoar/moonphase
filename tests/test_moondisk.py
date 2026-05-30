from moonphase.moondisk import illuminated_fraction, lit_polygon


def test_illuminated_fraction():
    assert illuminated_fraction(0) == 0.0
    assert abs(illuminated_fraction(90) - 0.5) < 1e-9
    assert abs(illuminated_fraction(180) - 1.0) < 1e-9
    assert abs(illuminated_fraction(270) - 0.5) < 1e-9


def test_new_moon_has_no_polygon():
    assert lit_polygon(0, 0, 1.0, 0.0) is None
    assert lit_polygon(0, 0, 1.0, 360.0) is None


def _xrange(poly):
    xs = [x for x, _ in poly]
    return min(xs), max(xs)


def test_full_moon_spans_whole_disk():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 180.0))
    assert lo < -0.98 and hi > 0.98


def test_first_quarter_is_right_half():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 90.0))
    assert abs(lo) < 0.02 and hi > 0.98          # lit from center to right limb


def test_last_quarter_is_left_half():
    lo, hi = _xrange(lit_polygon(0, 0, 1.0, 270.0))
    assert lo < -0.98 and abs(hi) < 0.02         # lit from left limb to center


def test_waxing_crescent_lit_on_right():
    # thin crescent: lit region hugs the right limb (mean x > 0)
    poly = lit_polygon(0, 0, 1.0, 45.0)
    mean_x = sum(x for x, _ in poly) / len(poly)
    assert mean_x > 0.3


def test_waning_crescent_lit_on_left():
    poly = lit_polygon(0, 0, 1.0, 315.0)
    mean_x = sum(x for x, _ in poly) / len(poly)
    assert mean_x < -0.3
