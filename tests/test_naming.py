from moonphase.microphase import MicrophaseScheme
from moonphase.naming import default_name


def test_names_for_four():
    s = MicrophaseScheme.from_divisions(4)
    assert default_name(0, s) == "New"
    assert default_name(1, s) == "First Quarter"
    assert default_name(2, s) == "Full"
    assert default_name(3, s) == "Last Quarter"


def test_names_for_eight():
    s = MicrophaseScheme.from_divisions(8)
    assert default_name(0, s) == "New"
    assert default_name(1, s) == "Waxing Crescent"
    assert default_name(4, s) == "Full"
    assert default_name(7, s) == "Waning Crescent"


def test_no_names_for_other_divisions():
    s = MicrophaseScheme.from_divisions(16)
    assert default_name(0, s) is None
    assert default_name(5, s) is None
