from __future__ import annotations

from typing import Protocol

from project_invest.domain.models import (
    Candle,
    ExecutionOrder,
    FeatureRow,
    PortfolioHistorySnapshot,
    PortfolioSnapshot,
    ResearchCycleReport,
    ResearchEvent,
    ResearchJob,
    RuntimeComponentStatus,
    TradeMemoryRecord,
    StrategyGenome,
    StrategyRegistryEntry,
)


class CandleRepository(Protocol):
    def store_candles(self, symbol: str, interval: str, candles: list[Candle], stage: str) -> None:
        """Persist candles for a symbol and interval."""

    def load_candles(self, symbol: str, interval: str, stage: str) -> list[Candle]:
        """Load candles for a symbol and interval."""


class FeatureRepository(Protocol):
    def store_features(self, symbol: str, interval: str, rows: list[FeatureRow]) -> None:
        """Persist engineered features."""

    def load_features(self, symbol: str, interval: str) -> list[FeatureRow]:
        """Load engineered features."""


class PortfolioRepository(Protocol):
    def save_portfolio(self, portfolio: PortfolioSnapshot) -> None:
        """Persist the latest portfolio state."""

    def load_portfolio(self) -> PortfolioSnapshot | None:
        """Load the latest portfolio state."""


class PortfolioHistoryRepository(Protocol):
    def load_portfolio_history(self, limit: int | None = None) -> list[PortfolioHistorySnapshot]:
        """Load immutable portfolio accounting points in chronological order."""


class TradeRepository(Protocol):
    def append_trade(self, trade: ExecutionOrder) -> None:
        """Persist an executed order."""

    def load_trades(self, limit: int | None = None) -> list[ExecutionOrder]:
        """Load recent or full trade history."""


class ReportRepository(Protocol):
    def save_latest_report(self, report: ResearchCycleReport, stream: str = "research") -> None:
        """Persist the latest research report and any historical copy."""

    def load_latest_report(self, stream: str = "research") -> ResearchCycleReport | None:
        """Load the latest research report."""


class EventLogRepository(Protocol):
    def append_event(self, event: ResearchEvent) -> None:
        """Persist a research/trading event entry."""

    def load_events(self, limit: int | None = None) -> list[ResearchEvent]:
        """Load recent or full event history."""


class TradeMemoryRepository(Protocol):
    def save_trade_memory(self, record: TradeMemoryRecord) -> None:
        """Persist a trade memory record, updating existing entries by id."""

    def load_trade_memory(self, limit: int | None = None) -> list[TradeMemoryRecord]:
        """Load recent or full trade memory history."""

    def load_open_trade_memory(self, symbol: str) -> TradeMemoryRecord | None:
        """Load the latest open trade memory record for a symbol if one exists."""


class ActiveStrategyRepository(Protocol):
    def save_active_strategy(self, symbol: str, genome: StrategyGenome) -> None:
        """Persist the strategy currently governing an open paper position."""

    def load_active_strategy(self, symbol: str) -> StrategyGenome | None:
        """Load the persisted strategy for a symbol if one exists."""

    def delete_active_strategy(self, symbol: str) -> None:
        """Delete the persisted strategy for a symbol."""


class StrategyRegistryRepository(Protocol):
    def save_strategy_registry(self, symbol: str, entries: list[StrategyRegistryEntry]) -> None:
        """Persist the current registry of strategies for a symbol."""

    def load_strategy_registry(self, symbol: str) -> list[StrategyRegistryEntry]:
        """Load the persisted registry of strategies for a symbol."""


class RuntimeStatusRepository(Protocol):
    def save_runtime_status(self, status: RuntimeComponentStatus) -> None:
        """Persist the latest heartbeat and lifecycle state for one worker component."""

    def load_runtime_statuses(self) -> list[RuntimeComponentStatus]:
        """Load worker lifecycle states written by this runtime's processes."""


class ResearchJobRepository(Protocol):
    def create_job(self, job: ResearchJob) -> None:
        """Durably append a queued research job."""

    def list_jobs(self, limit: int | None = None) -> list[ResearchJob]:
        """Return jobs ordered by creation time."""

    def get_job(self, job_id: str) -> ResearchJob | None:
        """Load a single job by its stable identifier."""

    def update_job(self, job: ResearchJob) -> None:
        """Replace a job state after a validated lifecycle transition."""

    def claim_next_job(self, worker_id: str) -> ResearchJob | None:
        """Atomically claim one queued local job, if one exists."""


class ResearchStorage(
    CandleRepository,
    FeatureRepository,
    PortfolioRepository,
    PortfolioHistoryRepository,
    TradeRepository,
    ReportRepository,
    EventLogRepository,
    TradeMemoryRepository,
    ActiveStrategyRepository,
    StrategyRegistryRepository,
    RuntimeStatusRepository,
    ResearchJobRepository,
    Protocol,
):
    backend_name: str

    def close(self) -> None:
        """Release any resources held by the storage backend."""
