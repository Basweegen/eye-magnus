#!/usr/bin/env python3
"""Scan text files for common secret patterns.

Exits 1 if anything looks like a credential. Run before committing:

    python3 scripts/scan_secrets.py .
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = [
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("github_fine_token", re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("openai_style_key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)(password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
    ),
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache", "node_modules"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".sh", ".yml", ".yaml", ".txt", ".cfg", ".ini", ""}


def scan(root: str | Path) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    for path in Path(root).rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix and path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append((str(path), number, name))
    return findings


def main() -> int:
    roots = sys.argv[1:] or ["."]
    findings: list[tuple[str, int, str]] = []
    for root in roots:
        findings.extend(scan(root))
    for path, number, name in findings:
        print(f"{path}:{number}: {name}")
    if findings:
        print(f"FAIL: {len(findings)} potential secret(s) found")
        return 1
    print("OK: no secret patterns found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
