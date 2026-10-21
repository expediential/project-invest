from __future__ import annotations

from project_invest.domain.models import PortfolioSnapshot, RiskDecision, RiskLimits, StrategyGenome


class RiskManager:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate_entry(
        self,
        symbol: str,
        portfolio: PortfolioSnapshot,
        price: float,
        desired_quantity: int,
        genome: StrategyGenome,
    ) -> RiskDecision:
        if desired_quantity <= 0:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Desired quantity is zero.")

        if symbol in portfolio.positions:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Position already exists for the symbol.")

        if len(portfolio.positions) >= self.limits.max_positions:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Max positions limit reached.")

        max_loss_allowed = portfolio.starting_capital * self.limits.max_daily_loss
        if portfolio.daily_pnl is not None and portfolio.daily_pnl <= -max_loss_allowed:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Daily loss limit breached.")

        drawdown_limit = portfolio.starting_capital * (1 - self.limits.max_drawdown)
        if portfolio.total_equity <= drawdown_limit:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Max drawdown limit breached.")

        risk_budget = portfolio.total_equity * self.limits.max_risk_per_trade
        per_share_risk = price * max(genome.stop_loss_pct, 0.005)
        quantity_by_risk = int(risk_budget / per_share_risk) if per_share_risk > 0 else desired_quantity

        exposure_cap = portfolio.total_equity * self.limits.max_gross_exposure
        remaining_exposure = max(0.0, exposure_cap - portfolio.open_exposure)
        quantity_by_exposure = int(remaining_exposure / price) if price > 0 else 0

        position_cap = portfolio.total_equity * self.limits.max_position_pct
        quantity_by_position = int(position_cap / price) if price > 0 else 0

        allowed_quantity = min(desired_quantity, quantity_by_risk, quantity_by_exposure, quantity_by_position)
        if allowed_quantity <= 0:
            return RiskDecision(approved=False, allowed_quantity=0, reason="Risk rules allow no additional exposure.")

        if allowed_quantity < desired_quantity:
            return RiskDecision(
                approved=True,
                allowed_quantity=allowed_quantity,
                reason="Order size reduced by risk controls.",
            )

        return RiskDecision(approved=True, allowed_quantity=allowed_quantity, reason="Approved.")
