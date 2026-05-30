from moonphase.renderers.celltext import damped_text_color


def test_bright_cell_gets_darker_text_but_not_pure_black():
    c = damped_text_color((0.9, 0.9, 0.9), contrast=0.55)
    assert all(0.0 < ch < 0.9 for ch in c)       # darker than cell, not black


def test_dark_cell_gets_lighter_text_but_not_pure_white():
    c = damped_text_color((0.1, 0.1, 0.1), contrast=0.55)
    assert all(0.1 < ch < 1.0 for ch in c)       # lighter than cell, not white


def test_contrast_zero_returns_cell_and_one_returns_target():
    cell = (0.2, 0.4, 0.6)
    assert damped_text_color(cell, contrast=0.0) == cell      # invisible end
    # luminance(cell) < 0.5 -> target white
    assert damped_text_color(cell, contrast=1.0) == (1.0, 1.0, 1.0)
