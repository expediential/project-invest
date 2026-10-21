# Implementation Audit

## Scope and method

Phase Zero inspected the checkout at `2d2fb84767f8bd0934019bd68d2efaf29dd594dd` after fetching the supplied public repository into an initially empty local clone. The working branch is `codex/phase-zero-audit`. Executable code, configuration, tests, Docker files, and deployment documents were reviewed; no runtime behavior was changed.

The repository is an early, paper-first research application, not yet an autonomous quant research platform. It has useful foundations (typed models, a FastAPI application, a paper broker, local/Postgres storage abstractions, synthetic tests), but its observed implementation does not yet meet the evidence, reproducibility, validation, persistence, or operational-safety requirements for promotion beyond controlled local paper experiments.

## Verified baseline

| Check | Result | Evidence |
| --- | --- | --- |
| Git state before changes | Clean; local clone initially had no commits or remote | `git status --short --branch`, then `git ls-remote` and `git fetch` |
| Current source revision | `2d2fb84 update project invest` | `git log -5 --oneline` |
| Test suite | Not executed | `python -m pytest -q` failed: `No module named pytest`; no repository `.venv` is present |
| Source syntax | Passed | `python -m compileall -q src` |
| CI configuration | Not present | no `.github/`, `tox`, `nox`, lint, type-check, or pre-commit configuration found |

`pytest` must be installed in an isolated project environment before test results can be claimed. No test outcome is inferred from the static inspection.

## Findings

Each finding includes observed evidence, the smallest safe remedy, and the regression test required before it can be closed.

### F-01 — Public unauthenticated endpoint can initiate paper-trading cycles

- Severity: **critical**
- Evidence: `POST /api/trading/run` calls `TradingLab.run_cycle`; the root dashboard exposes a “Run Trading Cycle” action. The production Nginx configuration publishes the application on port 80 with no authentication or authorization layer.
- Affected files: `src/project_invest/api/app.py`, `src/project_invest/api/dashboard.py`, `deploy/nginx/nginx.conf`, `docker-compose.prod.yml`.
- Proposed fix: make trading-cycle control an authenticated administrative capability, default it off for public deployments, add rate limiting/idempotency keys, and keep read-only dashboard routes separately authorized. Until that exists, bind the control API to a private interface or disable the route in production.
- Required test: unauthenticated and read-only credentials receive no trading execution capability; a valid idempotency key permits exactly one paper cycle.

### F-02 — Runtime still accepts a `live` execution mode

- Severity: **critical**
- Evidence: `Settings.execution_mode` accepts `live`; `build_container` creates `LiveExecutionEngine`. It rejects orders today because no adapter is supplied, but the application supports a `live` code path and documents it as a valid setting.
- Affected files: `src/project_invest/config.py`, `src/project_invest/container.py`, `src/project_invest/execution/live.py`, `README.md`.
- Proposed fix: reject `live` during configuration validation for this release and move the live adapter boundary to a future, separately authorized feature. Keep paper as the only executable mode.
- Required test: every attempted `live` configuration fails before the API or any worker starts.

### F-03 — Deployment guidance silently substitutes synthetic data after a provider failure

- Severity: **critical**
- Evidence: `DEPLOY_ORACLE.md` and `DEPLOY_VPS.md` set `PROJECT_INVEST_ALLOW_MOCK_FALLBACK=true`; container wiring uses `MockMarketDataProvider` as fallback. Generated candles have fresh timestamps and can proceed through research or paper execution while being reported by provider name `mock`.
- Affected files: `DEPLOY_ORACLE.md`, `DEPLOY_VPS.md`, `src/project_invest/container.py`, `src/project_invest/services/ingestion.py`, `src/project_invest/providers/mock.py`.
- Proposed fix: forbid mock fallback outside explicit test/dev mode; return a typed data-unavailable result and block new entries when data is unavailable, stale, malformed, or synthetic.
- Required test: a Yahoo failure in a production/paper configuration produces no new order and a visible provider-health failure.

### F-04 — Feature history leaks latest sentiment into all historical rows

- Severity: **critical**
- Evidence: `FeatureEngineeringEngine.build_feature_rows` obtains one snapshot for `candles[-1].symbol` then copies it into every feature timestamp. `LocalSentimentProvider` does not retain publication or availability timestamps.
- Affected files: `src/project_invest/services/feature_engineering.py`, `src/project_invest/services/sentiment.py`, `src/project_invest/domain/models.py`.
- Proposed fix: version and store timestamped sentiment/events, join only observations available at each candle timestamp, and leave historical sentiment null when no valid as-of data exists.
- Required test: an event published after a historical bar cannot change that bar’s feature row or any backtest result.

### F-05 — “Walk-forward” evaluation reuses the training history in each fold

- Severity: **critical**
- Evidence: `run_walk_forward` calls `run` on `candles[:test_end]` with `trade_start_index=train_end`. `run` starts with `initial_capital` and allows positions entered at the first test index while signals use the complete in-sample prefix; no fitted artifact, final untouched holdout, purge, embargo, or fold-level data version is recorded. The same entire candle series is also used to score evolution candidates.
- Affected files: `src/project_invest/services/backtesting.py`, `src/project_invest/services/strategy_evolution.py`, `tests/test_backtesting.py`.
- Proposed fix: introduce explicit chronological train/validation/holdout definitions, fit only in train windows, use a strict OOS execution ledger, optionally purge overlapping labels, and prohibit holdout access until promotion review.
- Required test: perturbing a future/holdout bar cannot change prior fold features, signals, fitted parameters, or fold metrics.

### F-06 — Backtest bar execution and stop/target semantics are optimistic/ambiguous

- Severity: **high**
- Evidence: entries execute at the current candle close after a signal generated from that candle; `_determine_exit_price` chooses the stop whenever both stop and target lie inside one OHLC bar. No opening gap, intrabar ordering, trading calendar, missing-bar, split/dividend, or corporate-action policy is modeled.
- Affected files: `src/project_invest/services/backtesting.py`, `src/project_invest/providers/yahoo.py`.
- Proposed fix: document a bar-close/next-bar execution policy, model gap fills and conservative same-bar collision handling, validate OHLC continuity, and explicitly exclude unsupported adjustments/markets until supported.
- Required test: deterministic gap and same-bar stop/target fixtures yield documented conservative fills and fees.

### F-07 — Sharpe annualization is hard-coded to daily sampling

- Severity: **high**
- Evidence: `_sharpe_ratio` always multiplies by `sqrt(252)`, while configured research/trading intervals include `1m`, `5m`, `1h`, and `1d`.
- Affected files: `src/project_invest/services/backtesting.py`, `src/project_invest/config.py`, `README.md`.
- Proposed fix: make metric frequency and annualization an explicit validation-policy field; calculate only from documented return intervals or present an unannualized measure when the calendar is unknown.
- Required test: equivalent daily and intraday fixtures use their configured annualization factors; unsupported intervals fail validation rather than silently using 252.

### F-08 — Promotion gate allows weak candidates to enter paper trading

- Severity: **high**
- Evidence: `StrategyPromotionGate.apply` converts non-hard failures into reduced-confidence BUY signals (“Soft-promoted”), including insufficient validation trade count. Defaults allow one validation trade and negative minimum return/Sharpe thresholds.
- Affected files: `src/project_invest/services/strategy_promotion.py`, `src/project_invest/config.py`, `src/project_invest/services/research_lab.py`, `src/project_invest/services/trading_lab.py`.
- Proposed fix: separate `rejected`, `experimental`, `paper-eligible`, and `active-paper` states; all evidence-gate failures must prevent allocation. Define positive, market-aware sample and cost-adjusted thresholds in a versioned policy.
- Required test: a one-trade or threshold-failing strategy is recorded as rejected/experimental and cannot create a paper BUY.

### F-09 — Portfolio optimizer is not risk-aware and is not in the trading path

- Severity: **high**
- Evidence: `PortfolioOptimizer` normalizes champion score × `(1 - drawdown)` and returns equal weights if the total is nonpositive. It does not reject NaN/infinite values, use covariance, liquidity, uncertainty, current exposure, turnover, or costs. `ResearchLab` and `TradingLab` never call it.
- Affected files: `src/project_invest/services/portfolio_optimization.py`, `src/project_invest/services/analytics.py`, `src/project_invest/container.py`.
- Proposed fix: retain it as analytics-only until a constrained allocator is designed; then introduce validated inputs, zero-allocation capability, hard exposure constraints, and a separate allocator decision record before execution integration.
- Required test: invalid values, correlated candidates, stale inputs, concentration caps, and high uncertainty all produce bounded or zero allocations.

### F-10 — Persistent-state writes are non-transactional across portfolio, orders, events, and memory

- Severity: **high**
- Evidence: paper execution saves portfolio before appending the filled order; labs subsequently update registry, append event, and update trade memory as separate operations. Local JSON files and Postgres JSONB rows have no shared transaction or recovery protocol.
- Affected files: `src/project_invest/services/paper_trading.py`, `src/project_invest/services/research_lab.py`, `src/project_invest/services/trading_lab.py`, `src/project_invest/storage/data_lake.py`, `src/project_invest/storage/postgres.py`.
- Proposed fix: introduce a durable event/command ledger and atomic repository unit of work for a cycle/order transition; recover unfinished commands idempotently after restart.
- Required test: inject a failure after each persistence step and verify restart produces one reconciled portfolio/order/memory state with no duplicate fill.

### F-11 — Long-running work has competing owners and no cross-process lease

- Severity: **high**
- Evidence: API lifespan may own research/trading/legacy workers; `launch` starts an API with both embedded loops enabled; standalone `worker` exists in combined/research/trading modes; Docker separately starts research and trading workers. The in-memory lock only coordinates workers in one API process.
- Affected files: `src/project_invest/runtime.py`, `src/project_invest/api/app.py`, `src/project_invest/services/worker.py`, `docker-compose.prod.yml`, `README.md`.
- Proposed fix: choose one deployment mode (separate worker processes recommended), remove or hard-disable embedded execution loops in production, and use a storage-backed lease/cycle ID to prevent duplicate workers across processes.
- Required test: duplicate API/worker startup against a shared store yields one owner and no duplicated cycle/order.

### F-12 — Configuration silently coerces invalid values and lacks cross-field validation

- Severity: **high**
- Evidence: execution mode, storage backend, and sentiment provider validators silently fall back to defaults. Numeric risk, cost, loop, interval, provider, market, and DB/cache combinations have no range or cross-field checks.
- Affected files: `src/project_invest/config.py`, `src/project_invest/container.py`.
- Proposed fix: use strict enumerations and model-level validation; fail startup with safe, actionable messages for invalid configuration and unsafe combinations.
- Required test: invalid execution modes, negative risk/costs, malformed intervals, Postgres without DSN, cache without reachable configuration, and public trading control each fail closed.

### F-13 — Storage schema has no migration/versioning or query indexes

- Severity: **medium**
- Evidence: `PostgresResearchStorage._install` issues `CREATE TABLE IF NOT EXISTS` at runtime; JSONB payload tables rely on full-history scans and have no schema-version table or indexes for event/trade-memory lookups. Local storage has ad hoc JSON recovery.
- Affected files: `src/project_invest/storage/postgres.py`, `src/project_invest/storage/data_lake.py`, `src/project_invest/storage/repositories.py`.
- Proposed fix: add versioned migrations, a migration runner, explicit indexes, retention/backup guidance, and repository integration tests for local plus Postgres.
- Required test: upgrade from each supported schema version preserves portfolio, orders, events, registry, and memory; query plans use intended indexes.

### F-14 — Trade memory is fill-only and insufficient for decision learning

- Severity: **medium**
- Evidence: `TradeMemoryService.capture` returns immediately unless an order is filled. Rejected/held signals exist only as `ResearchEvent`; input feature timestamps, dataset/model versions, intended order, simulated fill, and outcome provenance are not separately modeled.
- Affected files: `src/project_invest/services/trade_memory.py`, `src/project_invest/domain/models.py`, `src/project_invest/services/research_lab.py`, `src/project_invest/services/trading_lab.py`.
- Proposed fix: introduce linked immutable records for signal, decision, intended order, fill, position, exit, and outcome; segregate decision-time features from outcome fields.
- Required test: rejected and skipped decisions are queryable without becoming fills; closed learning rows contain only decision-time inputs and a reconciled outcome.

### F-15 — Experiment system, data versions, and optional HPC interface do not exist

- Severity: **medium**
- Evidence: no experiment definition/run/artifact models, queue, status machine, deduplication, code/config snapshot, dataset/feature version, checksum, or generic/Cosmos execution adapter are present in `src/` or tests.
- Affected files: repository-wide; most directly `src/project_invest/domain/models.py`, `src/project_invest/storage/repositories.py`, `src/project_invest/container.py`.
- Proposed fix: implement a laptop-first durable experiment registry and bounded local queue only after Phase One safety fixes; add a Cosmos adapter only after approved access and scheduler/runtime verification.
- Required test: duplicate submissions deduplicate; queued/running/completed/failed/cancelled/rejected transitions persist and reproduce a recorded local run.

### F-16 — Documentation and packaging are inconsistent with the checkout

- Severity: **medium**
- Evidence: README instructs `Copy-Item .env.example .env`, but `.env.example` is absent. README says only mock/Yahoo providers yet the universe defaults include US equities, crypto, and FX. Deployment guides reference `jamesChlorosis/project-invest.git` rather than the supplied `expediential` repository and expose HTTP while advising HTTPS “later.”
- Affected files: `README.md`, `DEPLOY_ORACLE.md`, `DEPLOY_VPS.md`, `.gitignore`, `.dockerignore`, `src/project_invest/services/universe.py`.
- Proposed fix: add a secret-free validated example configuration, correct repository and capability statements, set NSE-only default scope, and make HTTPS/authentication prerequisites rather than deferred hardening.
- Required test: CI checks that documented example configuration loads and that all referenced repository-local files exist.

### F-17 — Observability and service health are incomplete

- Severity: **medium**
- Evidence: workers save only `last_error` in memory, use no bounded retry/backoff, cycle/correlation IDs, structured logs, heartbeat, or durable status. `/health` reports `status: ok` even when storage/provider access has not been checked and does not independently assess API, storage, workers, or data freshness.
- Affected files: `src/project_invest/services/worker.py`, `src/project_invest/api/app.py`, `src/project_invest/services/ingestion.py`.
- Proposed fix: add structured lifecycle records and separate liveness/readiness endpoints with storage, worker-lease, provider freshness, and queue status checks.
- Required test: provider outage, storage outage, and failed worker each produce distinct unhealthy/readiness responses while liveness remains meaningful.

## Deferred / not evidenced

- Cosmos access, scheduler type, GPU availability, university approval, quotas, data-transfer rules, and installed software were not available locally and must not be assumed.
- No real Yahoo or broker request was made during this audit.
- There is no evidence of real-money broker integration; the observed live engine rejects because it has no adapter. This is a safeguard, not authorization to enable live trading.

## Recommended Phase One implementation plan

### Phase One status update — 2026-10-21

Resolved in commits `2cf19fc` and `cb7c8ff`: live mode is rejected by configuration; embedded loops are rejected; operational cycle routes fail closed without a configured bearer token; mock fallback was removed and mock/unknown candles are blocked at the paper boundary; local historical sentiment now requires publication and observation timestamps; candidate validation excludes a final holdout; and promotion failures block BUY signals.

Still unresolved: cross-process durable worker leases, transactional portfolio/order/event reconciliation, storage migrations, calendar/corporate-action policy, authenticated read access, and full final-holdout reporting remain future work. The existing API health check is still not a complete storage/provider readiness check.

Do not begin experiment, ranking, allocator, ML, or Cosmos work until the following acceptance gates pass:

1. **Fail closed:** paper-only configuration, strict startup validation, provider/staleness gates, and no synthetic fallback in paper/production.
2. **Single owner:** one supported worker topology with a durable cycle lease/idempotency key and controlled shutdown.
3. **Atomic state:** reconcile a paper fill and associated ledger entries across restart/failure injection.
4. **Honest validation:** correct backtest timing/annualization and strict chronological split/holdout contracts.
5. **Operational boundary:** authenticated administrative control or no remotely exposed execution endpoint; separate storage and worker health.
6. **Evidence:** isolated environment dependencies installed; unit, API, local-storage, Postgres integration, restart, risk-rejection, and provider-failure tests pass.

Rollback for Phase One should be by reverting the dedicated change set and restoring the storage backup created before migrations. No database migration or deletion is authorized in Phase Zero.
