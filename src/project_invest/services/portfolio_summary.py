from __future__ import annotations

from project_invest.domain.models import PortfolioHistorySnapshot, PortfolioSnapshot


class PortfolioSummaryService:
    """Build one read-only accounting view for API and dashboard consumers."""

    def build(
        self,
        portfolio: PortfolioSnapshot | None,
        history: list[PortfolioHistorySnapshot],
        starting_capital: float,
    ) -> dict[str, object]:
        if portfolio is None:
            return {
                "state": "empty",
                "paper_trading": True,
                "message": "No persisted paper portfolio exists yet. A portfolio baseline is created on the first paper execution.",
                "starting_capital": starting_capital,
                "history_available": False,
                "history_points": 0,
                "positions": [],
            }

        market_value = round(sum(position.quantity * position.last_price for position in portfolio.positions.values()), 4)
        unrealized_pnl = round(
            sum(
                ((position.last_price - position.average_price) * position.quantity) - position.entry_fee_paid
                for position in portfolio.positions.values()
            ),
            4,
        )
        total_pnl = round(portfolio.total_equity - portfolio.starting_capital, 4)
        reconciled_pnl = round(portfolio.realized_pnl + unrealized_pnl, 4)
        reconciliation_delta = round(total_pnl - reconciled_pnl, 4)
        positions = [
            self._position_summary(symbol, position, portfolio.total_equity)
            for symbol, position in sorted(portfolio.positions.items())
        ]
        current_drawdown, max_drawdown = self._drawdowns(history, portfolio)
        total_return_pct = round((total_pnl / portfolio.starting_capital) * 100, 4) if portfolio.starting_capital else None
        gross_exposure_pct = round((market_value / portfolio.total_equity) * 100, 4) if portfolio.total_equity else None

        return {
            "state": "ready",
            "paper_trading": True,
            "as_of": portfolio.as_of,
            "starting_capital": portfolio.starting_capital,
            "equity": portfolio.total_equity,
            "cash": portfolio.cash,
            "invested_market_value": market_value,
            "realized_pnl": portfolio.realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "daily_pnl": portfolio.daily_pnl,
            "daily_pnl_available": portfolio.daily_pnl is not None,
            "current_drawdown_pct": current_drawdown,
            "max_observed_drawdown_pct": max_drawdown,
            "open_positions": len(positions),
            "gross_exposure": market_value,
            "gross_exposure_pct": gross_exposure_pct,
            "net_exposure": market_value,
            "net_exposure_note": "Long-only paper portfolio; net exposure equals invested market value.",
            "pnl_reconciliation_delta": reconciliation_delta,
            "history_available": bool(history),
            "history_points": len(history),
            "positions": positions,
        }

    def _position_summary(self, symbol: str, position, total_equity: float) -> dict[str, object]:
        market_value = round(position.quantity * position.last_price, 4)
        cost_basis = round((position.quantity * position.average_price) + position.entry_fee_paid, 4)
        unrealized_pnl = round(market_value - cost_basis, 4)
        return_pct = round((unrealized_pnl / cost_basis) * 100, 4) if cost_basis else None
        weight_pct = round((market_value / total_equity) * 100, 4) if total_equity else None
        return {
            "symbol": symbol,
            "quantity": position.quantity,
            "average_entry_price": position.average_price,
            "entry_fee_paid": position.entry_fee_paid,
            "last_price": position.last_price,
            "last_price_at": position.last_price_at,
            "price_status": "marked" if position.last_price_at is not None else "timestamp_unavailable",
            "market_value": market_value,
            "cost_basis": cost_basis,
            "unrealized_pnl": unrealized_pnl,
            "return_pct": return_pct,
            "weight_pct": weight_pct,
            "opened_at": position.opened_at,
            "strategy_id": position.strategy_id,
            "status": "open",
        }

    def _drawdowns(
        self,
        history: list[PortfolioHistorySnapshot],
        portfolio: PortfolioSnapshot,
    ) -> tuple[float, float]:
        equities = [snapshot.total_equity for snapshot in history]
        if not equities or equities[-1] != portfolio.total_equity:
            equities.append(portfolio.total_equity)
        peak = portfolio.starting_capital
        maximum = 0.0
        current = 0.0
        for equity in equities:
            peak = max(peak, equity)
            drawdown = ((equity - peak) / peak) * 100 if peak else 0.0
            maximum = min(maximum, drawdown)
            current = drawdown
        return round(current, 4), round(maximum, 4)
