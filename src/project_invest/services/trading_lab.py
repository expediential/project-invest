from __future__ import annotations

from dataclasses import asdict

from project_invest.domain.models import (
    BacktestMetrics,
    Candle,
    EvolutionReport,
    MarketRegime,
    OrderStatus,
    ResearchCycleReport,
    ResearchEvent,
    SignalAction,
    StrategyEvaluation,
    StrategyGenome,
    StrategyRegistryEntry,
    StrategyRegistryStatus,
    SymbolResearchResult,
    TradeSignal,
    utc_now,
)
from project_invest.execution.base import ExecutionEngine
from project_invest.services.feature_engineering import FeatureEngineeringEngine
from project_invest.services.ingestion import MarketDataIngestionService
from project_invest.services.market_regime import MarketRegimeDetector
from project_invest.services.meta_strategy import MetaStrategySelector
from project_invest.services.multi_timeframe import MultiTimeframeGate
from project_invest.services.sentiment_overlay import SentimentSignalAdjuster
from project_invest.services.trade_memory import TradeMemoryService
from project_invest.services.strategy_promotion import StrategyPromotionGate
from project_invest.services.strategy_registry import StrategyRegistryService
from project_invest.services.strategy_signals import StrategySignalEngine
from project_invest.services.universe import market_for_symbol
from project_invest.storage.repositories import (
    ActiveStrategyRepository,
    EventLogRepository,
    FeatureRepository,
    ReportRepository,
    StrategyRegistryRepository,
)


class TradingLab:
    def __init__(
        self,
        ingestion: MarketDataIngestionService,
        feature_engine: FeatureEngineeringEngine,
        signal_engine: StrategySignalEngine,
        execution_engine: ExecutionEngine,
        promotion_gate: StrategyPromotionGate,
        strategy_registry_service: StrategyRegistryService,
        market_regime_detector: MarketRegimeDetector,
        meta_strategy_selector: MetaStrategySelector,
        multi_timeframe_gate: MultiTimeframeGate | None,
        sentiment_adjuster: SentimentSignalAdjuster | None,
        sentiment_memory_enabled: bool,
        sentiment_memory_lookback: int,
        sentiment_memory_min_records: int,
        active_strategy_repository: ActiveStrategyRepository,
        strategy_registry_repository: StrategyRegistryRepository,
        feature_repository: FeatureRepository,
        report_repository: ReportRepository,
        event_log_repository: EventLogRepository,
        trade_memory_service: TradeMemoryService | None,
        interval: str,
        lookback_bars: int,
        confirmation_lookback_bars: int,
        default_symbols: list[str],
        execution_markets: list[str],
        allow_mock_data: bool,
    ) -> None:
        self.ingestion = ingestion
        self.feature_engine = feature_engine
        self.signal_engine = signal_engine
        self.execution_engine = execution_engine
        self.promotion_gate = promotion_gate
        self.strategy_registry_service = strategy_registry_service
        self.market_regime_detector = market_regime_detector
        self.meta_strategy_selector = meta_strategy_selector
        self.multi_timeframe_gate = multi_timeframe_gate
        self.sentiment_adjuster = sentiment_adjuster
        self.sentiment_memory_enabled = sentiment_memory_enabled
        self.sentiment_memory_lookback = sentiment_memory_lookback
        self.sentiment_memory_min_records = sentiment_memory_min_records
        self.active_strategy_repository = active_strategy_repository
        self.strategy_registry_repository = strategy_registry_repository
        self.feature_repository = feature_repository
        self.report_repository = report_repository
        self.event_log_repository = event_log_repository
        self.trade_memory_service = trade_memory_service
        self.interval = interval
        self.lookback_bars = lookback_bars
        self.confirmation_lookback_bars = confirmation_lookback_bars
        self.default_symbols = default_symbols
        self.execution_markets = {market.upper() for market in execution_markets}
        self.allow_mock_data = allow_mock_data

    async def run_cycle(self, symbols: list[str] | None = None) -> ResearchCycleReport:
        active_symbols = symbols or self.default_symbols
        started_at = utc_now()
        results: list[SymbolResearchResult] = []
        latest_prices: dict[str, float] = {}
        provider_name = getattr(self.ingestion.primary_provider, "name", "unknown")
        latest_report = self.report_repository.load_latest_report(stream="research")
        report_results = {item.symbol: item for item in latest_report.results} if latest_report else {}

        for symbol in active_symbols:
            provider_name, candles = await self.ingestion.ingest_symbol(symbol, self.interval, self.lookback_bars)
            self._assert_tradable_market_data(symbol, candles)
            features = self.feature_engine.build_feature_rows(candles)
            self.feature_repository.store_features(symbol, self.interval, features)
            latest_feature = features[-1] if features else None
            confirmation_candles: dict[str, list[Candle]] = {}
            if self.multi_timeframe_gate and self.multi_timeframe_gate.intervals:
                for interval in self.multi_timeframe_gate.intervals:
                    if interval == self.interval:
                        continue
                    _, tf_candles = await self.ingestion.ingest_symbol(
                        symbol,
                        interval,
                        self.confirmation_lookback_bars,
                    )
                    confirmation_candles[interval] = tf_candles

            current_portfolio = self.execution_engine.get_portfolio(latest_prices)
            existing_position = current_portfolio.positions.get(symbol)
            active_genome = self.active_strategy_repository.load_active_strategy(symbol)
            if existing_position is None and active_genome is not None:
                self.active_strategy_repository.delete_active_strategy(symbol)
                active_genome = None

            market_regime = self.market_regime_detector.detect(candles)
            strategy_registry = self.strategy_registry_repository.load_strategy_registry(symbol)
            base_evolution = report_results.get(symbol).evolution if report_results.get(symbol) else None

            evolution = base_evolution or self._fallback_evolution(symbol)
            executed_genome: StrategyGenome | None = active_genome
            latest_signal: TradeSignal

            if existing_position is not None:
                if executed_genome is None:
                    executed_genome = evolution.champion.genome
                latest_signal = self.signal_engine.generate_signal(executed_genome, candles, has_position=True)
            else:
                evaluations = [evolution.champion, *evolution.leaderboard] if evolution else []
                if evaluations:
                    meta_selected, meta_reason = self.meta_strategy_selector.select(
                        evaluations,
                        strategy_registry,
                        market_regime,
                    )
                    selected = meta_selected or evolution.champion
                    executed_genome = selected.genome
                    raw_signal = self.signal_engine.generate_signal(executed_genome, candles, has_position=False)
                    latest_signal = self.promotion_gate.apply(selected, raw_signal)
                    evolution = evolution.model_copy(
                        update={
                            "meta_selected": meta_selected,
                            "meta_reason": meta_reason,
                        }
                    )
                elif strategy_registry:
                    executed_genome = self._best_registry_genome(strategy_registry, market_regime)
                    latest_signal = self.signal_engine.generate_signal(executed_genome, candles, has_position=False)
                else:
                    executed_genome = self._fallback_genome(symbol)
                    latest_signal = TradeSignal(
                        symbol=symbol,
                        action=SignalAction.HOLD,
                        confidence=0.0,
                        reason="No research results yet. Run a research cycle first.",
                        strategy_id=executed_genome.strategy_id,
                    )

            alignments = []
            if self.multi_timeframe_gate and confirmation_candles:
                latest_signal, alignments = self.multi_timeframe_gate.apply(latest_signal, confirmation_candles)
            if self.sentiment_adjuster is not None:
                memory_edge = None
                if self.sentiment_memory_enabled and self.trade_memory_service is not None:
                    memory_edge = self.trade_memory_service.evaluate_sentiment_edge(
                        symbol=symbol,
                        strategy_family=executed_genome.family if executed_genome is not None else None,
                        sentiment_score=latest_feature.sentiment_score if latest_feature else None,
                        news_intensity=latest_feature.news_intensity if latest_feature else None,
                        lookback=self.sentiment_memory_lookback,
                        min_records=self.sentiment_memory_min_records,
                    )
                latest_signal = self.sentiment_adjuster.apply(latest_signal, latest_feature, memory_edge)

            latest_signal = self._apply_execution_market_gate(latest_signal, existing_position is not None)

            evolution = evolution.model_copy(update={"latest_signal": latest_signal, "market_regime": market_regime})
            latest_price = candles[-1].close
            latest_prices[symbol] = latest_price
            execution_genome = executed_genome or evolution.champion.genome
            order = self.execution_engine.execute(latest_signal, latest_price, execution_genome)
            post_order_portfolio = self.execution_engine.get_portfolio(latest_prices)
            position_active = symbol in post_order_portfolio.positions

            if existing_position is not None and active_genome is None and executed_genome is not None:
                self.active_strategy_repository.save_active_strategy(symbol, executed_genome)

            if order.status == OrderStatus.FILLED:
                if order.action == SignalAction.BUY and executed_genome is not None:
                    self.active_strategy_repository.save_active_strategy(symbol, executed_genome)
                elif order.action == SignalAction.SELL:
                    self.active_strategy_repository.delete_active_strategy(symbol)

            updated_registry = self.strategy_registry_service.update_registry(
                symbol=symbol,
                previous_entries=strategy_registry,
                evolution=evolution,
                executed_genome=executed_genome,
                latest_order=order,
                position_active=position_active,
                finished_at=utc_now(),
            )
            self.strategy_registry_repository.save_strategy_registry(symbol, updated_registry)

            event = ResearchEvent(
                symbol=symbol,
                strategy_id=execution_genome.strategy_id,
                regime=market_regime,
                strategy_family=execution_genome.family,
                meta_reason=evolution.meta_reason,
                timeframe_alignment=[asdict(item) for item in alignments] if alignments else None,
                signal_action=latest_signal.action,
                signal_confidence=latest_signal.confidence,
                signal_reason=latest_signal.reason,
                order_action=order.action,
                order_status=order.status,
                order_note=order.note,
                price=latest_price,
                realized_pnl=order.realized_pnl,
                rsi_14=latest_feature.rsi_14 if latest_feature else None,
                momentum_5=latest_feature.momentum_5 if latest_feature else None,
                volatility_10=latest_feature.volatility_10 if latest_feature else None,
                sma_20=latest_feature.sma_20 if latest_feature else None,
                ema_12=latest_feature.ema_12 if latest_feature else None,
                sentiment_score=latest_feature.sentiment_score if latest_feature else None,
                news_intensity=latest_feature.news_intensity if latest_feature else None,
            )
            self.event_log_repository.append_event(event)
            if self.trade_memory_service is not None:
                self.trade_memory_service.capture(event, order)

            results.append(
                SymbolResearchResult(
                    symbol=symbol,
                    candles_collected=len(candles),
                    feature_rows=len(features),
                    executed_strategy_id=execution_genome.strategy_id if execution_genome is not None else None,
                    evolution=evolution,
                    latest_order=order,
                )
            )

        portfolio = self.execution_engine.get_portfolio(latest_prices)
        report = ResearchCycleReport(
            started_at=started_at,
            finished_at=utc_now(),
            provider=provider_name,
            interval=self.interval,
            symbols=active_symbols,
            results=results,
            portfolio=portfolio,
        )
        self.report_repository.save_latest_report(report, stream="trading")
        return report

    def _best_registry_genome(
        self,
        entries: list[StrategyRegistryEntry],
        regime: MarketRegime | None,
    ) -> StrategyGenome:
        candidates = [entry for entry in entries if entry.status == StrategyRegistryStatus.ACTIVE]
        if not candidates:
            candidates = [entry for entry in entries if entry.status == StrategyRegistryStatus.CANDIDATE]
        if not candidates:
            candidates = entries

        def score_entry(entry: StrategyRegistryEntry) -> float:
            return (
                entry.last_score
                + (entry.last_validation_sharpe * 0.25)
                + (entry.cumulative_realized_pnl * 0.01)
                + (entry.times_selected * 0.02)
            )

        ranked = sorted(candidates, key=score_entry, reverse=True)
        return ranked[0].genome

    def _fallback_genome(self, symbol: str) -> StrategyGenome:
        return StrategyGenome(strategy_id=f"strat-bootstrap-{symbol}")

    def _fallback_evolution(self, symbol: str) -> EvolutionReport:
        genome = self._fallback_genome(symbol)
        metrics = BacktestMetrics(
            total_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            trades=0,
            final_equity=0.0,
        )
        evaluation = StrategyEvaluation(
            genome=genome,
            metrics=metrics,
            validation_metrics=metrics,
            robustness_score=0.0,
            score=0.0,
        )
        signal = TradeSignal(
            symbol=symbol,
            action=SignalAction.HOLD,
            confidence=0.0,
            reason="No research results yet. Run a research cycle first.",
            strategy_id=genome.strategy_id,
        )
        return EvolutionReport(
            symbol=symbol,
            population_size=0,
            generations=0,
            champion=evaluation,
            leaderboard=[],
            latest_signal=signal,
        )

    def _apply_execution_market_gate(self, signal: TradeSignal, has_position: bool) -> TradeSignal:
        if signal.action != SignalAction.BUY or has_position:
            return signal

        market = market_for_symbol(signal.symbol)
        if not self.execution_markets or self._is_execution_market_allowed(market):
            return signal

        return signal.model_copy(
            update={
                "action": SignalAction.HOLD,
                "confidence": 0.0,
                "reason": f"Execution market gate blocked buy: {market} is research-only in the current portfolio.",
            }
        )

    def _is_execution_market_allowed(self, market: str) -> bool:
        if market in self.execution_markets:
            return True
        if market in {"NASDAQ", "NYSE"} and "US" in self.execution_markets:
            return True
        if market == "US" and ("NASDAQ" in self.execution_markets or "NYSE" in self.execution_markets):
            return True
        return False

    def _assert_tradable_market_data(self, symbol: str, candles: list[Candle]) -> None:
        if not candles:
            raise RuntimeError(f"{symbol}: no market data is available for paper execution.")
        if any(candle.data_source == "mock" for candle in candles) and not self.allow_mock_data:
            raise RuntimeError(f"{symbol}: mock-origin data is not eligible for paper execution.")
        if any(candle.data_source == "unknown" for candle in candles) and not self.allow_mock_data:
            raise RuntimeError(f"{symbol}: market-data provenance is unknown; paper execution is blocked.")
