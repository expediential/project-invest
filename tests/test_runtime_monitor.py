from __future__ import annotations

import builtins
import subprocess

from project_invest.services.runtime_monitor import RuntimeMonitor


def test_monitor_reports_unavailable_before_a_sample() -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)

    snapshot = monitor.snapshot()

    assert snapshot["state"] == "unavailable"
    assert snapshot["metrics"] == {}


def test_monitor_handles_missing_optional_psutil(monkeypatch) -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)
    original_import = builtins.__import__

    def missing_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("simulated missing psutil")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_psutil)

    sample = monitor._collect()

    assert sample["state"] == "unavailable"
    assert "psutil" in sample["error"]


def test_monitor_collects_local_metrics_when_psutil_is_available() -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)

    sample = monitor._collect()

    assert sample["state"] == "healthy"
    assert {"cpu_percent", "memory_percent", "disk_percent", "network", "process"} <= sample["metrics"].keys()
    assert sample["metrics"]["process"]["pid"] > 0


def test_monitor_reports_gpu_query_timeout_without_failing_the_sample(monkeypatch) -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)
    monkeypatch.setattr("project_invest.services.runtime_monitor.shutil.which", lambda _: "nvidia-smi")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)

    monkeypatch.setattr("project_invest.services.runtime_monitor.subprocess.run", timeout)

    gpu = monitor._collect_gpu()

    assert gpu["state"] == "unavailable"
    assert "could not be queried" in gpu["reason"]
