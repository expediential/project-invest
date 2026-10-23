from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderStatus(str, Enum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class StrategyFamily(str, Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"


class StrategyRegistryStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class TradeMemoryStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class TradeMemoryOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    FLAT = "flat"


class RuntimeComponentState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


class RuntimeComponentStatus(BaseModel):
    """Persisted heartbeat from a worker process, safe to read from the API process."""

    model_config = ConfigDict(extra="forbid")

    component: Literal["research_worker", "trading_worker"]
    state: RuntimeComponentState
    updated_at: datetime = Field(default_factory=utc_now)
    heartbeat_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    cycle_started_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_cycle_duration_seconds: float | None = None


class Candle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    data_source: str = "unknown"


class FeatureRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timestamp: datetime
    close: float
    sma_5: float | None = None
    sma_20: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    rsi_14: float | None = None
    momentum_5: float | None = None
    volatility_10: float | None = None
    volume_zscore_20: float | None = None
    sentiment_score: float | None = None
    news_intensity: float | None = None


class StrategyGenome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(default_factory=lambda: f"strat-{uuid4().hex[:10]}")
    family: StrategyFamily = StrategyFamily.TREND_FOLLOWING
    short_window: int = 8
    long_window: int = 21
    momentum_threshold: float = 0.01
    mean_reversion_threshold: float = 0.015
    rsi_entry_threshold: float = 35.0
    rsi_exit_threshold: float = 55.0
    breakout_lookback: int = 20
    breakout_buffer: float = 0.003
    volume_confirmation: float = 1.1
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    risk_fraction: float = 0.1


class TradeSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    action: SignalAction
    confidence: float
    reason: str
    strategy_id: str
    timestamp: datetime = Field(default_factory=utc_now)


class BacktestTrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    strategy_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    return_pct: float


class BacktestMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trades: int
    final_equity: float


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genome: StrategyGenome
    metrics: BacktestMetrics
    trades: list[BacktestTrade] = Field(default_factory=list)


class StrategyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genome: StrategyGenome
    metrics: BacktestMetrics
    validation_metrics: BacktestMetrics | None = None
    robustness_score: float = 0.0
    score: float


class EvolutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    population_size: int
    generations: int
    champion: StrategyEvaluation
    leaderboard: list[StrategyEvaluation] = Field(default_factory=list)
    latest_signal: TradeSignal
    market_regime: MarketRegime | None = None
    meta_selected: StrategyEvaluation | None = None
    meta_reason: str | None = None


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    quantity: int
    average_price: float
    opened_at: datetime
    last_price: float
    strategy_id: str
    entry_fee_paid: float = 0.0
    last_price_at: datetime | None = None


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    starting_capital: float
    cash: float
    realized_pnl: float = 0.0
    daily_pnl: float | None = None
    open_exposure: float = 0.0
    total_equity: float
    positions: dict[str, Position] = Field(default_factory=dict)

    @classmethod
    def bootstrap(cls, starting_capital: float) -> "PortfolioSnapshot":
        return cls(
            as_of=utc_now(),
            starting_capital=starting_capital,
            cash=starting_capital,
            total_equity=starting_capital,
        )


class PortfolioHistorySnapshot(BaseModel):
    """Immutable accounting point captured when the persisted portfolio changes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    snapshot_id: str = Field(default_factory=lambda: f"portfolio-{uuid4().hex}")
    captured_at: datetime = Field(default_factory=utc_now)
    as_of: datetime
    starting_capital: float
    cash: float
    realized_pnl: float
    open_exposure: float
    total_equity: float
    position_count: int

    @classmethod
    def from_portfolio(cls, portfolio: PortfolioSnapshot) -> "PortfolioHistorySnapshot":
        return cls(
            as_of=portfolio.as_of,
            starting_capital=portfolio.starting_capital,
            cash=portfolio.cash,
            realized_pnl=portfolio.realized_pnl,
            open_exposure=portfolio.open_exposure,
            total_equity=portfolio.total_equity,
            position_count=len(portfolio.positions),
        )


class RiskLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_risk_per_trade: float
    max_daily_loss: float
    max_positions: int
    max_gross_exposure: float
    max_position_pct: float
    max_drawdown: float


class RiskDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    allowed_quantity: int
    reason: str


class ExecutionOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_id: str = Field(default_factory=lambda: f"order-{uuid4().hex[:10]}")
    mode: ExecutionMode
    symbol: str
    action: SignalAction
    status: OrderStatus
    quantity: int
    requested_price: float
    fill_price: float
    fee_paid: float
    realized_pnl: float = 0.0
    note: str
    strategy_id: str
    timestamp: datetime = Field(default_factory=utc_now)


class ResearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"event-{uuid4().hex[:10]}")
    timestamp: datetime = Field(default_factory=utc_now)
    symbol: str
    strategy_id: str
    regime: MarketRegime | None = None
    strategy_family: StrategyFamily | None = None
    meta_reason: str | None = None
    timeframe_alignment: list[dict[str, object]] | None = None
    signal_action: SignalAction
    signal_confidence: float
    signal_reason: str
    order_action: SignalAction
    order_status: OrderStatus
    order_note: str | None = None
    price: float
    realized_pnl: float = 0.0
    rsi_14: float | None = None
    momentum_5: float | None = None
    volatility_10: float | None = None
    sma_20: float | None = None
    ema_12: float | None = None
    sentiment_score: float | None = None
    news_intensity: float | None = None


class TradeMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(default_factory=lambda: f"memory-{uuid4().hex[:10]}")
    symbol: str
    market: str | None = None
    strategy_id: str
    strategy_family: StrategyFamily | None = None
    entry_trade_id: str
    exit_trade_id: str | None = None
    status: TradeMemoryStatus = TradeMemoryStatus.OPEN
    outcome: TradeMemoryOutcome | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    holding_minutes: float | None = None
    quantity: int
    entry_price: float
    exit_price: float | None = None
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    realized_pnl: float = 0.0
    return_pct: float | None = None
    success_label: int | None = None
    entry_confidence: float | None = None
    close_confidence: float | None = None
    entry_reason: str | None = None
    close_reason: str | None = None
    entry_note: str | None = None
    close_note: str | None = None
    entry_regime: MarketRegime | None = None
    close_regime: MarketRegime | None = None
    meta_reason: str | None = None
    timeframe_alignment: list[dict[str, object]] | None = None
    rsi_14: float | None = None
    momentum_5: float | None = None
    volatility_10: float | None = None
    sma_20: float | None = None
    ema_12: float | None = None
    sentiment_score: float | None = None
    news_intensity: float | None = None


class StrategyRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    genome: StrategyGenome
    status: StrategyRegistryStatus = StrategyRegistryStatus.CANDIDATE
    last_score: float = 0.0
    last_validation_sharpe: float = 0.0
    last_validation_return: float = 0.0
    last_signal_action: SignalAction | None = None
    last_order_status: OrderStatus | None = None
    last_seen_at: datetime = Field(default_factory=utc_now)
    last_order_at: datetime | None = None
    times_selected: int = 0
    paper_entry_count: int = 0
    paper_exit_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    cumulative_realized_pnl: float = 0.0
    stale_cycles: int = 0


class SymbolResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    candles_collected: int
    feature_rows: int
    executed_strategy_id: str | None = None
    evolution: EvolutionReport
    latest_order: ExecutionOrder


class ResearchCycleReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    provider: str
    interval: str
    symbols: list[str]
    results: list[SymbolResearchResult]
    portfolio: PortfolioSnapshot
