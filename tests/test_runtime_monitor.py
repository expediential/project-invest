from __future__ import annotations

import builtins

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
