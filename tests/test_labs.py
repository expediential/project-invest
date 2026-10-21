from __future__ import annotations

import asyncio
from pathlib import Path

from project_invest.config import Settings
from project_invest.container import build_container


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        market_data_provider="mock",
        allow_mock_data=True,
        storage_backend="local",
        data_root=tmp_path / "lake",
        use_market_universes=False,
        research_symbols=["RELIANCE.NS"],
        execution_markets=["NSE"],
        sentiment_provider="neutral",
        sentiment_memory_enabled=True,
        research_interval="15m",
        trading_interval="5m",
        lookback_bars=80,
        trading_lookback_bars=80,
        confirmation_intervals=[],
        population_size=6,
        generations=2,
    )


def test_research_lab_cycle_runs_with_sentiment_memory_enabled(tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path))
    try:
        report = asyncio.run(container.research_lab.run_cycle(["RELIANCE.NS"], execute_trades=False))
    finally:
        container.close()

    assert report.symbols == ["RELIANCE.NS"]
    assert len(report.results) == 1
    assert report.results[0].symbol == "RELIANCE.NS"


def test_trading_lab_cycle_runs_with_sentiment_memory_enabled(tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path))
    try:
        report = asyncio.run(container.trading_lab.run_cycle(["RELIANCE.NS"]))
    finally:
        container.close()

    assert report.symbols == ["RELIANCE.NS"]
    assert len(report.results) == 1
    assert report.results[0].symbol == "RELIANCE.NS"
