"""Built-in microphase names for the familiar 4- and 8-division schemes.

Custom names (the ``--labels`` flag) are a later phase; this module only
provides the traditional names, used when ``divisions`` is 4 or 8.
"""

from __future__ import annotations

from .microphase import MicrophaseScheme

_NAMES_4 = ["New", "First Quarter", "Full", "Last Quarter"]
_NAMES_8 = [
    "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


def default_name(index: int, scheme: MicrophaseScheme) -> str | None:
    """Traditional name for microphase ``index``, or ``None`` if the scheme
    has no built-in names (any ``divisions`` other than 4 or 8)."""
    if scheme.divisions == 4:
        return _NAMES_4[index % 4]
    if scheme.divisions == 8:
        return _NAMES_8[index % 8]
    return None
