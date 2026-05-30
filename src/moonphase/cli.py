"""Command-line entry point: ``moonphase --start ... --end ... [--divisions N | --step Xdeg]``."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone

from . import renderers
from .calendar import build_series
from .ephemeris import PhaseEphemeris
from .events import build_events
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


_STEP_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(deg|d|°)?\s*$", re.IGNORECASE)


def _parse_date(s: str) -> datetime:
    # Accept YYYY-MM-DD or full ISO 8601.
    try:
        if "T" in s or " " in s:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc) \
                if datetime.fromisoformat(s).tzinfo is None else datetime.fromisoformat(s)
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moonphase", description=__doc__)
    p.add_argument("--start", type=_parse_date, required=True, help="UTC start date (YYYY-MM-DD)")
    p.add_argument("--end", type=_parse_date, required=True, help="UTC end date (YYYY-MM-DD)")

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
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    eph = PhaseEphemeris(kernel_path=args.ephemeris)

    if mode == "events":
        # --sample does not apply in events mode (events are root-found, not sampled)
        events = build_events(args.start, args.end, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="events", events=events)
    else:
        samples = build_series(args.start, args.end, scheme,
                               sample_step=args.sample, ephemeris=eph)
        # series-mode events: phase centers always, transitions when requested
        events = build_events(args.start, args.end, scheme, eph,
                              transitions=args.transitions)
        report = Report(scheme=scheme, mode="series", samples=samples, events=events)

    renderers.get(args.format)(report, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
