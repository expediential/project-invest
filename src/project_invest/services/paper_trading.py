from __future__ import annotations

from project_invest.domain.models import (
    ExecutionMode,
    ExecutionOrder,
    OrderStatus,
    PortfolioSnapshot,
    Position,
    SignalAction,
    StrategyGenome,
    TradeSignal,
    utc_now,
)
from project_invest.services.risk import RiskManager
from project_invest.storage.repositories import PortfolioRepository, TradeRepository


class PaperBroker:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        trade_repository: TradeRepository,
        risk_manager: RiskManager,
        starting_capital: float,
        slippage_bps: float,
        fee_bps: float,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.trade_repository = trade_repository
        self.risk_manager = risk_manager
        self.starting_capital = starting_capital
        self.slippage_multiplier = slippage_bps / 10_000
        self.fee_multiplier = fee_bps / 10_000

    def get_portfolio(self, market_prices: dict[str, float] | None = None) -> PortfolioSnapshot:
        portfolio = self.portfolio_repository.load_portfolio() or PortfolioSnapshot.bootstrap(self.starting_capital)
        if not market_prices:
            return portfolio
        return self.refresh_portfolio(portfolio, market_prices)

    def refresh_portfolio(self, portfolio: PortfolioSnapshot, market_prices: dict[str, float]) -> PortfolioSnapshot:
        positions: dict[str, Position] = {}
        open_exposure = 0.0
        marked_at = utc_now()

        for symbol, position in portfolio.positions.items():
            has_fresh_price = symbol in market_prices
            last_price = market_prices.get(symbol, position.last_price)
            updated = position.model_copy(
                update={
                    "last_price": last_price,
                    "last_price_at": marked_at if has_fresh_price else position.last_price_at,
                }
            )
            positions[symbol] = updated
            open_exposure += updated.quantity * updated.last_price

        total_equity = portfolio.cash + open_exposure
        daily_pnl = self._daily_pnl(total_equity, marked_at)
        return portfolio.model_copy(
            update={
                "as_of": marked_at,
                "positions": positions,
                "open_exposure": round(open_exposure, 4),
                "total_equity": round(total_equity, 4),
                "daily_pnl": daily_pnl,
            }
        )

    def _daily_pnl(self, total_equity: float, marked_at) -> float | None:
        history_loader = getattr(self.portfolio_repository, "load_portfolio_history", None)
        if not callable(history_loader):
            return None
        snapshots = history_loader()
        day_start = next(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.as_of.date() == marked_at.date()
            ),
            None,
        )
        if day_start is None:
            return None
        return round(total_equity - day_start.total_equity, 4)

    def execute_signal(self, signal: TradeSignal, market_price: float, genome: StrategyGenome) -> ExecutionOrder:
        portfolio = self.portfolio_repository.load_portfolio()
        if portfolio is None:
            portfolio = PortfolioSnapshot.bootstrap(self.starting_capital)
            # Capture a real baseline only when an execution is requested, never from a read route.
            self.portfolio_repository.save_portfolio(portfolio)
        portfolio = self.refresh_portfolio(portfolio, {signal.symbol: market_price})

        if signal.action == SignalAction.HOLD:
            return ExecutionOrder(
                mode=ExecutionMode.PAPER,
                symbol=signal.symbol,
                action=signal.action,
                status=OrderStatus.SKIPPED,
                quantity=0,
                requested_price=market_price,
                fill_price=market_price,
                fee_paid=0.0,
                note=signal.reason,
                strategy_id=signal.strategy_id,
            )

        if signal.action == SignalAction.BUY:
            return self._execute_buy(signal, market_price, genome, portfolio)

        return self._execute_sell(signal, market_price, portfolio)

    def _execute_buy(
        self,
        signal: TradeSignal,
        market_price: float,
        genome: StrategyGenome,
        portfolio: PortfolioSnapshot,
    ) -> ExecutionOrder:
        desired_quantity = int((portfolio.cash * max(genome.risk_fraction, 0.02) * max(signal.confidence, 0.25)) / market_price)
        decision = self.risk_manager.evaluate_entry(signal.symbol, portfolio, market_price, desired_quantity, genome)
        quantity = decision.allowed_quantity
        if not decision.approved or quantity <= 0:
            return ExecutionOrder(
                mode=ExecutionMode.PAPER,
                symbol=signal.symbol,
                action=signal.action,
                status=OrderStatus.REJECTED,
                quantity=0,
                requested_price=market_price,
                fill_price=market_price,
                fee_paid=0.0,
                note=decision.reason,
                strategy_id=signal.strategy_id,
            )

        fill_price = market_price * (1 + self.slippage_multiplier)
        fee = fill_price * quantity * self.fee_multiplier
        total_cost = (fill_price * quantity) + fee
        while quantity > 0 and total_cost > portfolio.cash:
            quantity -= 1
            fee = fill_price * quantity * self.fee_multiplier
            total_cost = (fill_price * quantity) + fee

        if quantity <= 0:
            return ExecutionOrder(
                mode=ExecutionMode.PAPER,
                symbol=signal.symbol,
                action=signal.action,
                status=OrderStatus.REJECTED,
                quantity=0,
                requested_price=market_price,
                fill_price=market_price,
                fee_paid=0.0,
                note="Not enough cash after fees and slippage.",
                strategy_id=signal.strategy_id,
            )

        positions = dict(portfolio.positions)
        positions[signal.symbol] = Position(
            symbol=signal.symbol,
            quantity=quantity,
            average_price=round(fill_price, 4),
            opened_at=utc_now(),
            last_price=market_price,
            strategy_id=signal.strategy_id,
            entry_fee_paid=round(fee, 4),
            last_price_at=utc_now(),
        )

        updated_portfolio = portfolio.model_copy(
            update={
                "as_of": utc_now(),
                "cash": round(portfolio.cash - total_cost, 4),
                "positions": positions,
            }
        )
        refreshed = self.refresh_portfolio(updated_portfolio, {signal.symbol: market_price})
        self.portfolio_repository.save_portfolio(refreshed)

        order = ExecutionOrder(
            mode=ExecutionMode.PAPER,
            symbol=signal.symbol,
            action=signal.action,
            status=OrderStatus.FILLED,
            quantity=quantity,
            requested_price=market_price,
            fill_price=round(fill_price, 4),
            fee_paid=round(fee, 4),
            realized_pnl=0.0,
            note=decision.reason,
            strategy_id=signal.strategy_id,
        )
        self.trade_repository.append_trade(order)
        return order

    def _execute_sell(
        self,
        signal: TradeSignal,
        market_price: float,
        portfolio: PortfolioSnapshot,
    ) -> ExecutionOrder:
        existing = portfolio.positions.get(signal.symbol)
        if existing is None:
            return ExecutionOrder(
                mode=ExecutionMode.PAPER,
                symbol=signal.symbol,
                action=signal.action,
                status=OrderStatus.SKIPPED,
                quantity=0,
                requested_price=market_price,
                fill_price=market_price,
                fee_paid=0.0,
                note="No open position to close.",
                strategy_id=signal.strategy_id,
            )

        fill_price = market_price * (1 - self.slippage_multiplier)
        fee = fill_price * existing.quantity * self.fee_multiplier
        proceeds = (fill_price * existing.quantity) - fee
        pnl = ((fill_price - existing.average_price) * existing.quantity) - fee - existing.entry_fee_paid

        positions = dict(portfolio.positions)
        del positions[signal.symbol]

        updated_portfolio = portfolio.model_copy(
            update={
                "as_of": utc_now(),
                "cash": round(portfolio.cash + proceeds, 4),
                "realized_pnl": round(portfolio.realized_pnl + pnl, 4),
                "positions": positions,
            }
        )
        refreshed = self.refresh_portfolio(updated_portfolio, {})
        self.portfolio_repository.save_portfolio(refreshed)

        order = ExecutionOrder(
            mode=ExecutionMode.PAPER,
            symbol=signal.symbol,
            action=signal.action,
            status=OrderStatus.FILLED,
            quantity=existing.quantity,
            requested_price=market_price,
            fill_price=round(fill_price, 4),
            fee_paid=round(fee, 4),
            realized_pnl=round(pnl, 4),
            note="Position closed.",
            strategy_id=signal.strategy_id,
        )
        self.trade_repository.append_trade(order)
        return order
