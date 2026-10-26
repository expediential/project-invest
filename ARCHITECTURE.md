# Architecture Notes

This repository implements the first runnable slice of a larger quant research operating system.

## Current live modules

- `src/project_invest/providers/`
  - pluggable market data providers
- `src/project_invest/storage/`
  - repository protocols, local file backend, Postgres backend, and optional Redis cache layer
- `src/project_invest/services/feature_engineering.py`
  - feature store generation for common indicators
- `src/project_invest/services/strategy_signals.py`
  - signal logic for strategy genomes
- `src/project_invest/services/strategy_evolution.py`
  - genetic strategy discovery loop
- `src/project_invest/services/backtesting.py`
  - backtests with slippage, fees, stop loss, and take profit
- `src/project_invest/services/risk.py`
  - portfolio risk controls
- `src/project_invest/services/paper_trading.py`
  - simulated exchange and portfolio updates
- `src/project_invest/services/runtime_monitor.py`
  - bounded background local telemetry cache with optional NVIDIA discovery
- `src/project_invest/services/job_queue.py`
  - durable `LOCAL-LITE` research-only queue with atomic claims and restart recovery
- `src/project_invest/services/execution_backends.py`
  - local/remote execution contract; Cosmos is explicitly unconfigured
- `src/project_invest/execution/`
  - execution mode boundary between paper and live
- `src/project_invest/api/`
  - FastAPI control center and dashboard
- `src/project_invest/runtime.py`
  - explicit runtime entrypoints for API, run-once, and worker modes

## Execution boundary

The research stack stays the same in both modes:

```text
data -> features -> strategy evolution -> backtesting -> signal
```

Only the execution engine changes:

```text
paper mode: signal -> PaperExecutionEngine -> local simulated portfolio
live mode:  signal -> LiveExecutionEngine  -> broker adapter
```

`LiveExecutionEngine` is intentionally present now even though no broker adapter is wired yet. That keeps the interface stable for future Zerodha or Angel One integrations.

## Storage boundary

The service layer now talks to repository interfaces instead of concrete file storage:

```text
services -> repository protocols -> storage backend
```

Backends currently available:

- `local`
  - JSON files under `runtime/data_lake`
- `postgres`
  - tables for candles, features, trades, portfolio state, and reports
- optional Redis cache
  - wraps either backend without changing service code

## Production topology

Recommended deployment for one VM:

```text
nginx -> api -> repository layer -> postgres
                     |
                     -> optional redis cache

worker -> research loop -> same repository layer -> postgres
```

The API should not own the continuous worker loop in production. Run the worker as a separate process or container.

## Runtime monitor and job boundary

```text
background monitor -> bounded in-memory sample cache -> /api/runtime/monitor -> dashboard
authenticated job submit -> durable storage -> atomic local claim -> research-only cycle -> durable result state
```

The monitor does not block HTTP requests and does not retain unlimited samples. The local executor is fixed at one concurrent research job and passes `execute_trades=False`; it is not a paper-trading or live-execution queue. A job that was running when its executor stops is marked failed on recovery and never automatically rerun. Storage-level atomic claims prevent two local executors from taking the same queued job. The existing independently launched worker processes still require their own durable lease design.

`UnconfiguredCosmosBackend` defines only submit/status/result concepts. It cannot connect, schedule, upload data, or bypass validation/risk/paper boundaries.

## What should deepen next

- object storage for large historical datasets
- migration/versioning support for Postgres schemas
- mock/yahoo provider mix -> dedicated collectors for news, fundamentals, and options data
- live execution stub -> broker adapter implementation
- simple portfolio optimizer -> multi-strategy allocator with richer covariance/risk modeling

## Suggested next build order

1. Add storage migrations and repository-level integration tests.
2. Persist evolved strategies and research runs as first-class datasets.
3. Add multi-source ingestion for news and fundamentals.
4. Add model training jobs and ensemble predictors.
5. Expand allocation logic across multiple champion strategies.
6. Implement a real broker adapter behind `LiveExecutionEngine`.
