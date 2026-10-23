from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import project_invest.api.app as app_module
from project_invest.domain.models import RuntimeComponentState, RuntimeComponentStatus, utc_now
from project_invest.services.worker import _WorkerStatusReporter
from project_invest.storage.data_lake import LocalDataLake


class _StatusRepository:
    def __init__(self) -> None:
        self.records: list[RuntimeComponentStatus] = []

    def save_runtime_status(self, status: RuntimeComponentStatus) -> None:
        self.records.append(status)


def test_worker_lifecycle_persists_running_idle_and_stopped_states() -> None:
    repository = _StatusRepository()
    reporter = _WorkerStatusReporter(repository, "research_worker")
    reporter.publish(RuntimeComponentState.STARTING)
    reporter.publish(RuntimeComponentState.RUNNING, cycle_started_at=utc_now())
    reporter.succeeded(0.25)
    reporter.publish(RuntimeComponentState.STOPPED)

    assert [record.state for record in repository.records] == [
        RuntimeComponentState.STARTING,
        RuntimeComponentState.RUNNING,
        RuntimeComponentState.IDLE,
        RuntimeComponentState.STOPPED,
    ]
    assert repository.records[2].last_success_at is not None


def test_worker_failure_is_reported_without_becoming_a_permanent_running_state() -> None:
    repository = _StatusRepository()
    reporter = _WorkerStatusReporter(repository, "trading_worker")
    reporter.publish(RuntimeComponentState.STARTING)
    reporter.publish(RuntimeComponentState.RUNNING, cycle_started_at=utc_now())
    reporter.failed(RuntimeError("provider timed out"), 0.5)

    failed = next(record for record in repository.records if record.state is RuntimeComponentState.FAILED)
    assert failed.last_error == "provider timed out"
    assert failed.last_error_at is not None


def test_stale_heartbeat_is_distinguished_from_running() -> None:
    status = RuntimeComponentStatus(
        component="research_worker",
        state=RuntimeComponentState.RUNNING,
        heartbeat_at=utc_now() - timedelta(minutes=5),
    )

    view = app_module._runtime_component_view(status, interval_seconds=10)

    assert view["state"] == "stale"
    assert view["reported_state"] == "running"


def test_local_runtime_status_survives_a_separate_storage_instance(tmp_path) -> None:
    first = LocalDataLake(tmp_path)
    first.save_runtime_status(
        RuntimeComponentStatus(component="research_worker", state=RuntimeComponentState.IDLE)
    )

    second = LocalDataLake(tmp_path)
    statuses = second.load_runtime_statuses()

    assert len(statuses) == 1
    assert statuses[0].component == "research_worker"
    assert statuses[0].state is RuntimeComponentState.IDLE


def test_dashboard_market_reads_do_not_trigger_provider_ingestion() -> None:
    class _Storage:
        def load_candles(self, symbol, interval, stage):
            return []

        def load_features(self, symbol, interval):
            return []

    class _Ingestion:
        async def ingest_symbol(self, *args, **kwargs):
            raise AssertionError("dashboard read attempted provider ingestion")

    settings = SimpleNamespace(research_interval="1d", trading_interval="5m")
    container = SimpleNamespace(settings=settings, storage=_Storage(), ingestion=_Ingestion())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))

    market_request = app_module.market_data("RELIANCE.NS", request, interval="5m")
    features_request = app_module.features("RELIANCE.NS", request, interval="5m")
    try:
        market_request.send(None)
    except StopIteration as result:
        assert result.value == []
    else:  # pragma: no cover - this endpoint deliberately performs no I/O await.
        market_request.close()
        raise AssertionError("dashboard market endpoint unexpectedly awaited work")
    try:
        features_request.send(None)
    except StopIteration as result:
        assert result.value == []
    else:  # pragma: no cover - this endpoint deliberately performs no I/O await.
        features_request.close()
        raise AssertionError("dashboard features endpoint unexpectedly awaited work")
