"""Command-line entry point: ``moonphase --start ... --end ... [--divisions N | --step Xdeg]``."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta

from dataclasses import replace

from . import renderers
from .calendar import build_series
from .displaytz import DisplayZone
from .ephemeris import PhaseEphemeris
from .events import build_events
from .labels import resolve_labels
from .microphase import MicrophaseScheme
from .report import Report


def resolve_mode(fmt, requested, modes_for):
    """Resolve the effective render mode for ``fmt``.

    ``requested`` is the user's --mode (or None). ``modes_for(fmt)`` returns
    the set of modes the format supports. Single-mode formats auto-resolve;
    multi-mode formats default to "series"; an incompatible explicit mode
    raises ValueError listing the supported modes.
    """
    supported = modes_for(fmt)
    if requested is None:
        if len(supported) == 1:
            return next(iter(supported))
        return "series"
    if requested not in supported:
        raise ValueError(
            f"format {fmt!r} supports mode(s): {', '.join(sorted(supported))}"
        )
    return requested


def _label_events(events, labels):
    """Override phase-center event names from resolved labels (transitions keep
    their None name)."""
    if not labels:
        return events
    return [replace(e, name=labels[e.index]) if e.kind == "center" else e
            for e in events]


_STEP_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(deg|d|°)?\s*$", re.IGNORECASE)


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD or full ISO 8601. Naive input stays naive (its zone is
    resolved later); ISO input with an offset stays aware."""
    try:
        if "T" in s or " " in s:
            return datetime.fromisoformat(s)
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"bad date {s!r}: {e}") from e


def _parse_step_deg(s: str) -> float:
    m = _STEP_RE.match(s)
    if not m:
        raise argparse.ArgumentTypeError(f"bad --step {s!r}; expected e.g. '1deg' or '0.5'")
    return float(m.group(1))


def _parse_sample(s: str) -> timedelta:
    m = re.match(r"^\s*([0-9]+)\s*([smhd])\s*$", s, re.IGNORECASE)
    if not m:
        raise argparse.ArgumentTypeError(f"bad --sample {s!r}; expected e.g. '1h', '30m', '1d'")
    n, unit = int(m.group(1)), m.group(2).lower()
    return {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
            "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]


_SIZE_RE = re.compile(r"^\s*([0-9]+)\s*[xX]\s*([0-9]+)\s*$")


def _parse_size(s: str) -> tuple[int, int]:
    """Parse pixel dimensions ``WIDTHxHEIGHT``, e.g. '5000x3000'."""
    m = _SIZE_RE.match(s)
    if not m:
        raise argparse.ArgumentTypeError(
            f"bad --size {s!r}; expected e.g. '5000x3000' (WIDTHxHEIGHT)")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("--size dimensions must be positive")
    return (w, h)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moonphase", description=__doc__)
    p.add_argument("--start", type=_parse_date, required=True,
                   help="start date (YYYY-MM-DD or ISO 8601); bare dates use local time")
    p.add_argument("--end", type=_parse_date, required=True,
                   help="end date (YYYY-MM-DD or ISO 8601); bare dates use local time")

    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--divisions", type=int, help="number of equal microphases per synodic cycle")
    g.add_argument("--step", type=_parse_step_deg,
                   help="angular width of each microphase, e.g. '1deg', '0.5'")

    p.add_argument("--sample", type=_parse_sample, default=timedelta(hours=1),
                   help="sampling cadence (default: 1h)")
    p.add_argument("--mode", choices=["series", "events"], default=None,
                   help="output mode; auto-resolved from --format when omitted")
    p.add_argument("--transitions", action="store_true",
                   help="include transition points (overlays in series; rows in events)")
    p.add_argument("--theme", choices=["dark", "light"], default="dark",
                   help="color theme for rendered charts (default: dark)")
    p.add_argument("--tint", choices=["illumination", "index"], default="illumination",
                   help="heatmap cell tint (heatmap only)")
    p.add_argument("--calendar", choices=["gregorian", "lunar"], default="gregorian",
                   help="heatmap layout: civil months or lunar months")
    p.add_argument("--lunar-anchor", choices=["new", "full"], default="new",
                   help="lunar-month boundary (with --calendar lunar)")
    p.add_argument("--labels", default=None,
                   help="custom microphase names: inline comma list or @file "
                        "(one per line, or JSON index->name); sparse-merged over built-ins")
    p.add_argument("--format", default="chart", choices=renderers.available(),
                   help="output renderer")
    p.add_argument("--out", default=None,
                   help="output path; format inferred from extension where applicable")
    p.add_argument("--ephemeris", default=None,
                   help="path to a JPL .bsp kernel; default downloads DE421 to ./data/")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    scheme = (MicrophaseScheme.from_divisions(args.divisions)
              if args.divisions is not None
              else MicrophaseScheme.from_step(args.step))

    try:
        mode = resolve_mode(args.format, args.mode, renderers.modes_for)
        labels = resolve_labels(args.labels, scheme)
    except (ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    zone = DisplayZone.resolve(args.start)
    start_utc = zone.to_utc(args.start)
    end_utc = zone.to_utc(args.end)

    options = {"theme": args.theme, "tint": args.tint, "calendar": args.calendar,
               "lunar_anchor": args.lunar_anchor}

    eph = PhaseEphemeris(kernel_path=args.ephemeris)

    if mode == "events":
        # --sample does not apply in events mode (events are root-found, not sampled)
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        events = _label_events(events, labels)
        report = Report(scheme=scheme, mode="events", events=events, tz=zone,
                        options=options, labels=labels)
    else:
        samples = build_series(start_utc, end_utc, scheme,
                               sample_step=args.sample, ephemeris=eph)
        events = build_events(start_utc, end_utc, scheme, eph,
                              transitions=args.transitions)
        events = _label_events(events, labels)
        report = Report(scheme=scheme, mode="series", samples=samples,
                        events=events, tz=zone, options=options, labels=labels)

    try:
        renderers.get(args.format)(report, args.out)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
