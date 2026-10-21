from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from project_invest.api.terminal_dashboard import render_dashboard
from project_invest.api.schemas import ResearchRunRequest
from project_invest.config import settings
from project_invest.container import ServiceContainer, build_container
from project_invest.services.universe import (
    default_crypto_universe,
    default_forex_universe,
    default_nasdaq_universe,
    default_nse_universe,
    default_nyse_universe,
    resolve_symbol_groups,
    resolve_symbols,
    symbol_market_map,
)
from project_invest.services.worker import (
    BackgroundResearchWorker,
    BackgroundTradingWorker,
)
from project_invest.services.portfolio_summary import PortfolioSummaryService


def _embedded_loops_enabled(container: ServiceContainer) -> bool:
    return any(
        [
            container.settings.research_loop_enabled,
            container.settings.trading_loop_enabled,
            container.settings.live_loop_enabled,
        ]
    )


async def _boot_embedded_workers(
    app: FastAPI,
    container: ServiceContainer,
    resolved_symbols: list[str],
) -> None:
    # Defer heavy loop startup until after the API lifecycle is fully online.
    await asyncio.sleep(0.05)
    loop_lock = asyncio.Lock()
    app.state.worker_boot_status = "starting"
    app.state.worker_startup_error = None
    app.state.loop_lock = loop_lock

    try:
        if container.settings.research_loop_enabled:
            research_worker = BackgroundResearchWorker(
                research_lab=container.research_lab,
                interval_seconds=container.settings.research_loop_seconds,
                symbols=resolved_symbols,
                execute_trades=False,
                run_lock=loop_lock,
            )
            await research_worker.start()
            app.state.research_worker = research_worker

        if container.settings.trading_loop_enabled:
            trading_worker = BackgroundTradingWorker(
                trading_lab=container.trading_lab,
                interval_seconds=container.settings.trading_loop_seconds,
                symbols=resolved_symbols,
                run_lock=loop_lock,
            )
            await trading_worker.start()
            app.state.trading_worker = trading_worker

        if container.settings.live_loop_enabled and not (
            container.settings.research_loop_enabled or container.settings.trading_loop_enabled
        ):
            legacy_worker = BackgroundResearchWorker(
                research_lab=container.research_lab,
                interval_seconds=container.settings.live_loop_seconds,
                symbols=resolved_symbols,
                execute_trades=True,
            )
            await legacy_worker.start()
            app.state.legacy_worker = legacy_worker

        app.state.worker_boot_status = "running"
    except Exception as exc:
        app.state.worker_boot_status = "error"
        app.state.worker_startup_error = str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container(settings)
    app.state.container = container
    app.state.legacy_worker = None
    app.state.research_worker = None
    app.state.trading_worker = None
    app.state.worker_boot_task = None
    app.state.worker_boot_status = "idle"
    app.state.worker_startup_error = None
    resolved_symbols = resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    resolved_groups = resolve_symbol_groups(
        resolved_symbols,
        container.settings.symbol_groups,
        container.settings.symbol_group_size,
    )
    app.state.resolved_symbols = resolved_symbols
    app.state.resolved_groups = resolved_groups

    if _embedded_loops_enabled(container):
        app.state.worker_boot_status = "scheduled"
        app.state.worker_boot_task = asyncio.create_task(
            _boot_embedded_workers(app, container, resolved_symbols)
        )

    yield

    worker_boot_task = getattr(app.state, "worker_boot_task", None)
    if worker_boot_task is not None:
        worker_boot_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_boot_task

    legacy_worker = getattr(app.state, "legacy_worker", None)
    research_worker = getattr(app.state, "research_worker", None)
    trading_worker = getattr(app.state, "trading_worker", None)
    if legacy_worker is not None:
        await legacy_worker.stop()
    if research_worker is not None:
        await research_worker.stop()
    if trading_worker is not None:
        await trading_worker.stop()
    container.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

_LOCAL_AUTH_COOKIE = "project_invest_local_auth"


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def _is_loopback_request(request: Request) -> bool:
    client_host = request.client.host if request.client is not None else ""
    return client_host.lower() in {"127.0.0.1", "::1", "localhost", "testclient"}


def _auto_local_dashboard_auth_enabled(request: Request) -> bool:
    return (
        os.getenv("PROJECT_INVEST_AUTO_LOCAL_DASHBOARD_AUTH", "").strip().lower() == "true"
        and _is_loopback_request(request)
    )


def require_operational_access(request: Request) -> None:
    """Fail closed unless an explicitly configured bearer token authorizes an operation."""
    configured_token = get_container(request).settings.api_auth_token
    if configured_token is None:
        raise HTTPException(status_code=503, detail="Operational API controls are disabled.")

    authorization = request.headers.get("Authorization", "")
    scheme, _, supplied_token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        supplied_token = ""
    if not supplied_token and _auto_local_dashboard_auth_enabled(request):
        supplied_token = request.cookies.get(_LOCAL_AUTH_COOKIE, "")
    if not supplied_token:
        raise HTTPException(status_code=401, detail="Bearer authentication is required.")
    if not secrets.compare_digest(configured_token.get_secret_value(), supplied_token):
        raise HTTPException(status_code=403, detail="Invalid operational credentials.")


def _build_launch_hint(
    embedded_loops_enabled: bool,
    worker_running: bool,
) -> str:
    if embedded_loops_enabled:
        return "API owns the research and trading loops in this run mode."
    if worker_running:
        return "Standalone workers are running outside the API process."
    return (
        "API-only mode. Automatic research and trading loops are not running here. "
        "Use run-project-invest.cmd or python -m project_invest launch --host 0.0.0.0 --port 8000 "
        "for the full local stack."
    )


def resolve_interval(request: Request, requested_interval: str | None) -> str:
    if requested_interval:
        return requested_interval
    container = get_container(request)
    latest_report = container.storage.load_latest_report(stream="trading") or container.storage.load_latest_report(
        stream="research"
    )
    if latest_report is not None and latest_report.interval:
        return latest_report.interval
    return container.settings.trading_interval or container.settings.research_interval


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    container = get_container(request)
    auto_local_auth = _auto_local_dashboard_auth_enabled(request) and container.settings.api_auth_token is not None
    response = HTMLResponse(render_dashboard(container.settings.app_name, auto_local_auth=auto_local_auth))
    if auto_local_auth:
        response.set_cookie(
            key=_LOCAL_AUTH_COOKIE,
            value=container.settings.api_auth_token.get_secret_value(),
            httponly=True,
            samesite="strict",
            path="/api",
        )
    return response


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    container = get_container(request)
    legacy_worker = getattr(request.app.state, "legacy_worker", None)
    research_worker = getattr(request.app.state, "research_worker", None)
    trading_worker = getattr(request.app.state, "trading_worker", None)
    latest_research_report = container.storage.load_latest_report(stream="research")
    latest_trading_report = container.storage.load_latest_report(stream="trading")
    resolved_symbols = getattr(request.app.state, "resolved_symbols", None) or resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    resolved_groups = getattr(request.app.state, "resolved_groups", None) or resolve_symbol_groups(
        resolved_symbols,
        container.settings.symbol_groups,
        container.settings.symbol_group_size,
    )
    worker_last_error = None
    startup_error = getattr(request.app.state, "worker_startup_error", None)
    if startup_error:
        worker_last_error = startup_error
    for candidate in (legacy_worker, research_worker, trading_worker):
        last_error = getattr(candidate, "last_error", None)
        if last_error:
            worker_last_error = last_error
            break
    worker_running = any([legacy_worker, research_worker, trading_worker])
    embedded_loops_enabled = _embedded_loops_enabled(container)
    return {
        "status": "ok",
        "execution_mode": container.settings.execution_mode,
        "base_currency": container.settings.base_currency,
        "market_data_provider": container.settings.market_data_provider,
        "allow_mock_fallback": container.settings.allow_mock_fallback,
        "latest_report_provider": latest_research_report.provider if latest_research_report is not None else None,
        "latest_research_report_provider": latest_research_report.provider if latest_research_report is not None else None,
        "latest_trading_report_provider": latest_trading_report.provider if latest_trading_report is not None else None,
        "storage_backend": container.storage.backend_name,
        "research_symbols": resolved_symbols,
        "configured_symbols": container.settings.research_symbols,
        "symbol_groups": resolved_groups,
        "symbol_group_size": container.settings.symbol_group_size,
        "symbol_markets": symbol_market_map(resolved_symbols),
        "use_market_universes": container.settings.use_market_universes,
        "market_universes": container.settings.market_universes,
        "execution_markets": container.settings.execution_markets,
        "interval": container.settings.research_interval,
        "trading_interval": container.settings.trading_interval,
        "confirmation_intervals": container.settings.confirmation_intervals,
        "confirmation_short_window": container.settings.confirmation_short_window,
        "confirmation_long_window": container.settings.confirmation_long_window,
        "confirmation_min_trend_strength": container.settings.confirmation_min_trend_strength,
        "legacy_worker_running": legacy_worker is not None,
        "research_worker_running": research_worker is not None,
        "trading_worker_running": trading_worker is not None,
        "embedded_loops_enabled": embedded_loops_enabled,
        "worker_launch_mode": (
            "embedded"
            if embedded_loops_enabled
            else "standalone"
        ),
        "launch_hint": _build_launch_hint(embedded_loops_enabled, worker_running),
        "embedded_worker_boot_status": getattr(request.app.state, "worker_boot_status", "idle"),
        "worker_running": worker_running,
        "worker_last_error": worker_last_error,
    }


@app.get("/api/config")
async def config_snapshot(request: Request) -> dict[str, object]:
    container = get_container(request)
    resolved_symbols = getattr(request.app.state, "resolved_symbols", None) or resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    resolved_groups = getattr(request.app.state, "resolved_groups", None) or resolve_symbol_groups(
        resolved_symbols,
        container.settings.symbol_groups,
        container.settings.symbol_group_size,
    )
    return {
        "execution_mode": container.settings.execution_mode,
        "base_currency": container.settings.base_currency,
        "market_data_provider": container.settings.market_data_provider,
        "allow_mock_fallback": container.settings.allow_mock_fallback,
        "storage_backend": container.settings.storage_backend,
        "storage_cache_enabled": container.settings.storage_cache_enabled,
        "postgres_schema": container.settings.postgres_schema,
        "sentiment_provider": container.settings.sentiment_provider,
        "sentiment_data_root": str(container.settings.sentiment_data_root),
        "sentiment_min_intensity": container.settings.sentiment_min_intensity,
        "sentiment_confidence_boost": container.settings.sentiment_confidence_boost,
        "sentiment_confidence_penalty": container.settings.sentiment_confidence_penalty,
        "sentiment_reversal_block_threshold": container.settings.sentiment_reversal_block_threshold,
        "sentiment_memory_enabled": container.settings.sentiment_memory_enabled,
        "sentiment_memory_lookback": container.settings.sentiment_memory_lookback,
        "sentiment_memory_min_records": container.settings.sentiment_memory_min_records,
        "starting_capital": container.settings.starting_capital,
        "max_risk_per_trade": container.settings.max_risk_per_trade,
        "live_max_risk_per_trade": container.settings.live_max_risk_per_trade,
        "population_size": container.settings.population_size,
        "generations": container.settings.generations,
        "min_validation_sharpe": container.settings.min_validation_sharpe,
        "min_validation_return": container.settings.min_validation_return,
        "max_validation_drawdown": container.settings.max_validation_drawdown,
        "min_validation_trades": container.settings.min_validation_trades,
        "min_validation_profit_factor": container.settings.min_validation_profit_factor,
        "min_validation_win_rate": container.settings.min_validation_win_rate,
        "min_validation_trade_coverage": container.settings.min_validation_trade_coverage,
        "max_validation_return_gap": container.settings.max_validation_return_gap,
        "max_validation_sharpe_gap": container.settings.max_validation_sharpe_gap,
        "research_interval": container.settings.research_interval,
        "trading_interval": container.settings.trading_interval,
        "trading_lookback_bars": container.settings.trading_lookback_bars,
        "research_loop_enabled": container.settings.research_loop_enabled,
        "research_loop_seconds": container.settings.research_loop_seconds,
        "trading_loop_enabled": container.settings.trading_loop_enabled,
        "trading_loop_seconds": container.settings.trading_loop_seconds,
        "live_loop_enabled": container.settings.live_loop_enabled,
        "live_loop_seconds": container.settings.live_loop_seconds,
        "symbol_groups": resolved_groups,
        "symbol_group_size": container.settings.symbol_group_size,
        "use_market_universes": container.settings.use_market_universes,
        "market_universes": container.settings.market_universes,
        "execution_markets": container.settings.execution_markets,
        "research_symbols": resolved_symbols,
        "confirmation_intervals": container.settings.confirmation_intervals,
        "confirmation_lookback_bars": container.settings.confirmation_lookback_bars,
        "confirmation_short_window": container.settings.confirmation_short_window,
        "confirmation_long_window": container.settings.confirmation_long_window,
        "confirmation_min_trend_strength": container.settings.confirmation_min_trend_strength,
    }


@app.get("/api/universe")
async def universe(request: Request) -> dict[str, object]:
    container = get_container(request)
    resolved_symbols = getattr(request.app.state, "resolved_symbols", None) or resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    return {
        "resolved": resolved_symbols,
        "symbol_markets": symbol_market_map(resolved_symbols),
        "markets": container.settings.market_universes,
        "use_market_universes": container.settings.use_market_universes,
        "available": {
            "NSE": default_nse_universe(),
            "NASDAQ": default_nasdaq_universe(),
            "NYSE": default_nyse_universe(),
            "CRYPTO": default_crypto_universe(),
            "FOREX": default_forex_universe(),
        },
    }


@app.post("/api/research/run")
async def run_research(request: Request, payload: ResearchRunRequest | None = None):
    require_operational_access(request)
    container = get_container(request)
    symbols = payload.symbols if payload and payload.symbols else None
    try:
        return await container.research_lab.run_cycle(symbols, execute_trades=False)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research cycle failed: {exc}") from exc


@app.post("/api/trading/run")
async def run_trading(request: Request, payload: ResearchRunRequest | None = None):
    require_operational_access(request)
    container = get_container(request)
    symbols = payload.symbols if payload and payload.symbols else None
    try:
        return await container.trading_lab.run_cycle(symbols)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Trading cycle failed: {exc}") from exc


@app.get("/api/research/latest")
async def latest_report(request: Request):
    container = get_container(request)
    report = container.storage.load_latest_report(stream="research")
    if report is None:
        raise HTTPException(status_code=404, detail="No research report available yet.")
    return report


@app.get("/api/trading/latest")
async def latest_trading_report(request: Request):
    container = get_container(request)
    report = container.storage.load_latest_report(stream="trading")
    if report is None:
        raise HTTPException(status_code=404, detail="No trading report available yet.")
    return report


@app.get("/api/portfolio")
async def portfolio(request: Request):
    container = get_container(request)
    return container.execution_engine.get_portfolio()


@app.get("/api/portfolio/summary")
async def portfolio_summary(request: Request) -> dict[str, object]:
    container = get_container(request)
    return PortfolioSummaryService().build(
        portfolio=container.storage.load_portfolio(),
        history=container.storage.load_portfolio_history(),
        starting_capital=container.settings.starting_capital,
        base_currency=container.settings.base_currency,
    )


@app.get("/api/portfolio/history")
async def portfolio_history(request: Request, limit: int = Query(default=2_000, ge=1, le=10_000)):
    return get_container(request).storage.load_portfolio_history(limit=limit)


@app.get("/api/positions")
async def positions(request: Request) -> list[dict[str, object]]:
    container = get_container(request)
    summary = PortfolioSummaryService().build(
        portfolio=container.storage.load_portfolio(),
        history=container.storage.load_portfolio_history(),
        starting_capital=container.settings.starting_capital,
        base_currency=container.settings.base_currency,
    )
    return summary["positions"]


@app.get("/api/data-quality")
async def data_quality(request: Request) -> dict[str, object]:
    container = get_container(request)
    resolved_symbols = getattr(request.app.state, "resolved_symbols", None) or resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    interval = container.settings.trading_interval
    records = []
    for symbol in resolved_symbols:
        candles = container.storage.load_candles(symbol, interval, stage="processed")
        latest = candles[-1] if candles else None
        records.append(
            {
                "symbol": symbol,
                "interval": interval,
                "status": "available" if latest is not None else "unavailable",
                "latest_timestamp": latest.timestamp if latest is not None else None,
                "data_source": latest.data_source if latest is not None else None,
                "stored_bars": len(candles),
            }
        )
    return {
        "status": "available" if records and all(record["status"] == "available" for record in records) else "partial",
        "records": records,
        "note": "This endpoint reports stored data only. It does not fetch from a provider or claim real-time freshness.",
    }


@app.get("/api/research/compute-status")
async def compute_status(request: Request) -> dict[str, object]:
    container = get_container(request)
    return {
        "local_backend": {
            "status": "available",
            "purpose": "Local research and paper-trading workers",
            "worker_topology": "standalone",
        },
        "remote_backend": {
            "status": "not_configured",
            "name": "Cosmos",
            "message": "Remote compute is not configured. Scheduler, authentication, allocation, network, storage, and runtime details are required before integration.",
        },
        "jobs": [],
        "note": "No remote job, GPU, scheduler, or utilization data is reported until a verified backend exists.",
        "storage_backend": container.storage.backend_name,
    }


@app.get("/api/trades")
async def trades(request: Request, limit: int = Query(default=20, ge=1, le=200)):
    container = get_container(request)
    return container.storage.load_trades(limit=limit)


@app.get("/api/events")
async def events(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    container = get_container(request)
    return container.storage.load_events(limit=limit)


@app.get("/api/trade-memory")
async def trade_memory(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    container = get_container(request)
    return container.storage.load_trade_memory(limit=limit)


@app.get("/api/analytics/trade-memory")
async def trade_memory_summary(request: Request, limit: int = Query(default=500, ge=1, le=2000)):
    container = get_container(request)
    records = container.storage.load_trade_memory(limit=limit)
    return container.analytics.build_trade_memory_summary(records)


@app.get("/api/market/{symbol}")
async def market_data(symbol: str, request: Request, interval: str | None = None):
    container = get_container(request)
    resolved_interval = resolve_interval(request, interval)
    lookback_bars = (
        container.settings.lookback_bars
        if resolved_interval == container.settings.research_interval
        else container.settings.trading_lookback_bars
    )
    candles = container.storage.load_candles(symbol, resolved_interval, stage="processed")
    if not candles:
        _, candles = await container.ingestion.ingest_symbol(
            symbol,
            resolved_interval,
            lookback_bars,
        )
    return candles[-100:]


@app.get("/api/features/{symbol}")
async def features(symbol: str, request: Request, interval: str | None = None):
    container = get_container(request)
    resolved_interval = resolve_interval(request, interval)
    lookback_bars = (
        container.settings.lookback_bars
        if resolved_interval == container.settings.research_interval
        else container.settings.trading_lookback_bars
    )
    rows = container.storage.load_features(symbol, resolved_interval)
    if not rows:
        candles = container.storage.load_candles(symbol, resolved_interval, stage="processed")
        if not candles:
            _, candles = await container.ingestion.ingest_symbol(
                symbol,
                resolved_interval,
                lookback_bars,
            )
        rows = container.feature_engine.build_feature_rows(candles)
        container.storage.store_features(symbol, resolved_interval, rows)
    return rows[-100:]


@app.get("/api/strategies/{symbol}")
async def strategies(symbol: str, request: Request):
    container = get_container(request)
    return container.storage.load_strategy_registry(symbol)


@app.get("/api/analytics/summary")
async def analytics_summary(request: Request):
    container = get_container(request)
    report = container.storage.load_latest_report(stream="research") or container.storage.load_latest_report(
        stream="trading"
    )
    orders = container.storage.load_trades(limit=20)
    return container.analytics.build_summary(report, orders)


@app.get("/api/analytics/learning")
async def learning_summary(request: Request):
    container = get_container(request)
    resolved_symbols = getattr(request.app.state, "resolved_symbols", None) or resolve_symbols(
        container.settings.research_symbols,
        container.settings.use_market_universes,
        container.settings.market_universes,
    )
    registries_by_symbol = {
        symbol: container.storage.load_strategy_registry(symbol)
        for symbol in resolved_symbols
    }
    return container.analytics.build_learning_summary(
        resolved_symbols,
        registries_by_symbol,
    )


@app.get("/api/trades/replay/{trade_id}")
async def trade_replay(trade_id: str, request: Request, interval: str | None = None):
    container = get_container(request)
    trades = container.storage.load_trades(limit=500)
    trade = next((item for item in trades if item.trade_id == trade_id), None)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found.")

    paired_trade = None
    if trade.action.value == "BUY":
        paired_trade = next(
            (
                item
                for item in trades
                if item.symbol == trade.symbol and item.action.value == "SELL" and item.timestamp > trade.timestamp
            ),
            None,
        )
    elif trade.action.value == "SELL":
        paired_trade = next(
            (
                item
                for item in reversed(trades)
                if item.symbol == trade.symbol and item.action.value == "BUY" and item.timestamp < trade.timestamp
            ),
            None,
        )

    resolved_interval = resolve_interval(request, interval)
    lookback_bars = (
        container.settings.lookback_bars
        if resolved_interval == container.settings.research_interval
        else container.settings.trading_lookback_bars
    )
    candles = container.storage.load_candles(trade.symbol, resolved_interval, stage="processed")
    if not candles:
        _, candles = await container.ingestion.ingest_symbol(
            trade.symbol,
            resolved_interval,
            lookback_bars,
        )
    features = container.storage.load_features(trade.symbol, resolved_interval)
    if not features:
        features = container.feature_engine.build_feature_rows(candles)
        container.storage.store_features(trade.symbol, resolved_interval, features)

    return {
        "symbol": trade.symbol,
        "trade": trade,
        "paired_trade": paired_trade,
        "candles": candles,
        "features": features,
    }
