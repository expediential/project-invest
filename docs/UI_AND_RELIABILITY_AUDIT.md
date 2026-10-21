# UI and Reliability Audit

## Scope and baseline

This audit covers the paper portfolio lifecycle, storage contracts, operational API routes, dashboard data flow, and the existing research/worker boundaries on `main` after the Phase One safeguards.

The user verified the current suite before this work with:

```powershell
python -m pytest -q --basetemp .tmp_pytest -p no:cacheprovider
```

Result: `58 passed, 1 warning`. The warning is emitted by the installed FastAPI/Starlette test-client dependency and is not an application assertion failure. The automated workspace used for this audit cannot access the user's ignored `.venv`, so subsequent verification commands are documented and must be run from the user's activated environment until that environment is available to automation.

## Confirmed findings

| ID | Severity | Reproduction and cause | Status |
| --- | --- | --- | --- |
| UI-R-01 | High | Execute a paper BUY, then inspect `daily_pnl`. `PaperBroker.refresh_portfolio` writes lifetime realized plus open P&L into a field named daily P&L. It is neither day-bounded nor derived from a prior daily mark. | Open — replace dashboard usage with explicitly named total P&L and report daily P&L only when an actual daily baseline exists. |
| UI-R-02 | High | Execute a BUY with fees, mark the position unchanged, then compare `total_equity - starting_capital` with realized plus unrealized P&L. Position accounting excludes the entry fee from both open and closed P&L. | Open — preserve entry fees on positions and include them in unrealized/realized P&L. |
| UI-R-03 | High | Request `GET /api/portfolio` repeatedly. The endpoint calls `PaperBroker.get_portfolio`, which refreshes `as_of` and persists state despite no market price update or trade. | Open — make portfolio reads non-mutating. |
| UI-R-04 | High | Inspect storage and dashboard chart data sources. Only the latest `PortfolioSnapshot` is persisted; no versioned equity snapshots exist. Any smooth historical equity chart would be fabricated. | Open — add an append-only, versioned portfolio snapshot stream and expose its actual gaps. |
| UI-R-05 | Medium | A duplicate `ExecutionOrder.trade_id` can be appended twice by `LocalDataLake.append_trade`; local history has no deduplication guard. | Open — make order history idempotent by trade ID. |
| UI-R-06 | Medium | Refreshing the existing dashboard can call market/features endpoints that ingest and persist missing data. This does not place trades, but a read route has unexpected provider and storage side effects. | Open — distinguish cached read endpoints from an explicitly authorized data-refresh operation. |
| UI-R-07 | Medium | Existing dashboard labels expose raw `PortfolioSnapshot` values and no source-of-truth summary for cash, market value, P&L, drawdown, exposure, freshness, or stale data. | Open — add a portfolio summary service/API and use it for the redesigned overview. |
| UI-R-08 | Medium | There is no experiment/job persistence or configured remote-compute adapter. A Cosmos status panel cannot truthfully claim queue, GPU, scheduler, or connection state. | Open — expose an honest local/unconfigured compute status only; do not invent remote capabilities. |

## Probable issues needing environment or deployment verification

| ID | Area | Why it is not yet confirmed |
| --- | --- | --- |
| UI-P-01 | Cross-process worker ownership | Separate workers use the same storage but no durable lease is present. A shared local/Postgres deployment must be exercised with concurrent workers to confirm duplicate cycle behavior. |
| UI-P-02 | Postgres history and migration support | The local backend has no portfolio history stream today; Postgres must receive the same explicit schema and migration discipline when that stream is added. |
| UI-P-03 | Remote monitoring | No approved remote deployment, HTTPS endpoint, identity provider, or Cosmos allocation was supplied. Secure remote access and Cosmos execution remain unavailable. |

## Design limitations retained deliberately

- The project is paper-trading and research-only. No broker adapter or live execution path is enabled.
- Yahoo timestamps and availability are provider data, not a real-time market-data guarantee.
- Historical portfolio records created before snapshots exist cannot be reconstructed accurately.
- Local research remains the only supported compute backend. Remote cluster integration requires approved scheduler, authentication, allocation, storage, and network details.

## Repair plan

1. Correct fee-inclusive paper accounting; make read-only portfolio access non-mutating; deduplicate persisted order records.
2. Add durable portfolio snapshots and a tested summary API for accounting, drawdown, allocation, and data freshness.
3. Redesign the dashboard around those APIs, with explicit empty, stale, and unavailable states.
4. Add honest research/compute status and document the secure remote/Cosmos prerequisites without enabling speculative integrations.
