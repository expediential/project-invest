from __future__ import annotations

from dataclasses import dataclass

from project_invest.domain.models import SignalAction, StrategyEvaluation, TradeSignal


@dataclass(frozen=True)
class PromotionThresholds:
    min_validation_sharpe: float
    min_validation_return: float
    max_validation_drawdown: float
    min_validation_trades: int
    min_validation_profit_factor: float
    min_validation_win_rate: float
    min_validation_trade_coverage: float
    max_validation_return_gap: float
    max_validation_sharpe_gap: float


@dataclass(frozen=True)
class PromotionAssessment:
    approved: bool
    hard_failure: bool
    reason: str


class StrategyPromotionGate:
    def __init__(self, thresholds: PromotionThresholds) -> None:
        self.thresholds = thresholds

    def assess(self, evaluation: StrategyEvaluation) -> PromotionAssessment:
        metrics = evaluation.validation_metrics or evaluation.metrics
        full_metrics = evaluation.metrics
        soft_reason: str | None = None

        if metrics.trades < self.thresholds.min_validation_trades:
            soft_reason = "Validation trade count is too low for paper promotion."
        if metrics.win_rate < self.thresholds.min_validation_win_rate:
            hard_failure = metrics.win_rate < max(0.15, self.thresholds.min_validation_win_rate - 0.12)
            if hard_failure:
                return PromotionAssessment(
                    approved=False,
                    hard_failure=True,
                    reason="Validation win rate is below the paper-trading threshold.",
                )
            soft_reason = soft_reason or "Validation win rate is below the paper-trading threshold."
        if metrics.sharpe_ratio < self.thresholds.min_validation_sharpe:
            hard_failure = metrics.sharpe_ratio < (self.thresholds.min_validation_sharpe - 0.4)
            if hard_failure:
                return PromotionAssessment(
                    approved=False,
                    hard_failure=True,
                    reason="Validation Sharpe ratio is below the paper-trading threshold.",
                )
            soft_reason = soft_reason or "Validation Sharpe ratio is below the paper-trading threshold."
        if metrics.total_return < self.thresholds.min_validation_return:
            hard_failure = metrics.total_return < (self.thresholds.min_validation_return - 0.015)
            if hard_failure:
                return PromotionAssessment(
                    approved=False,
                    hard_failure=True,
                    reason="Validation return is below the paper-trading threshold.",
                )
            soft_reason = soft_reason or "Validation return is below the paper-trading threshold."
        if metrics.profit_factor < self.thresholds.min_validation_profit_factor:
            hard_failure = metrics.profit_factor < max(0.3, self.thresholds.min_validation_profit_factor - 0.25)
            if hard_failure:
                return PromotionAssessment(
                    approved=False,
                    hard_failure=True,
                    reason="Validation profit factor is below the paper-trading threshold.",
                )
            soft_reason = soft_reason or "Validation profit factor is below the paper-trading threshold."
        if metrics.max_drawdown > self.thresholds.max_validation_drawdown:
            return PromotionAssessment(
                approved=False,
                hard_failure=True,
                reason="Validation drawdown is above the paper-trading threshold.",
            )
        if evaluation.validation_metrics is not None:
            coverage = metrics.trades / max(full_metrics.trades, 1)
            if coverage < self.thresholds.min_validation_trade_coverage:
                soft_reason = soft_reason or "Validation trade coverage is too low compared to the full backtest."
            return_gap = abs(full_metrics.total_return - metrics.total_return)
            if return_gap > self.thresholds.max_validation_return_gap:
                soft_reason = soft_reason or "Validation return diverges too far from the full backtest."
            sharpe_gap = abs(full_metrics.sharpe_ratio - metrics.sharpe_ratio)
            if sharpe_gap > self.thresholds.max_validation_sharpe_gap:
                soft_reason = soft_reason or "Validation Sharpe diverges too far from the full backtest."
        if soft_reason is not None:
            return PromotionAssessment(
                approved=False,
                hard_failure=False,
                reason=soft_reason,
            )
        return PromotionAssessment(approved=True, hard_failure=False, reason="Promoted for paper trading.")

    def apply(self, evaluation: StrategyEvaluation, signal: TradeSignal) -> TradeSignal:
        if signal.action != SignalAction.BUY:
            return signal

        assessment = self.assess(evaluation)
        if assessment.approved:
            return signal

        return signal.model_copy(
            update={
                "action": SignalAction.HOLD,
                "confidence": 0.0,
                "reason": f"Paper-trading gate blocked entry: {assessment.reason}",
            }
        )
