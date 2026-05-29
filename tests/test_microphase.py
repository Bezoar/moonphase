from moonphase.microphase import MicrophaseScheme, phase_to_index


def test_divisions_scheme():
    s = MicrophaseScheme.from_divisions(8)
    assert s.divisions == 8
    assert s.step_deg == 45.0


def test_step_scheme():
    s = MicrophaseScheme.from_step(1.0)
    assert s.divisions == 360
    assert s.step_deg == 1.0


def test_phase_buckets_standard_four():
    s = MicrophaseScheme.from_divisions(4)
    assert phase_to_index(0.0, s) == 0       # new
    assert phase_to_index(90.0, s) == 1      # first quarter
    assert phase_to_index(180.0, s) == 2     # full
    assert phase_to_index(270.0, s) == 3     # last quarter
    assert phase_to_index(359.999, s) == 3


def test_wrap_around():
    s = MicrophaseScheme.from_divisions(32)
    assert phase_to_index(360.0, s) == 0
    assert phase_to_index(-1.0, s) == 31
