"""Display-timezone resolution, conversion, and human captions.

Phase 1 emitted UTC. This module resolves a single display timezone per run:
(1) an explicit offset on the start datetime, else (2) the system-local zone,
else (3) UTC. All computation stays in UTC; only output is converted to the
display zone. Local conversion uses ``datetime.astimezone()`` with no argument,
so DST is handled correctly per instant without any extra dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _fmt_offset(off: timedelta) -> str:
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


class DisplayZone:
    """How output timestamps are localized and labeled.

    ``kind`` is "utc", "fixed" (a constant offset), or "local" (the system
    zone, converted per-instant so DST is correct).
    """

    def __init__(self, kind: str, offset: timedelta | None = None):
        if kind not in ("utc", "fixed", "local"):
            raise ValueError(f"bad DisplayZone kind {kind!r}")
        self.kind = kind
        self._tz = (timezone.utc if kind == "utc"
                    else timezone(offset) if kind == "fixed"
                    else None)

    @classmethod
    def utc(cls) -> "DisplayZone":
        return cls("utc")

    @classmethod
    def resolve(cls, start: datetime) -> "DisplayZone":
        """Aware ``start`` -> its offset (UTC if zero). Naive ``start`` ->
        system-local if discernible, else UTC."""
        if start.tzinfo is not None:
            off = start.utcoffset() or timedelta(0)
            return cls("utc") if off == timedelta(0) else cls("fixed", off)
        try:
            local = datetime.now().astimezone().tzinfo
        except Exception:
            local = None
        return cls("local") if local is not None else cls("utc")

    def to_utc(self, dt: datetime) -> datetime:
        """Interpret ``dt`` in this zone; return the UTC-aware instant.

        An aware ``dt`` is converted directly. A naive ``dt`` is read as a
        wall-clock time in this zone.
        """
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        if self.kind == "utc":
            return dt.replace(tzinfo=timezone.utc)
        if self.kind == "fixed":
            return dt.replace(tzinfo=self._tz).astimezone(timezone.utc)
        return dt.astimezone(timezone.utc)  # local: naive read as system-local

    def to_display(self, dt: datetime) -> datetime:
        """Convert a UTC-aware instant into this display zone, DST-aware."""
        if self.kind == "local":
            return dt.astimezone()
        return dt.astimezone(self._tz)

    def caption(self, start_utc: datetime | None = None,
                end_utc: datetime | None = None) -> str:
        """Human label, e.g. 'UTC', 'UTC-08:00', 'local time (PST)',
        'local time (PST/PDT, DST changes within range)'."""
        if self.kind == "utc":
            return "UTC"
        if self.kind == "fixed":
            return "UTC" + _fmt_offset(self._tz.utcoffset(None))
        if start_utc is None:
            return "local time"
        a = start_utc.astimezone().tzname()
        b = (end_utc or start_utc).astimezone().tzname()
        if a == b:
            return f"local time ({a})"
        return f"local time ({a}/{b}, DST changes within range)"
