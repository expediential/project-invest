from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeMonitor:
    """Best-effort, bounded local telemetry collected outside request handlers."""

    def __init__(self, sample_interval_seconds: int = 5, history_size: int = 120) -> None:
        self.sample_interval_seconds = max(2, sample_interval_seconds)
        self._history: deque[dict[str, object]] = deque(maxlen=max(1, history_size))
        self._latest: dict[str, object] | None = None
        self._last_network: tuple[float, int, int] | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.last_error: str | None = None
        self.last_success_at: datetime | None = None

    async def start(self) -> None:
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def snapshot(self) -> dict[str, object]:
        if self._latest is None:
            return {
                "state": "unavailable",
                "sampled_at": None,
                "last_success_at": self.last_success_at,
                "error": self.last_error or "Telemetry has not completed its first sample.",
                "sample_interval_seconds": self.sample_interval_seconds,
                "history_points": len(self._history),
                "metrics": {},
                "gpu": {"state": "unavailable", "reason": "Telemetry has not completed its first sample."},
            }
        return {
            **self._latest,
            "sample_interval_seconds": self.sample_interval_seconds,
            "history_points": len(self._history),
        }

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                sample = await asyncio.to_thread(self._collect)
                self._latest = sample
                self._history.append(sample)
                self.last_success_at = _utc_now()
                self.last_error = None
            except Exception as exc:  # pragma: no cover - defensive OS telemetry boundary
                self.last_error = f"Telemetry collection failed: {exc}"
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.sample_interval_seconds)
            except asyncio.TimeoutError:
                continue

    def _collect(self) -> dict[str, object]:
        sampled_at = _utc_now()
        try:
            import psutil
        except ImportError:
            return {
                "state": "unavailable",
                "sampled_at": sampled_at,
                "last_success_at": self.last_success_at,
                "error": "Optional psutil telemetry is not installed.",
                "metrics": {},
                "gpu": self._collect_gpu(),
            }

        memory = psutil.virtual_memory()
        disk = shutil.disk_usage(os.getcwd())
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        network = psutil.net_io_counters()
        now_monotonic = time.monotonic()
        network_metrics: dict[str, float | None] = {"bytes_sent_per_second": None, "bytes_recv_per_second": None}
        if self._last_network is not None:
            previous_time, previous_sent, previous_recv = self._last_network
            elapsed = max(0.001, now_monotonic - previous_time)
            network_metrics = {
                "bytes_sent_per_second": round((network.bytes_sent - previous_sent) / elapsed, 2),
                "bytes_recv_per_second": round((network.bytes_recv - previous_recv) / elapsed, 2),
            }
        self._last_network = (now_monotonic, network.bytes_sent, network.bytes_recv)
        return {
            "state": "healthy",
            "sampled_at": sampled_at,
            "last_success_at": sampled_at,
            "error": None,
            "metrics": {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_total_bytes": memory.total,
                "memory_available_bytes": memory.available,
                "memory_used_bytes": memory.used,
                "memory_percent": memory.percent,
                "disk_total_bytes": disk.total,
                "disk_available_bytes": disk.free,
                "disk_used_bytes": disk.used,
                "disk_percent": round((disk.used / disk.total) * 100, 2) if disk.total else None,
                "network": network_metrics,
                "process": {
                    "pid": process.pid,
                    "cpu_percent": process.cpu_percent(interval=None),
                    "rss_bytes": process_memory.rss,
                    "vms_bytes": process_memory.vms,
                },
            },
            "gpu": self._collect_gpu(),
        }

    def _collect_gpu(self) -> dict[str, object]:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return {"state": "unavailable", "reason": "nvidia-smi is not available on this machine."}
        try:
            completed = subprocess.run(
                [
                    executable,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "unavailable", "reason": f"NVIDIA telemetry could not be queried: {exc}"}
        if completed.returncode != 0:
            return {"state": "unavailable", "reason": (completed.stderr or "nvidia-smi failed").strip()[:200]}
        devices = []
        for line in completed.stdout.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 6:
                continue
            devices.append(
                {
                    "name": fields[0],
                    "utilization_percent": _number_or_none(fields[1]),
                    "memory_used_mib": _number_or_none(fields[2]),
                    "memory_total_mib": _number_or_none(fields[3]),
                    "temperature_celsius": _number_or_none(fields[4]),
                    "power_watts": _number_or_none(fields[5]),
                }
            )
        return {"state": "healthy" if devices else "unavailable", "devices": devices, "reason": None if devices else "No NVIDIA devices were reported."}


def _number_or_none(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
