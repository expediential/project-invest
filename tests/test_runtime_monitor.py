from __future__ import annotations

from project_invest.services.runtime_monitor import RuntimeMonitor


def test_monitor_reports_unavailable_before_a_sample() -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)

    snapshot = monitor.snapshot()

    assert snapshot["state"] == "unavailable"
    assert snapshot["metrics"] == {}


def test_monitor_handles_missing_optional_psutil() -> None:
    monitor = RuntimeMonitor(sample_interval_seconds=5)

    sample = monitor._collect()

    assert sample["state"] == "unavailable"
    assert "psutil" in sample["error"]
