import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from moonphase.displaytz import DisplayZone


@contextmanager
def _tz(name):
    """Force the system local timezone for the duration of the block (POSIX)."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_resolve_aware_utc():
    z = DisplayZone.resolve(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert z.kind == "utc"
    assert z.caption() == "UTC"


def test_resolve_aware_fixed_offset():
    z = DisplayZone.resolve(datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-8))))
    assert z.kind == "fixed"
    assert z.caption() == "UTC-08:00"


def test_resolve_naive_is_local():
    with _tz("America/Los_Angeles"):
        z = DisplayZone.resolve(datetime(2026, 1, 1))  # naive
        assert z.kind == "local"


def test_to_utc_fixed_offset_interprets_wall_clock():
    z = DisplayZone("fixed", timedelta(hours=-8))
    got = z.to_utc(datetime(2026, 1, 1, 0, 0))  # naive midnight in UTC-08:00
    assert got == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_to_utc_local_interprets_wall_clock():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        # Jan 1 2026 is PST (UTC-8): local midnight -> 08:00 UTC
        got = z.to_utc(datetime(2026, 1, 1, 0, 0))
        assert got == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_to_display_local_is_dst_aware():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        winter = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)  # PST -08
        summer = datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)  # PDT -07
        assert z.to_display(winter).utcoffset() == timedelta(hours=-8)
        assert z.to_display(summer).utcoffset() == timedelta(hours=-7)


def test_caption_local_notes_dst_change():
    with _tz("America/Los_Angeles"):
        z = DisplayZone("local")
        jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
        jul = datetime(2026, 7, 1, tzinfo=timezone.utc)
        same = z.caption(jan, jan)
        spanning = z.caption(jan, jul)
        assert "PST" in same and "DST" not in same
        assert "DST changes within range" in spanning


def test_utc_roundtrip_and_caption():
    z = DisplayZone.utc()
    dt = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)
    assert z.to_display(dt) == dt
    assert z.to_utc(datetime(2026, 5, 1, 12)) == dt  # naive read as UTC
    assert z.caption() == "UTC"
