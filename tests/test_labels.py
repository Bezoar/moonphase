import json

import pytest

from moonphase.labels import resolve_labels, resolve_label_set
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


def test_label_set_none_returns_none_pair():
    assert resolve_label_set(None, S16) == (None, None)


def test_label_set_non_csv_has_no_abbrevs():
    names, abbrevs = resolve_label_set("New,First Quarter,Full,Last Quarter", S4)
    assert names == ["New", "First Quarter", "Full", "Last Quarter"]
    assert abbrevs is None


def test_label_set_csv_file(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\nCrescent Moon,Cr\nEmerging Moon,Em\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[0] == "Dark Moon" and names[3] == "Emerging Moon"
    assert abbrevs[0] == "Da" and abbrevs[3] == "Em"
    assert abbrevs[4] is None              # unfilled slot -> None


def test_label_set_csv_row_index_alignment(tmp_path):
    # row 1 -> index 0 (new / Dark)
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert (names[0], abbrevs[0]) == ("Dark Moon", "Da")
    assert (names[1], abbrevs[1]) == ("Sickle Moon", "Si")


def test_label_set_csv_sparse_abbrev(tmp_path):
    # a row with a name but no second column -> abbrev None for that slot
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon\nCrescent Moon,Cr\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[1] == "Sickle Moon"
    assert abbrevs[1] is None
    assert abbrevs[2] == "Cr"


def test_label_set_csv_first_comma_only(tmp_path):
    # split on the first comma; defensive (names normally have no commas)
    p = tmp_path / "m.csv"
    p.write_text("Full, Moon,Fl\n")
    names, abbrevs = resolve_label_set(f"@{p}", S16)
    assert names[0] == "Full"
    assert abbrevs[0] == "Moon,Fl"          # everything after the first comma


def test_label_set_one_per_line_unchanged(tmp_path):
    p = tmp_path / "names.txt"
    p.write_text("New\n\nFirst Quarter\n")
    names, abbrevs = resolve_label_set(f"@{p}", S8)
    assert names[0] == "New"
    assert names[1] == "Waxing Crescent"     # blank -> built-in
    assert abbrevs is None


def test_resolve_labels_still_returns_names_only(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Dark Moon,Da\nSickle Moon,Si\n")
    assert resolve_labels(f"@{p}", S16)[0] == "Dark Moon"
