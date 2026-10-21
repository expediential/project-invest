from __future__ import annotations

from project_invest.domain.models import (
    BacktestMetrics,
    SignalAction,
    StrategyEvaluation,
    StrategyGenome,
    TradeSignal,
)
from project_invest.services.strategy_promotion import PromotionThresholds, StrategyPromotionGate


def make_evaluation(
    *,
    validation_sharpe: float,
    validation_return: float,
    validation_drawdown: float,
    validation_trades: int,
    validation_win_rate: float = 0.5,
) -> StrategyEvaluation:
    genome = StrategyGenome()
    full_metrics = BacktestMetrics(
        total_return=0.01,
        sharpe_ratio=1.0,
        max_drawdown=0.02,
        win_rate=0.6,
        profit_factor=1.4,
        trades=6,
        final_equity=101000.0,
    )
    validation_metrics = BacktestMetrics(
        total_return=validation_return,
        sharpe_ratio=validation_sharpe,
        max_drawdown=validation_drawdown,
        win_rate=validation_win_rate,
        profit_factor=1.2,
        trades=validation_trades,
        final_equity=100500.0,
    )
    return StrategyEvaluation(
        genome=genome,
        metrics=full_metrics,
        validation_metrics=validation_metrics,
        robustness_score=0.2,
        score=1.0,
    )


def make_buy_signal() -> TradeSignal:
    return TradeSignal(
        symbol="INFY.NS",
        action=SignalAction.BUY,
        confidence=0.65,
        reason="Candidate entry",
        strategy_id="strat-test",
    )


def test_promotion_gate_blocks_weak_buy_candidates() -> None:
    gate = StrategyPromotionGate(
        PromotionThresholds(
            min_validation_sharpe=0.25,
            min_validation_return=0.0,
            max_validation_drawdown=0.1,
            min_validation_trades=2,
            min_validation_profit_factor=1.3,
            min_validation_win_rate=0.55,
            min_validation_trade_coverage=0.4,
            max_validation_return_gap=0.02,
            max_validation_sharpe_gap=0.6,
        )
    )
    evaluation = make_evaluation(
        validation_sharpe=0.05,
        validation_return=-0.01,
        validation_drawdown=0.12,
        validation_trades=1,
        validation_win_rate=0.4,
    )

    gated_signal = gate.apply(evaluation, make_buy_signal())

    assert gated_signal.action == SignalAction.HOLD
    assert "Paper-trading gate blocked entry" in gated_signal.reason


def test_promotion_gate_leaves_sell_signals_untouched() -> None:
    gate = StrategyPromotionGate(
        PromotionThresholds(
            min_validation_sharpe=0.25,
            min_validation_return=0.0,
            max_validation_drawdown=0.1,
            min_validation_trades=2,
            min_validation_profit_factor=1.3,
            min_validation_win_rate=0.55,
            min_validation_trade_coverage=0.4,
            max_validation_return_gap=0.02,
            max_validation_sharpe_gap=0.6,
        )
    )
    evaluation = make_evaluation(
        validation_sharpe=0.05,
        validation_return=-0.01,
        validation_drawdown=0.12,
        validation_trades=1,
    )
    sell_signal = TradeSignal(
        symbol="INFY.NS",
        action=SignalAction.SELL,
        confidence=0.51,
        reason="Exit candidate",
        strategy_id="strat-test",
    )

    gated_signal = gate.apply(evaluation, sell_signal)

    assert gated_signal.action == SignalAction.SELL
    assert gated_signal.reason == "Exit candidate"


def test_promotion_gate_blocks_borderline_buy_candidates() -> None:
    gate = StrategyPromotionGate(
        PromotionThresholds(
            min_validation_sharpe=0.25,
            min_validation_return=0.0,
            max_validation_drawdown=0.1,
            min_validation_trades=2,
            min_validation_profit_factor=1.0,
            min_validation_win_rate=0.45,
            min_validation_trade_coverage=0.4,
            max_validation_return_gap=0.02,
            max_validation_sharpe_gap=0.6,
        )
    )
    evaluation = make_evaluation(
        validation_sharpe=0.5,
        validation_return=0.01,
        validation_drawdown=0.02,
        validation_trades=2,
        validation_win_rate=0.5,
    )

    gated_signal = gate.apply(evaluation, make_buy_signal())

    assert gated_signal.action == SignalAction.HOLD
    assert gated_signal.confidence == 0.0
    assert "Paper-trading gate blocked entry" in gated_signal.reason
