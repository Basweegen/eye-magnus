"""Read-only Ollama inference telemetry.

Uses only the local Ollama HTTP API. There is no token, no cloud call, and no
model loading here: this module never sends a write or generate request.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _base_url() -> str:
    raw = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlsplit(raw)
    if parsed.username or parsed.password:
        raise ValueError("credentials in OLLAMA_HOST are not accepted")
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        if os.environ.get("EYE_MAGNUS_ALLOW_REMOTE_OLLAMA") != "1":
            raise ValueError("remote Ollama host blocked by default")
    return raw.rstrip("/")


def _get(path: str, timeout: float = 2.0) -> dict:
    request = urllib.request.Request(_base_url() + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", "replace")
    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def _integer(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    try:
        text = text.replace(_base_url(), "ollama")
    except ValueError:
        pass
    return text[:200]


def collect() -> dict:
    """Return the current inference health. Never mutates Ollama state."""
    result = {
        "available": False,
        "version": "",
        "running": [],
        "running_count": 0,
        "running_vram_bytes": 0,
        "running_size_bytes": 0,
        "installed_count": 0,
        "error": "",
    }

    try:
        version = _get("/api/version")
        processes = _get("/api/ps")
        tags = _get("/api/tags")
    except Exception as exc:  # local service may simply be stopped
        result["error"] = f"{type(exc).__name__}: {_safe_error(exc)}"
        return result

    result["available"] = True
    result["version"] = str(version.get("version", ""))[:40]
    tags_models = tags.get("models", [])
    result["installed_count"] = len(tags_models) if isinstance(tags_models, list) else 0

    models = processes.get("models", [])
    if not isinstance(models, list):
        models = []
    for model in models:
        if not isinstance(model, dict):
            continue
        details = model.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        size = _integer(model.get("size"))
        vram = _integer(model.get("size_vram"))
        result["running"].append({
            "name": str(model.get("name") or model.get("model") or "")[:120],
            "family": str(details.get("family", ""))[:40],
            "size_bytes": size,
            "vram_bytes": vram,
            "context_length": _integer(model.get("context_length")),
            "expires_at": str(model.get("expires_at", ""))[:40],
        })
        result["running_size_bytes"] += size
        result["running_vram_bytes"] += vram

    result["running_count"] = len(result["running"])
    return result
