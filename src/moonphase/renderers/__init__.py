"""Output renderer registry.

Adding a new format (PDF, HTML, ICS, ...) is a one-liner: define a function
``render(samples, scheme, out)`` and decorate with ``@register("name")``.
The CLI exposes every registered name via ``--format``.
"""

from __future__ import annotations

from typing import Callable, Iterable

from ..calendar import PhaseSample
from ..microphase import MicrophaseScheme

Renderer = Callable[[Iterable[PhaseSample], MicrophaseScheme, str | None], None]

_REGISTRY: dict[str, Renderer] = {}


def register(name: str) -> Callable[[Renderer], Renderer]:
    def deco(fn: Renderer) -> Renderer:
        if name in _REGISTRY:
            raise ValueError(f"renderer {name!r} already registered")
        _REGISTRY[name] = fn
        return fn
    return deco


def get(name: str) -> Renderer:
    try:
        return _REGISTRY[name]
    except KeyError as e:
        raise KeyError(f"unknown renderer {name!r}; available: {sorted(_REGISTRY)}") from e


def available() -> list[str]:
    return sorted(_REGISTRY)


# Import side-effect: register built-in renderers.
from . import chart, data, terminal  # noqa: E402,F401
