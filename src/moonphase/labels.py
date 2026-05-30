"""Resolve a ``--labels`` spec into per-microphase names.

A spec is either an inline comma list (positional) or ``@path`` to a file that
is one-name-per-line (positional, blank lines skipped) or a JSON ``{index:
name}`` map. Provided names override; everything else falls back to the
built-in name (for N in {4, 8}) or ``None``.
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


def resolve_labels(spec: str | None, scheme: MicrophaseScheme) -> list[str | None] | None:
    """Return a length-``divisions`` list of names (or ``None`` per slot), or
    ``None`` if ``spec`` is ``None``. Provided names win; gaps fall back to the
    built-in name or ``None``."""
    if spec is None:
        return None
    n = scheme.divisions
    overrides = _parse_overrides(spec, n)
    return [overrides.get(i) or default_name(i, scheme) for i in range(n)]
