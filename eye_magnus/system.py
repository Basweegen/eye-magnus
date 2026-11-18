"""Read-only host telemetry for Magnus System Health Monitoring.

Nothing in this module writes to disk, executes a shell command, or contacts a
network service. All figures come from the local kernel interfaces exposed by
psutil, plus the framebuffer/aperture information in sysfs.
"""

from __future__ import annotations

import glob
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import psutil

MIB = 1024 * 1024


@dataclass
class Usage:
    used: int
    total: int
    percent: float


@dataclass
class Snapshot:
    timestamp: str
    cpu_percent: float
    cpu_threads: int
    ram: Usage
    swap: Usage
    disk: Usage
    disk_read_bps: float
    disk_write_bps: float
    net_recv_bps: float
    net_send_bps: float
    gpu: dict
    llm: dict | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("ram", "swap", "disk"):
            usage: Usage = getattr(self, key)
            data[key]["used_mib"] = round(usage.used / MIB, 1)
            data[key]["total_mib"] = round(usage.total / MIB, 1)
        return data


class SystemMonitor:
    """Samples host counters. The first sample has zero I/O rates by design."""

    def __init__(self, disk_path: str = "/") -> None:
        self.disk_path = disk_path
        psutil.cpu_percent(interval=None)  # prime the delta counter
        self._previous: dict | None = None

    def sample(self, settle: float = 0.0) -> Snapshot:
        if settle > 0:
            time.sleep(settle)

        now = time.monotonic()
        cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        du = psutil.disk_usage(self.disk_path)
        dio = psutil.disk_io_counters()
        nio = psutil.net_io_counters()

        read_bps = write_bps = recv_bps = send_bps = 0.0
        previous = self._previous
        if previous is not None:
            elapsed = now - previous["time"]
            if elapsed > 0:
                if dio and previous["disk"]:
                    read_bps = max(0.0, (dio.read_bytes - previous["disk"].read_bytes) / elapsed)
                    write_bps = max(0.0, (dio.write_bytes - previous["disk"].write_bytes) / elapsed)
                if nio and previous["net"]:
                    recv_bps = max(0.0, (nio.bytes_recv - previous["net"].bytes_recv) / elapsed)
                    send_bps = max(0.0, (nio.bytes_sent - previous["net"].bytes_sent) / elapsed)

        self._previous = {"time": now, "disk": dio, "net": nio}

        return Snapshot(
            timestamp=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            cpu_percent=round(float(cpu), 1),
            cpu_threads=psutil.cpu_count(logical=True) or 0,
            ram=Usage(int(vm.used), int(vm.total), round(float(vm.percent), 1)),
            swap=Usage(int(sm.used), int(sm.total), round(float(sm.percent), 1)),
            disk=Usage(int(du.used), int(du.total), round(float(du.percent), 1)),
            disk_read_bps=round(read_bps, 1),
            disk_write_bps=round(write_bps, 1),
            net_recv_bps=round(recv_bps, 1),
            net_send_bps=round(send_bps, 1),
            gpu=gpu_info(),
        )


def gpu_info() -> dict:
    """Report GPU memory honestly, including the shared-memory case.

    Some PCI BAR files are root-only, but ``stat`` can still read their size.
    Integrated GPUs have no dedicated VRAM, so we report framebuffer against
    aperture and say so instead of inventing a dedicated figure.
    """
    aperture = 0
    for path in glob.glob("/sys/class/drm/card*/device/resource2"):
        try:
            size = os.stat(path).st_size
        except OSError:
            continue
        if size > 0:
            aperture = size
            break

    framebuffer_mib = 0
    for path in glob.glob("/sys/class/drm/card*/device/graphics/fb0"):
        try:
            with open(os.path.join(path, "virtual_size"), encoding="utf-8") as handle:
                dimensions = handle.read().strip()
            with open(os.path.join(path, "bits_per_pixel"), encoding="utf-8") as handle:
                bits = int(handle.read().strip())
            width, height = (int(part) for part in dimensions.split(","))
        except (OSError, ValueError):
            continue
        framebuffer_mib = (width * height * bits) // 8 // MIB
        break

    if aperture <= 0:
        return {
            "mode": "unknown",
            "used_mib": framebuffer_mib,
            "total_mib": 0,
            "percent": 0.0,
            "note": "No GPU aperture information available on this host.",
        }

    total_mib = aperture // MIB
    percent = round(100.0 * framebuffer_mib / total_mib, 1) if total_mib else 0.0
    return {
        "mode": "shared",
        "used_mib": framebuffer_mib,
        "total_mib": total_mib,
        "percent": percent,
        "note": "Integrated GPU shares system RAM: framebuffer versus aperture, not dedicated VRAM.",
    }
