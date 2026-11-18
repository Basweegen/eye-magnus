"""Command line interface for eye-magnus."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import __version__
from .format import color_enabled, render_live_lines
from .ollama import collect as collect_llm
from .system import SystemMonitor


def _interactive() -> bool:
    return bool(sys.stdout.isatty()) and os.environ.get("TERM", "dumb") != "dumb"


def _one_shot(args: argparse.Namespace, with_llm: bool) -> int:
    monitor = SystemMonitor(args.disk)
    snapshot = monitor.sample(settle=max(0.0, args.interval))
    llm = collect_llm() if with_llm else None
    snapshot.llm = llm

    if getattr(args, "json", False):
        print(json.dumps(snapshot.to_dict(), indent=2))
    else:
        print("\n".join(render_live_lines(snapshot, llm, color=color_enabled(args.no_color), live=False)))

    if with_llm and llm is not None and not llm.get("available"):
        return 3
    return 0


def _live(args: argparse.Namespace, with_llm: bool) -> int:
    interval = max(0.5, args.interval or 1.0)
    monitor = SystemMonitor(args.disk)
    color = color_enabled(args.no_color)
    sys.stdout.write("\033[?25l")  # hide cursor
    try:
        while True:
            snapshot = monitor.sample()
            llm = collect_llm() if with_llm else None
            snapshot.llm = llm
            screen = "\n".join(render_live_lines(snapshot, llm, color=color))
            sys.stdout.write("\033[2J\033[H" + screen + "\n")
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write("\033[?25h")  # restore cursor
        sys.stdout.flush()


def _add_common(parser: argparse.ArgumentParser, interval: float) -> None:
    parser.add_argument("--disk", default="/", help="mount point to watch (default: /)")
    parser.add_argument("--interval", type=float, default=interval, help="refresh seconds")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eye-magnus",
        description="Magnus System Health Monitoring: read-only, real-time host and local LLM health.",
    )
    parser.add_argument("--version", action="version", version=f"eye-magnus {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser("health", help="one-shot system snapshot")
    health.add_argument("--json", action="store_true", help="emit JSON instead of text")
    _add_common(health, 0.5)

    monitor = commands.add_parser("monitor", help="live terminal view of system health")
    _add_common(monitor, 1.0)

    llm = commands.add_parser("llm", help="system health plus live Ollama inference resources")
    llm.add_argument("--json", action="store_true", help="emit JSON instead of text")
    _add_common(llm, 1.0)

    args = parser.parse_args(argv)

    if args.command == "health":
        return _one_shot(args, with_llm=False)
    if args.command == "monitor":
        one_shot = getattr(args, "json", False) or not _interactive()
        return _one_shot(args, with_llm=False) if one_shot else _live(args, False)
    if args.command == "llm":
        return _one_shot(args, with_llm=True) if args.json or not _interactive() else _live(args, True)
    return 2
