"""The frozen context object every renderer consumes."""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import PhaseSample
from .displaytz import DisplayZone
from .events import PhaseEvent
from .microphase import MicrophaseScheme

_UTC = DisplayZone.utc()


@dataclass(frozen=True)
class Report:
    scheme: MicrophaseScheme
    mode: str                                  # "series" | "events"
    samples: list[PhaseSample] | None = None   # present iff mode == "series"
    events: list[PhaseEvent] | None = None      # exact events (overlay or primary)
    tz: DisplayZone = _UTC                      # display timezone (UTC by default)
    labels: list[str] | None = None            # custom names; None until Phase 4
