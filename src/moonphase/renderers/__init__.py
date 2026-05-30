"""Output renderer registry.

A renderer is ``render(report, out) -> None``. Register it with the modes it
supports; the CLI uses ``available(mode)`` to validate ``--format`` against
the resolved mode.
"""

from __future__ import annotations

from typing import Callable

from ..report import Report

Renderer = Callable[[Report, "str | None"], None]

_REGISTRY: dict[str, dict] = {}


def register(name: str, modes):
    """Decorator: register ``fn`` as renderer ``name`` supporting ``modes``
    (a set/iterable of "series" / "events")."""
    modes = frozenset(modes)
    if not modes <= {"series", "events"}:
        raise ValueError(f"invalid modes {set(modes)!r} for renderer {name!r}")

    def deco(fn: Renderer) -> Renderer:
        if name in _REGISTRY:
            raise ValueError(f"renderer {name!r} already registered")
        _REGISTRY[name] = {"fn": fn, "modes": modes}
        return fn
    return deco


def get(name: str) -> Renderer:
    try:
        return _REGISTRY[name]["fn"]
    except KeyError as e:
        raise KeyError(f"unknown renderer {name!r}; available: {sorted(_REGISTRY)}") from e


def modes_for(name: str) -> frozenset:
    try:
        return _REGISTRY[name]["modes"]
    except KeyError as e:
        raise KeyError(f"unknown renderer {name!r}; available: {sorted(_REGISTRY)}") from e


def available(mode: str | None = None) -> list[str]:
    if mode is None:
        return sorted(_REGISTRY)
    return sorted(n for n, v in _REGISTRY.items() if mode in v["modes"])


# Import side-effect: register built-in renderers.
from . import chart, data, terminal, almanac  # noqa: E402,F401
