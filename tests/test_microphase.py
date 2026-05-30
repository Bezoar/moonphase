from moonphase.microphase import MicrophaseScheme, phase_to_index


def test_divisions_scheme():
    s = MicrophaseScheme.from_divisions(8)
    assert s.divisions == 8
    assert s.step_deg == 45.0


def test_step_scheme():
    s = MicrophaseScheme.from_step(1.0)
    assert s.divisions == 360
    assert s.step_deg == 1.0


def test_centered_buckets_standard_four():
    s = MicrophaseScheme.from_divisions(4)
    # k*step is the CENTER of microphase k
    assert phase_to_index(0.0, s) == 0      # New (center)
    assert phase_to_index(44.0, s) == 0     # still inside New arc
    assert phase_to_index(46.0, s) == 1     # crossed into First Quarter arc
    assert phase_to_index(90.0, s) == 1     # First Quarter center
    assert phase_to_index(180.0, s) == 2    # Full center
    assert phase_to_index(270.0, s) == 3    # Last Quarter center


def test_transition_boundaries_round_half_up():
    s = MicrophaseScheme.from_divisions(4)
    # transition points (k+0.5)*step assign UP to the higher-index arc
    assert phase_to_index(45.0, s) == 1
    assert phase_to_index(135.0, s) == 2
    assert phase_to_index(225.0, s) == 3
    assert phase_to_index(315.0, s) == 0    # wraps up into New (index 4 mod 4)
    assert phase_to_index(314.9, s) == 3    # just below stays in Last Quarter


def test_centered_buckets_sixteen_fractional_step():
    s = MicrophaseScheme.from_divisions(16)  # step 22.5
    assert phase_to_index(11.25, s) == 1     # exact transition -> up
    assert phase_to_index(33.75, s) == 2     # exact transition -> up
    assert phase_to_index(0.0, s) == 0
    assert phase_to_index(359.999, s) == 0   # wraps to New center


def test_wrap_around():
    s = MicrophaseScheme.from_divisions(32)
    assert phase_to_index(360.0, s) == 0
    assert phase_to_index(-1.0, s) == 0      # just before New center -> New
