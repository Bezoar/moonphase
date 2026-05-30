"""The frozen context object every renderer consumes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone, tzinfo

from .calendar import PhaseSample
from .events import PhaseEvent
from .microphase import MicrophaseScheme


@dataclass(frozen=True)
class Report:
    scheme: MicrophaseScheme
    mode: str                                  # "series" | "events"
    samples: list[PhaseSample] | None = None   # present iff mode == "series"
    events: list[PhaseEvent] | None = None      # exact events (overlay or primary)
    tz: tzinfo = timezone.utc                  # display tz; UTC until Phase 2
    labels: list[str] | None = None            # custom names; None until Phase 4
