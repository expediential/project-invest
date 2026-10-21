from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import project_invest.api.app as app_module
from project_invest.config import Settings


class _DummyStorage:
    backend_name = "local"

    def __init__(self) -> None:
        self.candle_reads = 0

    def load_latest_report(self, stream: str = "research"):
        return None

    def load_portfolio(self):
        return None

    def load_portfolio_history(self, limit: int = 2_000):
        return []

    def load_candles(self, symbol: str, interval: str, stage: str = "processed"):
        self.candle_reads += 1
        assert stage == "processed"
        return []

    def close(self) -> None:
        return None


def test_health_endpoint_uses_the_standalone_worker_topology(monkeypatch) -> None:
    dummy_settings = Settings(
        research_symbols="RELIANCE.NS,TCS.NS",
        use_market_universes=False,
        market_universes="NSE",
        api_auth_token="test-token",
    )
    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=_DummyStorage(),
        research_lab=object(),
        trading_lab=object(),
        close=lambda: None,
    )

    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        response = client.get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["embedded_loops_enabled"] is False
    assert payload["worker_launch_mode"] == "standalone"
    assert payload["worker_running"] is False


def test_health_endpoint_shows_api_only_launch_hint_when_workers_are_not_running(monkeypatch) -> None:
    dummy_settings = Settings(
        research_symbols="RELIANCE.NS,TCS.NS",
        use_market_universes=False,
        market_universes="NSE",
        research_loop_enabled=False,
        trading_loop_enabled=False,
        live_loop_enabled=False,
    )
    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=_DummyStorage(),
        research_lab=object(),
        trading_lab=object(),
        close=lambda: None,
    )

    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        response = client.get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["worker_launch_mode"] == "standalone"
    assert payload["worker_running"] is False
    assert "run-project-invest.cmd" in payload["launch_hint"]


def test_run_trading_returns_detail_when_cycle_fails(monkeypatch) -> None:
    dummy_settings = Settings(
        research_symbols="RELIANCE.NS,TCS.NS",
        use_market_universes=False,
        market_universes="NSE",
        api_auth_token="test-token",
    )

    async def failing_trade_cycle(symbols=None):
        raise RuntimeError("kaboom")

    async def ok_research_cycle(symbols=None, execute_trades=False):
        return {"ok": True}

    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=_DummyStorage(),
        research_lab=SimpleNamespace(run_cycle=ok_research_cycle),
        trading_lab=SimpleNamespace(run_cycle=failing_trade_cycle),
        close=lambda: None,
    )

    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/trading/run",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"] == "Trading cycle failed: kaboom"


def test_run_research_returns_detail_when_cycle_fails(monkeypatch) -> None:
    dummy_settings = Settings(
        research_symbols="RELIANCE.NS,TCS.NS",
        use_market_universes=False,
        market_universes="NSE",
        api_auth_token="test-token",
    )

    async def failing_research_cycle(symbols=None, execute_trades=False):
        raise RuntimeError("broken-research")

    async def ok_trading_cycle(symbols=None):
        return {"ok": True}

    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=_DummyStorage(),
        research_lab=SimpleNamespace(run_cycle=failing_research_cycle),
        trading_lab=SimpleNamespace(run_cycle=ok_trading_cycle),
        close=lambda: None,
    )

    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/research/run",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"] == "Research cycle failed: broken-research"


def test_operational_routes_fail_closed_without_valid_credentials(monkeypatch) -> None:
    dummy_settings = Settings(research_symbols="RELIANCE.NS", use_market_universes=False)
    called = False

    async def should_not_run(symbols=None):
        nonlocal called
        called = True
        return {"ok": True}

    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=_DummyStorage(),
        research_lab=SimpleNamespace(run_cycle=should_not_run),
        trading_lab=SimpleNamespace(run_cycle=should_not_run),
        close=lambda: None,
    )
    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        response = client.post("/api/trading/run", json={})

    assert response.status_code == 503
    assert called is False


def test_monitoring_routes_report_stored_state_without_ingestion(monkeypatch) -> None:
    dummy_settings = Settings(
        app_name="Terminal Test",
        base_currency="usd",
        research_symbols="RELIANCE.NS",
        use_market_universes=False,
        api_auth_token="test-token",
    )
    dummy_storage = _DummyStorage()
    dummy_container = SimpleNamespace(
        settings=dummy_settings,
        storage=dummy_storage,
        research_lab=object(),
        trading_lab=object(),
        close=lambda: None,
    )
    monkeypatch.setattr(app_module, "build_container", lambda _: dummy_container)

    with TestClient(app_module.app) as client:
        dashboard = client.get("/")
        summary = client.get("/api/portfolio/summary")
        quality = client.get("/api/data-quality")
        compute = client.get("/api/research/compute-status")
        config = client.get("/api/config")

    assert dashboard.status_code == 200
    assert "Quant Research Terminal" in dashboard.text
    assert "Terminal Test" in dashboard.text
    assert summary.json()["state"] == "empty"
    assert summary.json()["base_currency"] == "USD"
    assert quality.json()["status"] == "partial"
    assert "does not fetch" in quality.json()["note"]
    assert dummy_storage.candle_reads == 1
    assert compute.json()["remote_backend"]["status"] == "not_configured"
    assert config.json()["base_currency"] == "USD"
