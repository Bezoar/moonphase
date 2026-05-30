import json

import pytest

from moonphase.labels import resolve_labels
from moonphase.microphase import MicrophaseScheme

S4 = MicrophaseScheme.from_divisions(4)
S8 = MicrophaseScheme.from_divisions(8)
S16 = MicrophaseScheme.from_divisions(16)


def test_none_spec_returns_none():
    assert resolve_labels(None, S16) is None


def test_inline_full_list():
    got = resolve_labels("New,Cres,Quarter,Gibbous", S4)
    assert got == ["New", "Cres", "Quarter", "Gibbous"]


def test_inline_sparse_falls_back_to_builtin():
    # blanks fall back to the built-in 8-division names
    got = resolve_labels("New,,First Quarter", S8)
    assert got[0] == "New"
    assert got[1] == "Waxing Crescent"      # blank -> built-in
    assert got[2] == "First Quarter"
    assert got[4] == "Full"                 # unspecified -> built-in


def test_inline_extras_ignored():
    got = resolve_labels("A,B,C,D,E,F", S4)   # 6 names for 4 arcs
    assert got == ["A", "B", "C", "D"]


def test_sixteen_unfilled_is_none():
    got = resolve_labels("New", S16)
    assert got[0] == "New"
    assert got[5] is None                    # no built-in for N=16, not overridden


def test_at_file_one_per_line(tmp_path):
    p = tmp_path / "names.txt"
    p.write_text("New\n\nFirst Quarter\n")    # blank line 2 -> fallback
    got = resolve_labels(f"@{p}", S8)
    assert got[0] == "New"
    assert got[1] == "Waxing Crescent"        # blank line -> built-in
    assert got[2] == "First Quarter"


def test_at_file_json_map(tmp_path):
    p = tmp_path / "names.json"
    p.write_text(json.dumps({"0": "Dark", "4": "Bright"}))
    got = resolve_labels(f"@{p}", S8)
    assert got[0] == "Dark"
    assert got[4] == "Bright"
    assert got[2] == "First Quarter"          # unspecified -> built-in


def test_at_file_json_out_of_range_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"9": "Nope"}))   # 9 not in 0..7
    with pytest.raises(ValueError):
        resolve_labels(f"@{p}", S8)


def test_missing_file_raises_valueerror(tmp_path):
    with pytest.raises(ValueError):
        resolve_labels(f"@{tmp_path / 'nope.txt'}", S8)
