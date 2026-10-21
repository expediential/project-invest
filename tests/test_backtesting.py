from __future__ import annotations

from datetime import datetime, timedelta, timezone

from project_invest.domain.models import Candle, StrategyFamily, StrategyGenome
from project_invest.services.backtesting import BacktestingEngine
from project_invest.services.strategy_signals import StrategySignalEngine


def make_trending_candles(count: int) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        close = price * 1.01
        candles.append(
            Candle(
                symbol="TREND",
                timestamp=start + timedelta(days=index),
                open=price,
                high=close * 1.01,
                low=price * 0.995,
                close=close,
                volume=10_000 + index,
            )
        )
        price = close
    return candles


def test_backtester_finds_positive_result_on_clean_trend() -> None:
    signal_engine = StrategySignalEngine()
    backtester = BacktestingEngine(
        signal_engine=signal_engine,
        slippage_bps=0,
        fee_bps=0,
        max_risk_per_trade=0.05,
    )
    genome = StrategyGenome(
        family=StrategyFamily.TREND_FOLLOWING,
        short_window=3,
        long_window=8,
        momentum_threshold=0.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.2,
        risk_fraction=0.25,
    )

    result = backtester.run("TREND", make_trending_candles(40), genome, initial_capital=100000.0)

    assert result.metrics.trades >= 1
    assert result.metrics.final_equity >= 100000.0
    assert result.metrics.total_return >= 0


def test_walk_forward_validation_preserves_positive_trend_edge() -> None:
    signal_engine = StrategySignalEngine()
    backtester = BacktestingEngine(
        signal_engine=signal_engine,
        slippage_bps=0,
        fee_bps=0,
        max_risk_per_trade=0.05,
    )
    genome = StrategyGenome(
        family=StrategyFamily.TREND_FOLLOWING,
        short_window=5,
        long_window=18,
        momentum_threshold=0.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.18,
        risk_fraction=0.2,
    )

    metrics = backtester.run_walk_forward("TREND", make_trending_candles(180), genome, initial_capital=100000.0)

    assert metrics.trades >= 1
    assert metrics.final_equity >= 100000.0
    assert metrics.total_return >= 0


def test_walk_forward_excludes_the_final_holdout_from_candidate_validation() -> None:
    signal_engine = StrategySignalEngine()
    backtester = BacktestingEngine(
        signal_engine=signal_engine,
        slippage_bps=0,
        fee_bps=0,
        max_risk_per_trade=0.05,
    )
    genome = StrategyGenome(
        family=StrategyFamily.TREND_FOLLOWING,
        short_window=5,
        long_window=18,
        momentum_threshold=0.0,
    )
    candles = make_trending_candles(180)
    altered_holdout = [candle.model_copy() for candle in candles]
    for index in range(144, len(altered_holdout)):
        candle = altered_holdout[index]
        altered_holdout[index] = candle.model_copy(update={"close": candle.close * 0.1, "low": candle.low * 0.1})

    original = backtester.run_walk_forward("TREND", candles, genome, initial_capital=100000.0)
    perturbed = backtester.run_walk_forward("TREND", altered_holdout, genome, initial_capital=100000.0)

    assert original == perturbed
