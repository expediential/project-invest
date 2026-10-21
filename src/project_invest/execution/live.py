from __future__ import annotations

from typing import Protocol

from project_invest.domain.models import (
    ExecutionMode,
    ExecutionOrder,
    OrderStatus,
    PortfolioSnapshot,
    StrategyGenome,
    TradeSignal,
)
from project_invest.execution.base import ExecutionEngine


class BrokerAdapter(Protocol):
    def place_order(self, signal: TradeSignal, market_price: float, genome: StrategyGenome) -> ExecutionOrder:
        """Send an order to a real broker."""

    def get_portfolio(self) -> PortfolioSnapshot:
        """Read the real broker portfolio."""


class LiveExecutionEngine(ExecutionEngine):
    mode = ExecutionMode.LIVE

    def __init__(self, adapter: BrokerAdapter | None, fallback_portfolio: PortfolioSnapshot) -> None:
        self.adapter = adapter
        self.fallback_portfolio = fallback_portfolio

    def execute(self, signal: TradeSignal, market_price: float, genome: StrategyGenome) -> ExecutionOrder:
        return ExecutionOrder(
            mode=ExecutionMode.LIVE,
            symbol=signal.symbol,
            action=signal.action,
            status=OrderStatus.REJECTED,
            quantity=0,
            requested_price=market_price,
            fill_price=market_price,
            fee_paid=0.0,
            note="Live execution is disabled in this release.",
            strategy_id=signal.strategy_id,
        )

    def get_portfolio(self, market_prices: dict[str, float] | None = None) -> PortfolioSnapshot:
        if self.adapter is None:
            return self.fallback_portfolio
        return self.adapter.get_portfolio()

