# eye-magnus

**Magnus System Health Monitoring** — a read-only, local-first command line tool that shows real-time host health and local LLM inference health in one place.

## What it is

`eye-magnus` is a small Python CLI with three commands:

| Command | What it does |
|---|---|
| `eye-magnus monitor` | Live, refreshing terminal view of CPU, RAM, swap, root disk, disk I/O, network I/O and GPU memory. Refreshes every second. |
| `eye-magnus llm` | The same live system view plus Ollama inference resources: Ollama version, installed model count, models currently loaded, their sizes, VRAM use, context length and expiry. |
| `eye-magnus health` | A one-shot snapshot of the host only, for scripts and dashboards. |

Every command also accepts `--json`, which prints one JSON object and exits without entering the live view:

```bash
eye-magnus llm --json
eye-magnus health --json
```

Exit codes: `0` success, `3` when `llm` runs but Ollama is unreachable, `2` for a CLI usage error.

## Who it is for

- **System administrators** who want a quick, honest health picture without a heavy agent or a web dashboard.
- **Local AI operators** running Ollama who need to see what models are loaded and how much memory they actually take.
- **Security-minded users** who want monitoring that does not phone home, collect telemetry, or require a token.
- **Kali / Arch / Linux desktop users** who want a terminal tool that works over SSH and in a plain console.

It is deliberately not a remote fleet monitor, an alerting system, or a dashboard server. It is one process, on one machine, reading local state.

## Why it exists

Host metrics and LLM metrics are normally in two different places. `htop` shows CPU and RAM; `ollama ps` shows loaded models. When a local model makes the machine crawl, you want both views at once. `eye-magnus` puts them side by side and is truthful about what the numbers mean.

The design rules are:

1. **Read-only.** The tool never loads, unloads, pulls or deletes a model. It never writes to disk and never executes a shell command.
2. **Local only.** Ollama is contacted on loopback (`127.0.0.1:11434`) by default. A remote host is refused unless `EYE_MAGNUS_ALLOW_REMOTE_OLLAMA=1` is set explicitly.
3. **No secrets.** No tokens, keys, emails or credentials are stored in the repository. A secret scan runs before every release.
4. **Honest GPU reporting.** This host has an Intel Arc integrated GPU with no dedicated VRAM. The tool reports framebuffer use against the GPU aperture and labels it "shared" instead of inventing a dedicated VRAM figure. On NVIDIA or AMD hardware it prefers real VRAM data from the vendor tool if available in future versions.
5. **Real time where it counts.** CPU load is measured from two `/proc/stat` samples, disk and network rates are byte deltas per second. Capacity percentages are snapshots, not activity.

## What "real time" means here

- **CPU** — load computed from two kernel samples; the live view refreshes every second.
- **RAM / swap** — sampled fresh on every refresh.
- **Disk capacity** — used percentage of the chosen mount point. Changes slowly by nature.
- **Disk I/O and network** — bytes per second from counter deltas. The first sample shows zero because there is no previous counter to subtract.
- **GPU** — framebuffer versus aperture on integrated graphics. This changes with display mode, not per frame.
- **LLM** — Ollama's own `/api/ps` report: genuinely loaded models and their memory, refreshed every second in live mode.

## Why there is no model loader

Loading a model is a *change* to the machine, not a health reading. A 19 GB model can consume most of the RAM, evict other work and slow the desktop. An automatic "system admin AI" that does this on its own would be hard to trust and harder to audit.

For now the `llm` command is strictly observational. A future version may add explicit `eye-magnus llm load <model>` and `unload` commands that ask before acting. An autonomous Magnus agent belongs in a separate project, not inside monitoring.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
eye-magnus --version
```

Requires Python 3.10+ and `psutil`. No other runtime dependency.

## Usage

```bash
# live system monitor (1 second refresh)
eye-magnus monitor

# live system + Ollama inference health
eye-magnus llm

# one-shot text snapshot
eye-magnus health

# machine-readable output for scripts
eye-magnus llm --json
eye-magnus health --json

# watch a different mount point, slower refresh, no color
eye-magnus monitor --disk /home --interval 2 --no-color
```

Example JSON shape:

```json
{
  "timestamp": "2026-11-18T05:30:00-07:00",
  "cpu_percent": 3.2,
  "cpu_threads": 22,
  "ram": { "used": 9000000000, "total": 40000000000, "percent": 22.5, "used_mib": 8583.9, "total_mib": 38146.9 },
  "swap": { "used": 0, "total": 80000000000, "percent": 0.0, "used_mib": 0.0, "total_mib": 76293.9 },
  "disk": { "used": 1500000000000, "total": 2000000000000, "percent": 76.0, "used_mib": 1430511.5, "total_mib": 1907348.6 },
  "disk_read_bps": 0.0,
  "disk_write_bps": 4096.0,
  "net_recv_bps": 120.0,
  "net_send_bps": 45.0,
  "gpu": { "mode": "shared", "used_mib": 8, "total_mib": 256, "percent": 3.1, "note": "Integrated GPU shares system RAM: framebuffer versus aperture, not dedicated VRAM." },
  "llm": {
    "available": true,
    "version": "0.40.7",
    "running": [],
    "running_count": 0,
    "running_vram_bytes": 0,
    "running_size_bytes": 0,
    "installed_count": 18,
    "error": ""
  }
}
```

## Security and privacy

- No outbound network calls. The only HTTP requests are to local Ollama on loopback.
- No command execution, no `sudo`, no writes to disk.
- No credentials are read, stored or logged. If `OLLAMA_HOST` contains a username or password, the tool refuses it.
- Error messages are sanitized: the local base URL is replaced before display.
- The repository is scanned for secret patterns before release. Add a test when adding new configuration surface.

## Repository layout

```
eye_magnus/
  cli.py        argument parsing and command dispatch
  system.py     host telemetry from psutil and sysfs
  ollama.py     read-only Ollama API client
  format.py     bars, human-readable sizes, JSON-friendly rendering
tests/          unit tests (stdlib unittest)
scripts/scan_secrets.py   secret-pattern scanner
```

## License

MIT. See [LICENSE](LICENSE).
