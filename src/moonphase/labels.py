"""Resolve a ``--labels`` spec into per-microphase names.

A spec is either an inline comma list (positional) or ``@path`` to a file that
is one-name-per-line (positional, blank lines skipped), a JSON ``{index: name}``
map, or a 2-column ``name,abbrev`` CSV (one ``Full Name,AB`` per line, row order =
microphase index), which additionally sets a short abbreviation per phase.
Provided names override; everything else falls back to the built-in name (for N
in {4, 8}) or ``None``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .microphase import MicrophaseScheme
from .naming import default_name


def _parse_overrides(spec: str, n: int) -> dict[int, str]:
    if spec.startswith("@"):
        path = Path(spec[1:])
        try:
            text = path.read_text()
        except OSError as e:
            raise ValueError(f"cannot read --labels file {str(path)!r}: {e}") from e
        stripped = text.strip()
        if stripped.startswith("{"):
            data = json.loads(stripped)              # JSONDecodeError is a ValueError
            out: dict[int, str] = {}
            for k, v in data.items():
                i = int(k)
                if not 0 <= i < n:
                    raise ValueError(f"--labels index {i} out of range 0..{n - 1}")
                name = str(v).strip()
                if name:
                    out[i] = name
            return out
        return {i: line.strip() for i, line in enumerate(text.splitlines())
                if i < n and line.strip()}
    return {i: part.strip() for i, part in enumerate(spec.split(","))
            if i < n and part.strip()}


def _parse_csv(text: str, n: int) -> tuple[dict[int, str], dict[int, str]]:
    """Parse a 2-column ``name,abbrev`` CSV. Physical line order is the
    microphase index (line 1 -> index 0), matching the one-name-per-line form.
    Split on the first comma only; blank/missing fields leave that slot unset."""
    names: dict[int, str] = {}
    abbrevs: dict[int, str] = {}
    for i, line in enumerate(text.splitlines()):
        if i >= n:
            break
        name, _, abbr = line.partition(",")
        name, abbr = name.strip(), abbr.strip()
        if name:
            names[i] = name
        if abbr:
            abbrevs[i] = abbr
    return names, abbrevs


def resolve_label_set(
    spec: str | None, scheme: MicrophaseScheme
) -> tuple[list[str] | None, list[str] | None]:
    """Return ``(names, abbrevs)``. ``names`` is the resolved label list (built-in
    fallbacks applied) or ``None``; ``abbrevs`` is a length-``divisions`` list of
    codes-or-``None``, but only when ``spec`` is a 2-column ``@file`` CSV — every
    other spec form yields ``abbrevs is None``."""
    if spec is None:
        return None, None
    n = scheme.divisions
    if spec.startswith("@"):
        path = Path(spec[1:])
        try:
            text = path.read_text()
        except OSError as e:
            raise ValueError(f"cannot read --labels file {str(path)!r}: {e}") from e
        # CSV when it is not JSON and any line carries a comma. (Names have no
        # commas, so a comma signals the second 'abbrev' column.)
        if not text.strip().startswith("{") and any("," in ln for ln in text.splitlines()):
            names_d, abbr_d = _parse_csv(text, n)
            names = [names_d.get(i) or default_name(i, scheme) for i in range(n)]
            abbrevs = [abbr_d.get(i) for i in range(n)]
            return names, abbrevs
    overrides = _parse_overrides(spec, n)
    names = [overrides.get(i) or default_name(i, scheme) for i in range(n)]
    return names, None


def resolve_labels(spec: str | None, scheme: MicrophaseScheme) -> list[str | None] | None:
    """Names only (back-compatible wrapper over :func:`resolve_label_set`)."""
    return resolve_label_set(spec, scheme)[0]
