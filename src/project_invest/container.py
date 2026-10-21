from __future__ import annotations

from dataclasses import dataclass

from project_invest.config import Settings, settings
from project_invest.domain.models import ExecutionMode, RiskLimits
from project_invest.execution.base import ExecutionEngine
from project_invest.execution.paper import PaperExecutionEngine
from project_invest.providers.mock import MockMarketDataProvider
from project_invest.providers.yahoo import YahooFinanceProvider
from project_invest.services.analytics import AnalyticsService
from project_invest.services.backtesting import BacktestingEngine
from project_invest.services.feature_engineering import FeatureEngineeringEngine
from project_invest.services.ingestion import MarketDataIngestionService
from project_invest.services.market_regime import MarketRegimeDetector
from project_invest.services.meta_strategy import MetaStrategySelector
from project_invest.services.multi_timeframe import MultiTimeframeGate
from project_invest.services.paper_trading import PaperBroker
from project_invest.services.portfolio_optimization import PortfolioOptimizer
from project_invest.services.research_lab import ResearchLab
from project_invest.services.risk import RiskManager
from project_invest.services.strategy_evolution import StrategyEvolutionEngine
from project_invest.services.strategy_promotion import PromotionThresholds, StrategyPromotionGate
from project_invest.services.strategy_registry import StrategyRegistryService
from project_invest.services.strategy_signals import StrategySignalEngine
from project_invest.services.sentiment import LocalSentimentProvider, NeutralSentimentProvider
from project_invest.services.sentiment_overlay import SentimentSignalAdjuster
from project_invest.services.trade_memory import TradeMemoryService
from project_invest.services.trading_lab import TradingLab
from project_invest.services.universe import resolve_symbols
from project_invest.storage.factory import build_storage
from project_invest.storage.repositories import ResearchStorage


@dataclass
class ServiceContainer:
    settings: Settings
    storage: ResearchStorage
    ingestion: MarketDataIngestionService
    feature_engine: FeatureEngineeringEngine
    signal_engine: StrategySignalEngine
    backtester: BacktestingEngine
    evolution_engine: StrategyEvolutionEngine
    execution_engine: ExecutionEngine
    promotion_gate: StrategyPromotionGate
    strategy_registry: StrategyRegistryService
    trade_memory: TradeMemoryService
    market_regime: MarketRegimeDetector
    meta_strategy: MetaStrategySelector
    sentiment_adjuster: SentimentSignalAdjuster
    research_lab: ResearchLab
    trading_lab: TradingLab
    optimizer: PortfolioOptimizer
    analytics: AnalyticsService

    def close(self) -> None:
        self.storage.close()


def build_container(active_settings: Settings | None = None) -> ServiceContainer:
    current_settings = active_settings or settings
    storage = build_storage(current_settings)

    primary_provider = _build_market_provider(current_settings.market_data_provider)
    ingestion = MarketDataIngestionService(primary_provider, storage)

    if current_settings.sentiment_provider == "local":
        sentiment_provider = LocalSentimentProvider(current_settings.sentiment_data_root)
    else:
        sentiment_provider = NeutralSentimentProvider()
    sentiment_adjuster = SentimentSignalAdjuster(
        min_intensity=current_settings.sentiment_min_intensity,
        confidence_boost=current_settings.sentiment_confidence_boost,
        confidence_penalty=current_settings.sentiment_confidence_penalty,
        reversal_block_threshold=current_settings.sentiment_reversal_block_threshold,
    )
    feature_engine = FeatureEngineeringEngine(sentiment_provider=sentiment_provider)
    signal_engine = StrategySignalEngine()

    effective_risk = current_settings.max_risk_per_trade
    if current_settings.execution_mode == ExecutionMode.LIVE.value:
        effective_risk = min(effective_risk, current_settings.live_max_risk_per_trade)

    risk_limits = RiskLimits(
        max_risk_per_trade=effective_risk,
        max_daily_loss=current_settings.max_daily_loss,
        max_positions=current_settings.max_positions,
        max_gross_exposure=current_settings.max_gross_exposure,
        max_position_pct=current_settings.max_position_pct,
        max_drawdown=current_settings.max_drawdown,
    )
    risk_manager = RiskManager(risk_limits)

    backtester = BacktestingEngine(
        signal_engine=signal_engine,
        slippage_bps=current_settings.order_slippage_bps,
        fee_bps=current_settings.fee_bps,
        max_risk_per_trade=effective_risk,
    )
    evolution_engine = StrategyEvolutionEngine(
        backtester=backtester,
        signal_engine=signal_engine,
        population_size=current_settings.population_size,
        generations=current_settings.generations,
        seed=current_settings.evolution_seed,
        initial_capital=current_settings.starting_capital,
    )
    promotion_gate = StrategyPromotionGate(
        PromotionThresholds(
            min_validation_sharpe=current_settings.min_validation_sharpe,
            min_validation_return=current_settings.min_validation_return,
            max_validation_drawdown=current_settings.max_validation_drawdown,
            min_validation_trades=current_settings.min_validation_trades,
            min_validation_profit_factor=current_settings.min_validation_profit_factor,
            min_validation_win_rate=current_settings.min_validation_win_rate,
            min_validation_trade_coverage=current_settings.min_validation_trade_coverage,
            max_validation_return_gap=current_settings.max_validation_return_gap,
            max_validation_sharpe_gap=current_settings.max_validation_sharpe_gap,
        )
    )
    strategy_registry = StrategyRegistryService()
    trade_memory = TradeMemoryService(storage)
    market_regime = MarketRegimeDetector(
        trend_threshold=current_settings.regime_trend_threshold,
        high_vol_threshold=current_settings.regime_high_vol_threshold,
        low_vol_threshold=current_settings.regime_low_vol_threshold,
        lookback=current_settings.regime_lookback,
    )
    meta_strategy = MetaStrategySelector()
    multi_timeframe_gate = MultiTimeframeGate(
        intervals=current_settings.confirmation_intervals,
        short_window=current_settings.confirmation_short_window,
        long_window=current_settings.confirmation_long_window,
        min_trend_strength=current_settings.confirmation_min_trend_strength,
    )

    paper_broker = PaperBroker(
        portfolio_repository=storage,
        trade_repository=storage,
        risk_manager=risk_manager,
        starting_capital=current_settings.starting_capital,
        slippage_bps=current_settings.order_slippage_bps,
        fee_bps=current_settings.fee_bps,
    )
    execution_engine = _build_execution_engine(current_settings, paper_broker)

    resolved_symbols = resolve_symbols(
        current_settings.research_symbols,
        current_settings.use_market_universes,
        current_settings.market_universes,
    )
    research_lab = ResearchLab(
        ingestion=ingestion,
        feature_engine=feature_engine,
        evolution_engine=evolution_engine,
        signal_engine=signal_engine,
        execution_engine=execution_engine,
        promotion_gate=promotion_gate,
        strategy_registry_service=strategy_registry,
        market_regime_detector=market_regime,
        meta_strategy_selector=meta_strategy,
        multi_timeframe_gate=multi_timeframe_gate,
        sentiment_adjuster=sentiment_adjuster,
        sentiment_memory_enabled=current_settings.sentiment_memory_enabled,
        sentiment_memory_lookback=current_settings.sentiment_memory_lookback,
        sentiment_memory_min_records=current_settings.sentiment_memory_min_records,
        active_strategy_repository=storage,
        strategy_registry_repository=storage,
        feature_repository=storage,
        report_repository=storage,
        event_log_repository=storage,
        trade_memory_service=trade_memory,
        interval=current_settings.research_interval,
        lookback_bars=current_settings.lookback_bars,
        confirmation_lookback_bars=current_settings.confirmation_lookback_bars,
        default_symbols=resolved_symbols,
    )
    trading_lab = TradingLab(
        ingestion=ingestion,
        feature_engine=feature_engine,
        signal_engine=signal_engine,
        execution_engine=execution_engine,
        promotion_gate=promotion_gate,
        strategy_registry_service=strategy_registry,
        market_regime_detector=market_regime,
        meta_strategy_selector=meta_strategy,
        multi_timeframe_gate=multi_timeframe_gate,
        sentiment_adjuster=sentiment_adjuster,
        sentiment_memory_enabled=current_settings.sentiment_memory_enabled,
        sentiment_memory_lookback=current_settings.sentiment_memory_lookback,
        sentiment_memory_min_records=current_settings.sentiment_memory_min_records,
        active_strategy_repository=storage,
        strategy_registry_repository=storage,
        feature_repository=storage,
        report_repository=storage,
        event_log_repository=storage,
        trade_memory_service=trade_memory,
        interval=current_settings.trading_interval,
        lookback_bars=current_settings.trading_lookback_bars,
        confirmation_lookback_bars=current_settings.confirmation_lookback_bars,
        default_symbols=resolved_symbols,
        execution_markets=current_settings.execution_markets,
        allow_mock_data=current_settings.allow_mock_data,
    )

    optimizer = PortfolioOptimizer()
    analytics = AnalyticsService(optimizer)
    return ServiceContainer(
        settings=current_settings,
        storage=storage,
        ingestion=ingestion,
        feature_engine=feature_engine,
        signal_engine=signal_engine,
        backtester=backtester,
        evolution_engine=evolution_engine,
        execution_engine=execution_engine,
        promotion_gate=promotion_gate,
        strategy_registry=strategy_registry,
        trade_memory=trade_memory,
        market_regime=market_regime,
        meta_strategy=meta_strategy,
        sentiment_adjuster=sentiment_adjuster,
        research_lab=research_lab,
        trading_lab=trading_lab,
        optimizer=optimizer,
        analytics=analytics,
    )


def _build_market_provider(provider_name: str):
    if provider_name == "yahoo":
        return YahooFinanceProvider()
    return MockMarketDataProvider()


def _build_execution_engine(settings: Settings, paper_broker: PaperBroker) -> ExecutionEngine:
    if settings.execution_mode != ExecutionMode.PAPER.value:
        raise RuntimeError("Only paper execution is supported; live execution is disabled.")
    return PaperExecutionEngine(paper_broker)
