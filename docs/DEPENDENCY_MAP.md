# Dependency Map

## Runtime flow

```text
CLI / Docker / FastAPI lifespan
    ├── runtime.py (api, run-once, trade-once, launch, worker)
    └── api/app.py (HTTP routes and optional embedded workers)
            │
            ▼
      container.build_container(Settings)
            ├── storage.factory
            │     ├── LocalDataLake ───────────────► runtime/data_lake/*.json
            │     └── PostgresResearchStorage ─────► PostgreSQL JSONB tables
            │              └── optional CachedResearchStorage / RedisJsonCache
            ├── provider: MockMarketDataProvider | YahooFinanceProvider
            ├── MarketDataIngestionService
            ├── FeatureEngineeringEngine + local/neutral sentiment
            ├── StrategySignalEngine + StrategyEvolutionEngine + BacktestingEngine
            ├── MarketRegimeDetector + MetaStrategySelector + MultiTimeframeGate
            ├── StrategyPromotionGate + StrategyRegistryService
            ├── RiskManager + PaperBroker
            └── ResearchLab and TradingLab
```

## Research and paper-execution paths

```text
POST /api/research/run, `run-once`, research worker
  → ResearchLab.run_cycle(execute_trades=False)
  → ingest candles → store raw + processed
  → build features → store features
  → evolve genomes → full backtest + walk-forward metrics
  → promotion/meta/timeframe/sentiment gates
  → create skipped “research-only” order
  → update strategy registry → append ResearchEvent → capture fill-only trade memory
  → save research report

POST /api/trading/run, `trade-once`, trading worker
  → TradingLab.run_cycle()
  → ingest candles → store raw + processed
  → retrieve latest research report / registry
  → generate selected signal and gates
  → execution engine
      ├── PaperExecutionEngine → PaperBroker → RiskManager
      └── LiveExecutionEngine → rejects (no broker adapter currently wired)
  → save portfolio → append order → registry/event/trade-memory updates
  → save trading report
```

## State ownership and writes

| State | Writer(s) | Store | Observed issue |
| --- | --- | --- | --- |
| Raw/processed candles | ingestion; market/features API cache miss | JSON files or one JSONB row per symbol/interval/stage | API reads can trigger remote ingestion; no dataset version/freshness ledger |
| Features | research/trading labs; features API cache miss | JSON files or one JSONB row per symbol/interval | latest sentiment applied to all historical rows |
| Portfolio | `PaperBroker.get_portfolio`, buy, sell | one JSON file / one JSONB row | no transaction with trade/event/memory records |
| Orders | `PaperBroker` filled orders only | JSON history / JSONB rows | append not atomic with portfolio save |
| Reports | both labs | JSON latest + timestamped history / JSONB keys | timestamp key has second precision; collisions overwrite historical report |
| Events | both labs | JSON history / JSONB rows | full-history structures and no query indexes |
| Trade memory | both labs through `TradeMemoryService` | JSON history / JSONB rows | only filled orders are represented |
| Active strategy | labs | per-symbol JSON / JSONB row | deleted when no existing position; no reconciliation protocol |
| Strategy registry | labs | per-symbol JSON / JSONB row | status vocabulary lacks experimental/paper eligible/rejected/degraded |

## Worker ownership map

| Entry point | Worker owner | Execution behavior |
| --- | --- | --- |
| `api` | FastAPI only when loop flags are true | research loop is read-only; trading and legacy loops execute paper orders |
| `launch` | API child process with both embedded loop flags enabled | research plus trading loops |
| `worker --mode research` | standalone research worker | read-only |
| `worker --mode trading` | standalone trading worker | paper execution |
| `worker --mode combined` | standalone research worker with `execute_trades=True` | paper execution through `ResearchLab` |
| production compose | standalone research and trading containers | paper execution in trading container |

Only workers within one API process share an `asyncio.Lock`; no cross-process or cross-container coordination exists.

## API surface

Read routes expose dashboard, health/config/universe, reports, portfolio, trades/events/memory, market/features, strategies, analytics, and trade replay. Mutation routes are `POST /api/research/run` and `POST /api/trading/run`. No authentication, authorization, rate limit, idempotency key, request correlation ID, or queue boundary is implemented.

## Deliberately absent components

No experiment registry, durable research queue, dataset/feature/model artifacts, final holdout registry, opportunity-ranking service, constrained allocation decision service, trained decision filter, event ingestion with availability time, storage migrations, CI pipeline, or Cosmos/HPC adapter is currently present.
