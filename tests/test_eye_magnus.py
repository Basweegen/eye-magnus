"""Unit tests for eye-magnus. Run with: python -m unittest discover -s tests"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eye_magnus.format import bar, human, rate  # noqa: E402
from eye_magnus.ollama import collect  # noqa: E402


class FormatTests(unittest.TestCase):
    def test_bar_width(self):
        self.assertEqual(len(bar(0, width=10, color=False)), 10)
        self.assertEqual(len(bar(100, width=10, color=False)), 10)
        self.assertEqual(bar(100, width=10, color=False), "\u2588" * 10)
        self.assertEqual(bar(0, width=10, color=False), "\u2591" * 10)

    def test_bar_clamps(self):
        self.assertEqual(bar(-50, width=4, color=False), "\u2591" * 4)
        self.assertEqual(bar(500, width=4, color=False), "\u2588" * 4)

    def test_human(self):
        self.assertEqual(human(0), "0.0B")
        self.assertTrue(human(2048).startswith("2.0K"))
        self.assertTrue(rate(1024).endswith("/s"))


class OllamaTests(unittest.TestCase):
    def test_collect_available(self):
        version = {"version": "0.40.7"}
        processes = {"models": [{
            "name": "tiny:latest", "size": 1000, "size_vram": 400,
            "context_length": 4096, "expires_at": "2026-11-18T06:00:00Z",
            "details": {"family": "llama"},
        }]}
        tags = {"models": [{"name": "tiny:latest"}, {"name": "other:latest"}]}
        with patch("eye_magnus.ollama._get", side_effect=[version, processes, tags]):
            result = collect()
        self.assertTrue(result["available"])
        self.assertEqual(result["version"], "0.40.7")
        self.assertEqual(result["running_count"], 1)
        self.assertEqual(result["installed_count"], 2)
        self.assertEqual(result["running_vram_bytes"], 400)

    def test_collect_unavailable(self):
        with patch("eye_magnus.ollama._get", side_effect=OSError("refused")):
            result = collect()
        self.assertFalse(result["available"])
        self.assertIn("OSError", result["error"])

    def test_remote_host_blocked(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://example.com:11434"}, clear=False):
            os.environ.pop("EYE_MAGNUS_ALLOW_REMOTE_OLLAMA", None)
            with self.assertRaises(ValueError):
                from eye_magnus.ollama import _base_url
                _base_url()


class SnapshotTests(unittest.TestCase):
    def test_to_dict_shape(self):
        from eye_magnus.system import Snapshot, Usage
        snap = Snapshot(
            timestamp="2026-11-18T05:00:00-07:00", cpu_percent=1.0, cpu_threads=4,
            ram=Usage(1024 * 1024, 4 * 1024 * 1024, 25.0),
            swap=Usage(0, 1024 * 1024, 0.0),
            disk=Usage(1024 * 1024, 2 * 1024 * 1024, 50.0),
            disk_read_bps=0.0, disk_write_bps=0.0, net_recv_bps=0.0, net_send_bps=0.0,
            gpu={"mode": "shared"},
        )
        data = snap.to_dict()
        self.assertEqual(data["ram"]["used_mib"], 1.0)
        self.assertEqual(data["disk"]["percent"], 50.0)
        self.assertEqual(data["gpu"]["mode"], "shared")


class SecretScanTests(unittest.TestCase):
    def test_scanner_detects_token_and_ignores_clean_file(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "scan_secrets.py"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "clean.py").write_text("value = 42\n", encoding="utf-8")
            token = "ghp_" + "a" * 36
            (root / "bad.py").write_text(f"key = '{token}'\n", encoding="utf-8")
            proc = os.system(f'python3 "{script}" "{root}" > /dev/null 2>&1')
            self.assertNotEqual(proc, 0)


if __name__ == "__main__":
    unittest.main()
