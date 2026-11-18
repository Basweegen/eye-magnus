"""Terminal rendering for snapshots. Colors follow usage thresholds."""

from __future__ import annotations

import os
import sys

from .system import Snapshot

MIB = 1024 * 1024
GREEN = "\033[38;2;34;197;94m"
AMBER = "\033[38;2;245;158;11m"
RED = "\033[38;2;239;68;68m"
RESET = "\033[0m"


def color_enabled(no_color: bool = False) -> bool:
    if no_color or os.environ.get("NO_COLOR"):
        return False
    return bool(sys.stdout.isatty())


def bar(percent: float, width: int = 20, color: bool = True) -> str:
    value = max(0.0, min(100.0, float(percent)))
    filled = int(round(value * width / 100))
    text = "\u2588" * filled + "\u2591" * (width - filled)
    if not color:
        return text
    shade = RED if value >= 85 else AMBER if value >= 60 else GREEN
    return f"{shade}{text}{RESET}"


def human(value: float) -> str:
    amount = float(value)
    for unit in ("B", "K", "M", "G", "T", "P"):
        if abs(amount) < 1024 or unit == "P":
            return f"{amount:.1f}{unit}"
        amount /= 1024
    return f"{amount:.1f}P"


def rate(value: float) -> str:
    return human(value) + "/s"


def render(snapshot: Snapshot, llm: dict | None = None, color: bool = True, llm_view: bool = False) -> list[str]:
    lines = [
        f"Magnus System Health Monitoring   {snapshot.timestamp}",
        "",
        f"CPU   {bar(snapshot.cpu_percent, color=color)} {snapshot.cpu_percent:5.1f}%  {snapshot.cpu_threads} threads",
        f"RAM   {bar(snapshot.ram.percent, color=color)} {snapshot.ram.percent:5.1f}%  {human(snapshot.ram.used)}/{human(snapshot.ram.total)}",
        f"SWAP  {bar(snapshot.swap.percent, color=color)} {snapshot.swap.percent:5.1f}%  {human(snapshot.swap.used)}/{human(snapshot.swap.total)}",
        f"DISK  {bar(snapshot.disk.percent, color=color)} {snapshot.disk.percent:5.1f}%  {human(snapshot.disk.used)}/{human(snapshot.disk.total)}  (root)",
        "",
        f"Disk I/O   read {rate(snapshot.disk_read_bps)}   write {rate(snapshot.disk_write_bps)}",
        f"Network    down {rate(snapshot.net_recv_bps)}   up {rate(snapshot.net_send_bps)}",
    ]

    gpu = snapshot.gpu or {}
    gpu_percent = float(gpu.get("percent", 0) or 0)
    lines.append(
        f"GPU    {bar(gpu_percent, color=color)} {gpu_percent:5.1f}%  "
        f"{human((gpu.get('used_mib', 0) or 0) * MIB)}/{human((gpu.get('total_mib', 0) or 0) * MIB)}  "
        f"({gpu.get('mode', 'unknown')})"
    )

    if llm is not None:
        lines.append("")
        lines.append("AI inference health (Ollama, read-only)")
        if not llm.get("available"):
            lines.append(f"  unavailable: {llm.get('error', 'unknown error')}")
        else:
            lines.append(
                f"  Ollama {llm.get('version', '?')} | installed {llm.get('installed_count', 0)} | "
                f"running {llm.get('running_count', 0)} | model VRAM {human(llm.get('running_vram_bytes', 0))}"
            )
            for model in llm.get("running", []):
                lines.append(
                    f"  - {model['name']}  size {human(model['size_bytes'])}  "
                    f"vram {human(model['vram_bytes'])}  ctx {model['context_length']}  "
                    f"expires {model['expires_at'] or '-'}"
                )
            if not llm.get("running"):
                lines.append("  no models currently loaded")

    return lines


def render_live_lines(snapshot: Snapshot, llm: dict | None = None, color: bool = True, live: bool = True) -> list[str]:
    """Compact rendering. Adds the stop hint only in live mode."""
    lines = render(snapshot, llm, color=color, llm_view=llm is not None)
    while lines and lines[-1] == "":
        lines.pop()
    if live:
        lines.append("Ctrl+C to stop")
    return lines
