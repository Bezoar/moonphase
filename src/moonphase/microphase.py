"""Microphase scheme: arbitrary division of the 360° synodic cycle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MicrophaseScheme:
    """A partition of the synodic cycle into equal angular slices.

    Exactly one of ``divisions`` or ``step_deg`` defines the scheme; the
    other is derived. Phase angle 0° is conventionally new moon (Sun and
    Moon at equal ecliptic longitude).
    """

    divisions: int
    step_deg: float

    @classmethod
    def from_divisions(cls, divisions: int) -> "MicrophaseScheme":
        if divisions < 1:
            raise ValueError("divisions must be >= 1")
        return cls(divisions=divisions, step_deg=360.0 / divisions)

    @classmethod
    def from_step(cls, step_deg: float) -> "MicrophaseScheme":
        if step_deg <= 0 or step_deg > 360:
            raise ValueError("step_deg must be in (0, 360]")
        # Allow non-integer divisions in principle, but round when exact.
        n = 360.0 / step_deg
        divisions = int(round(n))
        if abs(n - divisions) > 1e-9:
            # Non-uniform tail: keep exact step, report ceil divisions.
            divisions = int(n) + 1
        return cls(divisions=divisions, step_deg=step_deg)


def phase_to_index(phase_deg: float, scheme: MicrophaseScheme) -> int:
    """Map a phase angle in [0, 360) to its microphase bucket index."""
    a = phase_deg % 360.0
    idx = int(a // scheme.step_deg)
    if idx >= scheme.divisions:
        idx = scheme.divisions - 1
    return idx
