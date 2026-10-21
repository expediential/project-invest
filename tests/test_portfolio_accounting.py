from __future__ import annotations

from project_invest.domain.models import SignalAction, StrategyGenome, TradeSignal
from project_invest.services.paper_trading import PaperBroker
from project_invest.services.portfolio_summary import PortfolioSummaryService
from project_invest.services.risk import RiskManager
from project_invest.domain.models import RiskLimits
from project_invest.storage.data_lake import LocalDataLake


def _broker(tmp_path) -> tuple[PaperBroker, LocalDataLake]:
    storage = LocalDataLake(tmp_path / "lake")
    risk = RiskManager(
        RiskLimits(
            max_risk_per_trade=1.0,
            max_daily_loss=0.5,
            max_positions=5,
            max_gross_exposure=1.0,
            max_position_pct=1.0,
            max_drawdown=0.9,
        )
    )
    return (
        PaperBroker(
            portfolio_repository=storage,
            trade_repository=storage,
            risk_manager=risk,
            starting_capital=1_000.0,
            slippage_bps=0.0,
            fee_bps=100.0,
        ),
        storage,
    )


def test_paper_portfolio_includes_entry_and_exit_fees_in_pnl(tmp_path) -> None:
    broker, storage = _broker(tmp_path)
    genome = StrategyGenome(strategy_id="fee-aware", risk_fraction=0.2, stop_loss_pct=0.02)
    buy = broker.execute_signal(
        TradeSignal(symbol="FEE", action=SignalAction.BUY, confidence=1.0, reason="enter", strategy_id=genome.strategy_id),
        market_price=100.0,
        genome=genome,
    )

    after_buy = storage.load_portfolio()
    assert after_buy is not None
    assert after_buy.total_equity == 998.0
    assert after_buy.daily_pnl == -2.0
    assert after_buy.positions["FEE"].entry_fee_paid == 2.0

    sell = broker.execute_signal(
        TradeSignal(symbol="FEE", action=SignalAction.SELL, confidence=1.0, reason="exit", strategy_id=genome.strategy_id),
        market_price=110.0,
        genome=genome,
    )

    portfolio = storage.load_portfolio()
    assert portfolio is not None
    assert buy.quantity == 2
    assert sell.realized_pnl == 15.8
    assert portfolio.total_equity == 1_015.8
    assert portfolio.realized_pnl == 15.8


def test_portfolio_read_is_non_mutating_and_history_is_persisted(tmp_path) -> None:
    broker, storage = _broker(tmp_path)
    genome = StrategyGenome(strategy_id="read-only", risk_fraction=0.2, stop_loss_pct=0.02)
    broker.execute_signal(
        TradeSignal(symbol="READ", action=SignalAction.BUY, confidence=1.0, reason="enter", strategy_id=genome.strategy_id),
        market_price=100.0,
        genome=genome,
    )

    before = storage.load_portfolio()
    before_history = storage.load_portfolio_history()
    assert before is not None

    returned = broker.get_portfolio()

    assert returned == before
    assert storage.load_portfolio() == before
    assert storage.load_portfolio_history() == before_history
    assert len(before_history) == 2


def test_portfolio_summary_reconciles_accounting_and_position_values(tmp_path) -> None:
    broker, storage = _broker(tmp_path)
    genome = StrategyGenome(strategy_id="summary", risk_fraction=0.2, stop_loss_pct=0.02)
    broker.execute_signal(
        TradeSignal(symbol="SUMMARY", action=SignalAction.BUY, confidence=1.0, reason="enter", strategy_id=genome.strategy_id),
        market_price=100.0,
        genome=genome,
    )
    portfolio = broker.get_portfolio({"SUMMARY": 105.0})
    storage.save_portfolio(portfolio)

    summary = PortfolioSummaryService().build(
        storage.load_portfolio(), storage.load_portfolio_history(), starting_capital=1_000.0
    )

    assert summary["total_pnl"] == 8.0
    assert summary["unrealized_pnl"] == 8.0
    assert summary["pnl_reconciliation_delta"] == 0.0
    assert summary["history_available"] is True
    assert summary["positions"][0]["market_value"] == 210.0


def test_local_trade_history_is_idempotent_by_trade_id(tmp_path) -> None:
    broker, storage = _broker(tmp_path)
    genome = StrategyGenome(strategy_id="dedupe", risk_fraction=0.2, stop_loss_pct=0.02)
    order = broker.execute_signal(
        TradeSignal(symbol="DEDUPE", action=SignalAction.BUY, confidence=1.0, reason="enter", strategy_id=genome.strategy_id),
        market_price=100.0,
        genome=genome,
    )

    storage.append_trade(order)

    assert [trade.trade_id for trade in storage.load_trades()] == [order.trade_id]
