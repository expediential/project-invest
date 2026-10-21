from __future__ import annotations

import random
from uuid import uuid4

from project_invest.domain.models import (
    BacktestMetrics,
    Candle,
    EvolutionReport,
    MarketRegime,
    StrategyEvaluation,
    StrategyFamily,
    StrategyGenome,
)
from project_invest.services.backtesting import BacktestingEngine
from project_invest.services.strategy_signals import StrategySignalEngine


class StrategyEvolutionEngine:
    def __init__(
        self,
        backtester: BacktestingEngine,
        signal_engine: StrategySignalEngine,
        population_size: int,
        generations: int,
        seed: int,
        initial_capital: float,
    ) -> None:
        self.backtester = backtester
        self.signal_engine = signal_engine
        self.population_size = max(6, population_size)
        self.generations = max(1, generations)
        self.initial_capital = initial_capital
        self.random = random.Random(seed)

    def evolve(
        self,
        symbol: str,
        candles: list[Candle],
        has_position: bool = False,
        seed_genomes: list[StrategyGenome] | None = None,
        market_regime: MarketRegime | None = None,
    ) -> EvolutionReport:
        population = self._build_initial_population(seed_genomes or [], market_regime)
        champion: StrategyEvaluation | None = None
        leaderboard: list[StrategyEvaluation] = []

        for _ in range(self.generations):
            evaluations = [self._evaluate(symbol, candles, genome) for genome in population]
            evaluations.sort(key=lambda item: item.score, reverse=True)

            if champion is None or evaluations[0].score > champion.score:
                champion = evaluations[0]
            leaderboard = evaluations[: min(5, len(evaluations))]

            elite_count = max(2, self.population_size // 4)
            elites = [evaluation.genome for evaluation in evaluations[:elite_count]]
            next_population = elites.copy()

            selection_pool = evaluations[: max(3, len(evaluations) // 2)]
            while len(next_population) < self.population_size:
                parent_a = self.random.choice(selection_pool).genome
                parent_b = self.random.choice(selection_pool).genome
                child = self._crossover(parent_a, parent_b)
                if self.random.random() < 0.35:
                    child = self._mutate(child)
                next_population.append(self.signal_engine.normalize_genome(child))

            population = next_population

        if champion is None:
            champion = self._evaluate(symbol, candles, self._random_genome())
            leaderboard = [champion]

        latest_signal = self.signal_engine.generate_signal(champion.genome, candles, has_position=has_position)
        return EvolutionReport(
            symbol=symbol,
            population_size=self.population_size,
            generations=self.generations,
            champion=champion,
            leaderboard=leaderboard,
            latest_signal=latest_signal,
        )

    def _build_initial_population(
        self,
        seed_genomes: list[StrategyGenome],
        market_regime: MarketRegime | None,
    ) -> list[StrategyGenome]:
        population: list[StrategyGenome] = []
        seen: set[str] = set()

        for genome in seed_genomes:
            normalized = self.signal_engine.normalize_genome(genome)
            if normalized.strategy_id in seen:
                continue
            population.append(normalized)
            seen.add(normalized.strategy_id)
            if len(population) >= self.population_size:
                return population

        while len(population) < self.population_size:
            genome = self._random_genome(market_regime)
            if genome.strategy_id in seen:
                continue
            population.append(genome)
            seen.add(genome.strategy_id)

        return population

    def _evaluate(self, symbol: str, candles: list[Candle], genome: StrategyGenome) -> StrategyEvaluation:
        development_candles = self.backtester.development_slice(candles, genome)
        full_backtest = self.backtester.run(symbol, development_candles, genome, self.initial_capital)
        validation_metrics = self.backtester.run_walk_forward(
            symbol,
            development_candles,
            full_backtest.genome,
            self.initial_capital,
        )
        full_score = self._metrics_score(full_backtest.metrics)
        validation_score = self._metrics_score(validation_metrics)
        robustness_score = self._robustness_score(full_backtest.metrics, validation_metrics)
        validation_penalty = 0.25 if validation_metrics.trades == 0 else 0.0
        score = (validation_score * 0.7) + (full_score * 0.3) + robustness_score - validation_penalty

        return StrategyEvaluation(
            genome=full_backtest.genome,
            metrics=full_backtest.metrics,
            validation_metrics=validation_metrics,
            robustness_score=round(robustness_score, 6),
            score=round(score, 6),
        )

    def _random_genome(self, market_regime: MarketRegime | None = None) -> StrategyGenome:
        family = self._choose_family(market_regime)
        short_window = self.random.randint(3, 12)
        long_window = self.random.randint(short_window + 3, 42)
        if family == StrategyFamily.MEAN_REVERSION:
            short_window = self.random.randint(3, 10)
            long_window = self.random.randint(max(short_window + 3, 12), 48)
        elif family == StrategyFamily.BREAKOUT:
            short_window = self.random.randint(4, 10)
            long_window = self.random.randint(max(short_window + 4, 14), 52)

        genome = StrategyGenome(
            family=family,
            short_window=short_window,
            long_window=long_window,
            momentum_threshold=round(self.random.uniform(0.0, 0.018), 4),
            mean_reversion_threshold=round(self.random.uniform(0.0005, 0.014), 4),
            rsi_entry_threshold=round(self.random.uniform(34.0, 62.0), 2),
            rsi_exit_threshold=round(self.random.uniform(42.0, 72.0), 2),
            breakout_lookback=self.random.randint(6, 28),
            breakout_buffer=round(self.random.uniform(0.0, 0.004), 4),
            volume_confirmation=round(self.random.uniform(0.65, 1.15), 2),
            stop_loss_pct=round(self.random.uniform(0.006, 0.03), 4),
            take_profit_pct=round(self.random.uniform(0.012, 0.07), 4),
            risk_fraction=round(self.random.uniform(0.03, 0.16), 4),
        )
        return self.signal_engine.normalize_genome(genome)

    def _choose_family(self, market_regime: MarketRegime | None) -> StrategyFamily:
        if market_regime is None:
            return self.random.choice(list(StrategyFamily))

        weights = {
            StrategyFamily.TREND_FOLLOWING: 0.33,
            StrategyFamily.MEAN_REVERSION: 0.33,
            StrategyFamily.BREAKOUT: 0.34,
        }
        if market_regime == MarketRegime.TRENDING:
            weights = {
                StrategyFamily.TREND_FOLLOWING: 0.6,
                StrategyFamily.BREAKOUT: 0.25,
                StrategyFamily.MEAN_REVERSION: 0.15,
            }
        elif market_regime == MarketRegime.SIDEWAYS:
            weights = {
                StrategyFamily.MEAN_REVERSION: 0.6,
                StrategyFamily.TREND_FOLLOWING: 0.25,
                StrategyFamily.BREAKOUT: 0.15,
            }
        elif market_regime == MarketRegime.HIGH_VOL:
            weights = {
                StrategyFamily.BREAKOUT: 0.45,
                StrategyFamily.TREND_FOLLOWING: 0.35,
                StrategyFamily.MEAN_REVERSION: 0.2,
            }
        elif market_regime == MarketRegime.LOW_VOL:
            weights = {
                StrategyFamily.MEAN_REVERSION: 0.55,
                StrategyFamily.TREND_FOLLOWING: 0.3,
                StrategyFamily.BREAKOUT: 0.15,
            }

        roll = self.random.random()
        cumulative = 0.0
        for family, weight in weights.items():
            cumulative += weight
            if roll <= cumulative:
                return family
        return self.random.choice(list(StrategyFamily))

    def _crossover(self, left: StrategyGenome, right: StrategyGenome) -> StrategyGenome:
        family = self.random.choice([left.family, right.family])
        child = StrategyGenome(
            family=family,
            short_window=self.random.choice([left.short_window, right.short_window]),
            long_window=self.random.choice([left.long_window, right.long_window]),
            momentum_threshold=round((left.momentum_threshold + right.momentum_threshold) / 2, 4),
            mean_reversion_threshold=round(
                (left.mean_reversion_threshold + right.mean_reversion_threshold) / 2,
                4,
            ),
            rsi_entry_threshold=round((left.rsi_entry_threshold + right.rsi_entry_threshold) / 2, 2),
            rsi_exit_threshold=round((left.rsi_exit_threshold + right.rsi_exit_threshold) / 2, 2),
            breakout_lookback=self.random.choice([left.breakout_lookback, right.breakout_lookback]),
            breakout_buffer=round(self.random.choice([left.breakout_buffer, right.breakout_buffer]), 4),
            volume_confirmation=round((left.volume_confirmation + right.volume_confirmation) / 2, 2),
            stop_loss_pct=round(self.random.choice([left.stop_loss_pct, right.stop_loss_pct]), 4),
            take_profit_pct=round(self.random.choice([left.take_profit_pct, right.take_profit_pct]), 4),
            risk_fraction=round((left.risk_fraction + right.risk_fraction) / 2, 4),
        )
        return self.signal_engine.normalize_genome(child)

    def _mutate(self, genome: StrategyGenome) -> StrategyGenome:
        family = genome.family
        if self.random.random() < 0.12:
            family = self.random.choice(list(StrategyFamily))

        mutations = {
            "family": family,
            "short_window": max(3, genome.short_window + self.random.randint(-4, 3)),
            "long_window": max(genome.short_window + 3, genome.long_window + self.random.randint(-8, 6)),
            "momentum_threshold": round(max(0.0, genome.momentum_threshold + self.random.uniform(-0.006, 0.006)), 4),
            "mean_reversion_threshold": round(
                max(0.0005, genome.mean_reversion_threshold + self.random.uniform(-0.004, 0.004)),
                4,
            ),
            "rsi_entry_threshold": round(max(18.0, genome.rsi_entry_threshold + self.random.uniform(-10.0, 10.0)), 2),
            "rsi_exit_threshold": round(max(35.0, genome.rsi_exit_threshold + self.random.uniform(-10.0, 10.0)), 2),
            "breakout_lookback": max(6, genome.breakout_lookback + self.random.randint(-10, 8)),
            "breakout_buffer": round(max(0.0, genome.breakout_buffer + self.random.uniform(-0.003, 0.003)), 4),
            "volume_confirmation": round(
                max(0.6, genome.volume_confirmation + self.random.uniform(-0.18, 0.18)),
                2,
            ),
            "stop_loss_pct": round(max(0.005, genome.stop_loss_pct + self.random.uniform(-0.008, 0.008)), 4),
            "take_profit_pct": round(max(0.01, genome.take_profit_pct + self.random.uniform(-0.015, 0.015)), 4),
            "risk_fraction": round(max(0.01, genome.risk_fraction + self.random.uniform(-0.04, 0.04)), 4),
        }
        mutated = genome.model_copy(
            update={
                **mutations,
                "strategy_id": f"strat-{uuid4().hex[:10]}",
            }
        )
        return self.signal_engine.normalize_genome(mutated)

    def _metrics_score(self, metrics: BacktestMetrics) -> float:
        trade_penalty = 0.15 if metrics.trades == 0 else 0.0
        trade_bonus = min(0.25, (metrics.trades / 80) * 0.25)
        profit_factor_component = min(metrics.profit_factor, 3.0) * 0.15
        return (
            (metrics.total_return * 2.6)
            + (metrics.sharpe_ratio * 0.8)
            + (metrics.win_rate * 0.4)
            + profit_factor_component
            + trade_bonus
            - (metrics.max_drawdown * 1.4)
            - trade_penalty
        )

    def _robustness_score(
        self,
        full_metrics: BacktestMetrics,
        validation_metrics: BacktestMetrics,
    ) -> float:
        if validation_metrics.trades == 0:
            return -0.25

        return_gap = abs(full_metrics.total_return - validation_metrics.total_return)
        sharpe_gap = abs(full_metrics.sharpe_ratio - validation_metrics.sharpe_ratio)
        drawdown_penalty = max(0.0, validation_metrics.max_drawdown - full_metrics.max_drawdown) * 0.8
        trade_coverage = min(1.0, validation_metrics.trades / max(full_metrics.trades, 1))
        stability_bonus = max(0.0, 0.25 - return_gap) + max(0.0, 0.75 - sharpe_gap) * 0.2
        stability_penalty = (return_gap * 1.15) + (sharpe_gap * 0.12) + drawdown_penalty
        return (trade_coverage * 0.15) + stability_bonus - stability_penalty
