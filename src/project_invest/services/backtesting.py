from __future__ import annotations

from statistics import fmean, stdev

from project_invest.domain.models import (
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    Candle,
    SignalAction,
    StrategyGenome,
)
from project_invest.services.strategy_signals import StrategySignalEngine


class BacktestingEngine:
    def __init__(
        self,
        signal_engine: StrategySignalEngine,
        slippage_bps: float,
        fee_bps: float,
        max_risk_per_trade: float,
    ) -> None:
        self.signal_engine = signal_engine
        self.slippage_multiplier = slippage_bps / 10_000
        self.fee_multiplier = fee_bps / 10_000
        self.max_risk_per_trade = max_risk_per_trade

    def run(
        self,
        symbol: str,
        candles: list[Candle],
        genome: StrategyGenome,
        initial_capital: float,
        trade_start_index: int | None = None,
    ) -> BacktestResult:
        genome = self.signal_engine.normalize_genome(genome)
        required_bars = self.signal_engine.required_bars(genome)
        if len(candles) < required_bars:
            return BacktestResult(genome=genome, metrics=self._empty_metrics(initial_capital))

        cash = initial_capital
        equity_curve = [initial_capital]
        trades: list[BacktestTrade] = []
        position: dict[str, object] | None = None
        warmup_start_index = max(0, required_bars - 1)
        entry_start_index = max(warmup_start_index, trade_start_index or warmup_start_index)

        for index in range(warmup_start_index, len(candles)):
            candle = candles[index]
            window = candles[: index + 1]

            if position is not None:
                exit_price = self._determine_exit_price(candle, position, genome)
                if exit_price is None:
                    exit_signal = self.signal_engine.generate_signal(genome, window, has_position=True)
                    if exit_signal.action == SignalAction.SELL:
                        exit_price = candle.close

                if exit_price is not None:
                    fill_price = exit_price * (1 - self.slippage_multiplier)
                    quantity = int(position["quantity"])
                    fee = fill_price * quantity * self.fee_multiplier
                    proceeds = (fill_price * quantity) - fee
                    cash += proceeds
                    entry_cost = float(position["entry_cost"])
                    pnl = proceeds - entry_cost
                    trades.append(
                        BacktestTrade(
                            symbol=symbol,
                            strategy_id=genome.strategy_id,
                            entry_time=position["entry_time"],
                            exit_time=candle.timestamp,
                            entry_price=float(position["entry_price"]),
                            exit_price=round(fill_price, 4),
                            quantity=quantity,
                            pnl=round(pnl, 4),
                            return_pct=round(pnl / entry_cost if entry_cost else 0.0, 6),
                        )
                    )
                    position = None

            if position is None and index >= entry_start_index:
                signal = self.signal_engine.generate_signal(genome, window, has_position=False)
                if signal.action == SignalAction.BUY:
                    fill_price = candle.close * (1 + self.slippage_multiplier)
                    quantity = self._position_size(cash, fill_price, genome, signal.confidence)
                    if quantity > 0:
                        fee = fill_price * quantity * self.fee_multiplier
                        total_cost = (fill_price * quantity) + fee
                        if total_cost <= cash:
                            cash -= total_cost
                            position = {
                                "entry_price": fill_price,
                                "entry_cost": total_cost,
                                "entry_time": candle.timestamp,
                                "quantity": quantity,
                            }

            equity = cash + ((int(position["quantity"]) * candle.close) if position is not None else 0.0)
            equity_curve.append(round(equity, 4))

        if position is not None:
            last_candle = candles[-1]
            quantity = int(position["quantity"])
            fill_price = last_candle.close * (1 - self.slippage_multiplier)
            fee = fill_price * quantity * self.fee_multiplier
            proceeds = (fill_price * quantity) - fee
            cash += proceeds
            entry_cost = float(position["entry_cost"])
            pnl = proceeds - entry_cost
            trades.append(
                BacktestTrade(
                    symbol=symbol,
                    strategy_id=genome.strategy_id,
                    entry_time=position["entry_time"],
                    exit_time=last_candle.timestamp,
                    entry_price=float(position["entry_price"]),
                    exit_price=round(fill_price, 4),
                    quantity=quantity,
                    pnl=round(pnl, 4),
                    return_pct=round(pnl / entry_cost if entry_cost else 0.0, 6),
                )
            )
            equity_curve.append(round(cash, 4))

        metrics = self._build_metrics(initial_capital, cash, equity_curve, trades)
        return BacktestResult(genome=genome, metrics=metrics, trades=trades)

    def run_walk_forward(
        self,
        symbol: str,
        candles: list[Candle],
        genome: StrategyGenome,
        initial_capital: float,
    ) -> BacktestMetrics:
        genome = self.signal_engine.normalize_genome(genome)
        required_bars = self.signal_engine.required_bars(genome)
        minimum_total_bars = max((required_bars * 2) + 20, 80)
        if len(candles) < minimum_total_bars:
            return self._empty_metrics(initial_capital)

        test_size = max(required_bars, len(candles) // 6, 30)
        initial_train_size = max(required_bars * 3, len(candles) // 2, 90)
        holdout_size = max(test_size, len(candles) // 5, 20)
        validation_end = len(candles) - holdout_size
        initial_train_size = min(initial_train_size, validation_end - max(test_size, 15))
        if initial_train_size <= required_bars:
            return self.run(symbol, candles, genome, initial_capital).metrics

        fold_metrics: list[BacktestMetrics] = []
        train_end = initial_train_size

        while train_end < validation_end:
            test_end = min(validation_end, train_end + test_size)
            out_of_sample_bars = test_end - train_end
            if out_of_sample_bars < max(10, min(required_bars, 20)):
                break

            # The execution simulation receives only its allowed warm-up and
            # out-of-sample validation bars. The untouched final holdout is
            # deliberately excluded from candidate validation.
            warmup_start = max(0, train_end - required_bars)
            segment = candles[warmup_start:test_end]
            result = self.run(
                symbol,
                segment,
                genome,
                initial_capital,
                trade_start_index=train_end - warmup_start,
            )
            fold_metrics.append(result.metrics)
            train_end = test_end

        if not fold_metrics:
            return self._empty_metrics(initial_capital)

        return self._aggregate_metrics(initial_capital, fold_metrics)

    def development_slice(self, candles: list[Candle], genome: StrategyGenome) -> list[Candle]:
        """Return data eligible for fitting/candidate comparison, excluding final holdout."""
        required_bars = self.signal_engine.required_bars(self.signal_engine.normalize_genome(genome))
        holdout_size = max(required_bars, len(candles) // 5, 20)
        if len(candles) <= holdout_size:
            return []
        return candles[:-holdout_size]

    def _position_size(
        self,
        cash: float,
        fill_price: float,
        genome: StrategyGenome,
        confidence: float,
    ) -> int:
        desired_budget = cash * max(0.02, genome.risk_fraction * max(confidence, 0.25))
        quantity = int(desired_budget / fill_price)
        per_share_risk = fill_price * max(genome.stop_loss_pct, 0.005)
        if per_share_risk <= 0:
            return max(0, quantity)

        risk_budget = cash * self.max_risk_per_trade
        capped_quantity = int(risk_budget / per_share_risk)
        if capped_quantity <= 0:
            return 0
        return max(0, min(quantity, capped_quantity))

    def _determine_exit_price(
        self,
        candle: Candle,
        position: dict[str, object],
        genome: StrategyGenome,
    ) -> float | None:
        entry_price = float(position["entry_price"])
        stop_price = entry_price * (1 - genome.stop_loss_pct)
        target_price = entry_price * (1 + genome.take_profit_pct)
        if candle.low <= stop_price:
            return stop_price
        if candle.high >= target_price:
            return target_price
        return None

    def _build_metrics(
        self,
        initial_capital: float,
        final_equity: float,
        equity_curve: list[float],
        trades: list[BacktestTrade],
    ) -> BacktestMetrics:
        total_return = (final_equity / initial_capital) - 1 if initial_capital else 0.0
        drawdown = self._max_drawdown(equity_curve)
        sharpe = self._sharpe_ratio(equity_curve)

        wins = [trade.pnl for trade in trades if trade.pnl > 0]
        losses = [trade.pnl for trade in trades if trade.pnl < 0]
        win_rate = (len(wins) / len(trades)) if trades else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0)

        return BacktestMetrics(
            total_return=round(total_return, 6),
            sharpe_ratio=round(sharpe, 6),
            max_drawdown=round(drawdown, 6),
            win_rate=round(win_rate, 6),
            profit_factor=round(profit_factor, 6),
            trades=len(trades),
            final_equity=round(final_equity, 4),
        )

    def _max_drawdown(self, equity_curve: list[float]) -> float:
        peak = equity_curve[0] if equity_curve else 0.0
        max_drawdown = 0.0
        for equity in equity_curve:
            peak = max(peak, equity)
            if peak == 0:
                continue
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        return max_drawdown

    def _sharpe_ratio(self, equity_curve: list[float]) -> float:
        if len(equity_curve) < 3:
            return 0.0

        returns = []
        for index in range(1, len(equity_curve)):
            previous = equity_curve[index - 1]
            current = equity_curve[index]
            if previous == 0:
                continue
            returns.append((current / previous) - 1)

        if len(returns) < 2:
            return 0.0

        volatility = stdev(returns)
        if volatility == 0:
            return 0.0
        return (fmean(returns) / volatility) * (252 ** 0.5)

    def _empty_metrics(self, initial_capital: float) -> BacktestMetrics:
        return BacktestMetrics(
            total_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            trades=0,
            final_equity=round(initial_capital, 4),
        )

    def _aggregate_metrics(
        self,
        initial_capital: float,
        fold_metrics: list[BacktestMetrics],
    ) -> BacktestMetrics:
        compounded_equity = initial_capital
        for metrics in fold_metrics:
            compounded_equity *= 1 + metrics.total_return

        total_trades = sum(metrics.trades for metrics in fold_metrics)
        traded_folds = [metrics for metrics in fold_metrics if metrics.trades > 0]
        weight_basis = sum(metrics.trades for metrics in traded_folds)

        if weight_basis > 0:
            win_rate = sum(metrics.win_rate * metrics.trades for metrics in traded_folds) / weight_basis
            profit_factor = sum(metrics.profit_factor * metrics.trades for metrics in traded_folds) / weight_basis
        else:
            win_rate = fmean(metrics.win_rate for metrics in fold_metrics)
            profit_factor = fmean(metrics.profit_factor for metrics in fold_metrics)

        total_return = (compounded_equity / initial_capital) - 1 if initial_capital else 0.0
        sharpe_ratio = fmean(metrics.sharpe_ratio for metrics in fold_metrics)
        max_drawdown = max(metrics.max_drawdown for metrics in fold_metrics)

        return BacktestMetrics(
            total_return=round(total_return, 6),
            sharpe_ratio=round(sharpe_ratio, 6),
            max_drawdown=round(max_drawdown, 6),
            win_rate=round(win_rate, 6),
            profit_factor=round(profit_factor, 6),
            trades=total_trades,
            final_equity=round(compounded_equity, 4),
        )
